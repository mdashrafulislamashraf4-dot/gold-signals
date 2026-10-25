"""
============================================================
  tests/test_risk_engine.py
  Unit Tests for Risk Protection Guardian & Position Sizing
============================================================
"""

import unittest
import os
from unittest.mock import patch
from modules.database import DatabaseManager
from modules.risk_engine import RiskEngine


class TestRiskEngine(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.test_db_path = "database/test_signals.db"
        cls.db = DatabaseManager(cls.test_db_path)
        cls.risk = RiskEngine(cls.db)

    def setUp(self):
        # Clear database tables cleanly between tests without deleting locked file
        with self.db.get_connection() as conn:
            conn.execute("DELETE FROM signals")
            conn.execute("DELETE FROM risk_state")
            conn.commit()
        # Reset memory state
        self.risk.kill_switch_memory = False
        self.risk.db = self.db

    def test_position_sizing_broker_specifications(self):
        res = self.risk.calculate_position_size(
            account_equity=10000.0,
            risk_distance=5.0,
            risk_pct=0.25,
        )
        self.assertTrue(res["valid"])
        self.assertEqual(res["lot"], 0.05)
        self.assertEqual(res["dollar_risk"], 25.0)

    def test_position_sizing_respects_hard_risk_ceiling(self):
        res = self.risk.calculate_position_size(
            account_equity=10000.0,
            risk_distance=5.0,
            risk_pct=2.0,  # Clamped to 0.50%
        )
        self.assertTrue(res["valid"])
        self.assertLessEqual(res["risk_pct"], 0.50)
        self.assertEqual(res["lot"], 0.10)

    def test_max_spread_filter(self):
        approval_ok = self.risk.evaluate_trade_approval(current_spread=0.30, current_atr=3.0, avg_atr=3.0)
        self.assertTrue(approval_ok["approved"])

        approval_fail = self.risk.evaluate_trade_approval(current_spread=0.60, current_atr=3.0, avg_atr=3.0)
        self.assertFalse(approval_fail["approved"])
        self.assertEqual(approval_fail["reason"], "SPREAD_TOO_HIGH")

    def test_volatility_spike_filter(self):
        approval_spike = self.risk.evaluate_trade_approval(current_spread=0.25, current_atr=8.5, avg_atr=3.0)
        self.assertFalse(approval_spike["approved"])
        self.assertEqual(approval_spike["reason"], "ABNORMAL_VOLATILITY_SPIKE")

    def test_daily_loss_limit_gate(self):
        # 1. Daily loss gate halts trading when 1% loss ceiling is reached
        self.db.record_trade_loss(250.0)
        approval = self.risk.evaluate_trade_approval(current_spread=0.25, current_atr=3.0, avg_atr=3.0)
        self.assertFalse(approval["approved"])
        self.assertEqual(approval["reason"], "DAILY_LOSS_LIMIT_REACHED")

    def test_consecutive_losses_limit_gate(self):
        # Consecutive loss limit is disabled per user request: consecutive losses do not halt trading
        self.db.record_trade_loss(30.0)
        self.db.record_trade_loss(30.0)
        self.db.record_trade_loss(30.0)
        approval = self.risk.evaluate_trade_approval(current_spread=0.25, current_atr=3.0, avg_atr=3.0)
        self.assertTrue(approval["approved"])

    def test_emergency_kill_switch(self):
        self.risk.trigger_kill_switch(True)
        approval = self.risk.evaluate_trade_approval(current_spread=0.25, current_atr=3.0, avg_atr=3.0)
        self.assertFalse(approval["approved"])
        self.assertEqual(approval["reason"], "EMERGENCY_KILL_SWITCH_ACTIVE")

        self.risk.trigger_kill_switch(False)
        approval_resumed = self.risk.evaluate_trade_approval(current_spread=0.25, current_atr=3.0, avg_atr=3.0)
        self.assertTrue(approval_resumed["approved"])


if __name__ == "__main__":
    unittest.main()
