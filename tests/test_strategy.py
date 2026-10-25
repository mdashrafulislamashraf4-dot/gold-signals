"""
============================================================
  tests/test_strategy.py
  Unit & Integration Tests for SMC Scalping Strategy Components:
  15M Trend, 5M Sweeps, Displacement, FVG, OB, 1M Confirmation.
============================================================
"""

import unittest
import numpy as np
import pandas as pd
from modules.technical import TechnicalAnalyzer


class TestStrategyComponents(unittest.TestCase):

    def setUp(self):
        self.ta = TechnicalAnalyzer()

    def test_find_swings(self):
        highs = [2670.0, 2672.0, 2680.0, 2674.0, 2671.0, 2665.0, 2660.0, 2664.0, 2668.0]
        lows  = [2668.0, 2670.0, 2675.0, 2670.0, 2666.0, 2661.0, 2655.0, 2660.0, 2662.0]
        closes= [2669.0, 2671.0, 2678.0, 2672.0, 2668.0, 2662.0, 2658.0, 2663.0, 2665.0]
        opens = [2668.0, 2670.0, 2672.0, 2678.0, 2671.0, 2667.0, 2662.0, 2658.0, 2663.0]

        df = pd.DataFrame({"Open": opens, "High": highs, "Low": lows, "Close": closes})
        swings = self.ta.find_swings(df, left=2, right=2)

        self.assertIn("highs", swings)
        self.assertIn("lows", swings)
        self.assertTrue(any(abs(h["price"] - 2680.0) < 0.01 for h in swings["highs"]))
        self.assertTrue(any(abs(l["price"] - 2655.0) < 0.01 for l in swings["lows"]))

    def test_liquidity_sweep_detection(self):
        prior_low = 2670.0
        df = pd.DataFrame({
            "Open": [2675.0, 2672.0, 2671.0],
            "High": [2677.0, 2674.0, 2675.0],
            "Low":  [2672.0, 2667.0, 2670.0],
            "Close":[2673.0, 2672.0, 2674.0],
            "Volume":[1000, 1500, 1200],
        })
        swings = {"highs": [{"price": 2685.0}], "lows": [{"price": prior_low}]}
        liquidity = {"pdh": 2690.0, "pdl": 2670.0, "asian_high": 2685.0, "asian_low": 2672.0}
        eq_pools = {"equal_highs": [], "equal_lows": []}

        res = self.ta.detect_liquidity_sweep(df, liquidity, swings, eq_pools)
        self.assertTrue(res["bullish_sweep"])
        self.assertEqual(res["swept_level_price"], prior_low)

    def test_displacement_detection(self):
        atr = 2.0
        # Normal candle series: body < 4.5
        df_normal = pd.DataFrame({
            "Open": [2670.0, 2671.0, 2670.5],
            "High": [2672.0, 2672.5, 2671.5],
            "Low":  [2669.0, 2670.0, 2669.8],
            "Close":[2671.0, 2670.5, 2671.2],
        })
        disp_normal = self.ta.detect_displacement(df_normal, atr)
        self.assertFalse(disp_normal["bullish"])

        # Strong displacement: 3 bars, last bar has body = $5.00 (>= 4.5)
        df_disp = pd.DataFrame({
            "Open": [2670.0, 2671.0, 2670.0],
            "High": [2672.0, 2672.5, 2676.0],
            "Low":  [2669.0, 2670.0, 2669.5],
            "Close":[2671.0, 2670.5, 2675.0],  # Body = 5.0
        })
        disp_bull = self.ta.detect_displacement(df_disp, atr)
        self.assertTrue(disp_bull["bullish"])
        self.assertGreaterEqual(disp_bull["size"], 4.5)

    def test_fair_value_gap_detection(self):
        # 6 bars: Bar 0 High = 2672.0, Bar 2 Low = 2676.0 -> Gap: 2672 to 2676
        df = pd.DataFrame({
            "Open":  [2670.0, 2673.0, 2680.0, 2681.0, 2680.5, 2681.0],
            "High":  [2672.0, 2679.0, 2684.0, 2683.0, 2682.0, 2682.5],
            "Low":   [2669.0, 2672.5, 2676.0, 2678.0, 2679.0, 2680.0],
            "Close": [2671.5, 2678.5, 2682.0, 2680.0, 2681.5, 2682.0],
        })
        fvgs = self.ta.detect_fair_value_gaps(df, lookback=10)
        bullish_fvgs = [f for f in fvgs if f["type"] == "BULLISH"]
        self.assertGreater(len(bullish_fvgs), 0)
        self.assertEqual(bullish_fvgs[0]["bottom"], 2672.0)
        self.assertEqual(bullish_fvgs[0]["top"], 2676.0)

    def test_1m_confirmation(self):
        closes = [2670.0 + (i * 0.2) for i in range(25)]
        opens  = [c - 0.1 for c in closes]
        highs  = [c + 0.2 for c in closes]
        lows   = [o - 0.2 for o in opens]

        df_1m = pd.DataFrame({"Open": opens, "High": highs, "Low": lows, "Close": closes})
        conf_buy = self.ta.evaluate_1m_confirmation(df_1m, direction="BUY")
        self.assertTrue(conf_buy["confirmed"])

        closes_down = [2680.0 - (i * 0.2) for i in range(25)]
        opens_down  = [c + 0.1 for c in closes_down]
        highs_down  = [o + 0.2 for o in opens_down]
        lows_down   = [c - 0.2 for c in closes_down]

        df_1m_down = pd.DataFrame({"Open": opens_down, "High": highs_down, "Low": lows_down, "Close": closes_down})
        conf_sell = self.ta.evaluate_1m_confirmation(df_1m_down, direction="SELL")
        self.assertTrue(conf_sell["confirmed"])


if __name__ == "__main__":
    unittest.main()
