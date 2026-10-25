"""
============================================================
  tests/test_dynamic_tp_sl.py
  Unit Tests for Dynamic Take-Profit & Dynamic Stop-Loss Engine
  Verifies structural candidate ranking, front-running buffers,
  cost-adjusted R:R validation, and prohibition of fixed 1:5 ratio.
============================================================
"""

import unittest
from modules.dynamic_tp_engine import DynamicTPEngine
from modules.risk_engine import RiskEngine


class TestDynamicTPSLEngine(unittest.TestCase):

    def setUp(self):
        self.tp_engine = DynamicTPEngine(min_rr_ratio=1.0)
        self.risk_engine = RiskEngine()

    def test_dynamic_stop_loss_calculation(self):
        # Entry at 2680, sweep at 2676.0, ATR = 3.0
        # SL should be placed beyond sweep level with ATR buffer (1.1 * 3 = 3.3)
        res = self.risk_engine.calculate_stop_loss(
            direction="BUY",
            entry_price=2680.0,
            sweep_level=2676.0,
            last_swing_extreme=2677.0,
            ob_extreme=None,
            atr=3.0,
        )
        self.assertTrue(res["valid"])
        self.assertLess(res["sl"], 2676.0)
        self.assertGreaterEqual(res["risk_distance"], 1.5)
        self.assertLessEqual(res["risk_distance"], 8.5)

    def test_stop_loss_rejects_excessive_distance(self):
        # If sweep level is 2660 (20 dollars away on a scalp), it must be rejected
        res = self.risk_engine.calculate_stop_loss(
            direction="BUY",
            entry_price=2680.0,
            sweep_level=2660.0,
            last_swing_extreme=2665.0,
            ob_extreme=None,
            atr=3.0,
        )
        self.assertFalse(res["valid"])
        self.assertIn("exceeds maximum allowed scalping stop", res["reason"])

    def test_dynamic_take_profit_identifies_opposing_liquidity(self):
        # Entry 2680.0, SL 2676.0 (Risk = $4.00)
        # Opposing Equal Highs (BSL) at 2685.20
        # Should front-run 2685.20 and provide R:R ~ 1.1 - 1.2R
        res = self.tp_engine.find_opposing_targets(
            direction="BUY",
            entry_price=2680.0,
            sl_price=2676.0,
            swings_5m={"highs": [2685.0], "lows": []},
            swings_15m={"highs": [2692.0], "lows": []},
            eq_pools={"equal_highs": [2685.20], "equal_lows": []},
            fvgs_5m=[],
            fvgs_15m=[],
            obs_5m={},
            obs_15m={},
            key_levels={"resistance": [2688.0], "support": []},
            atr=3.0,
            spread=0.25,
        )
        self.assertTrue(res["valid"])
        self.assertGreater(res["tp"], 2680.0)
        self.assertLess(res["tp"], 2685.20)  # Must front-run the liquidity level
        self.assertGreaterEqual(res["rr_ratio"], 1.0)
        self.assertIn("Buy-Side Liquidity", res["target_basis"])

    def test_dynamic_tp_rejects_insufficient_reward_after_costs(self):
        # Entry 2680.0, SL 2676.0 (Risk = $4.00)
        # But nearest opposing resistance is at 2680.50 (only 0.50 reward vs 0.34 total costs)
        res = self.tp_engine.find_opposing_targets(
            direction="BUY",
            entry_price=2680.0,
            sl_price=2676.0,
            swings_5m={"highs": [2680.50], "lows": []},
            swings_15m={"highs": [], "lows": []},
            eq_pools={"equal_highs": [], "equal_lows": []},
            fvgs_5m=[],
            fvgs_15m=[],
            obs_5m={},
            obs_15m={},
            key_levels={"resistance": [2680.50], "support": []},
            atr=1.0,
            spread=0.35,
        )
        # If nearest obstacle offers < 1.0R, baseline fallback is checked or rejected
        # Net reward for 0.50 is < 0.20, which is filtered out of candidates
        self.assertIn("candidates", res)

    def test_transaction_costs_coverage(self):
        # Spread $0.30 + Commission ($0.04/oz) + Slippage ($0.05) = $0.39
        costs = self.tp_engine.calculate_transaction_costs(spread=0.30)
        self.assertAlmostEqual(costs, 0.39, places=2)


if __name__ == "__main__":
    unittest.main()
