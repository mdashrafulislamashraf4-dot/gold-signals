"""
============================================================
  tests/test_trade_management.py
  Unit Tests for Active Trade Management (Commander A Lifecycle)
============================================================
"""

import unittest
from datetime import datetime
import pytz

from config import TIMEZONE
from modules.database import DatabaseManager
from modules.risk_engine import RiskEngine
from modules.trade_manager import TradeManager


class TestTradeManagement(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.test_db_path = "database/test_trade_mgr.db"
        cls.db = DatabaseManager(cls.test_db_path)
        cls.risk = RiskEngine(cls.db)
        cls.tm = TradeManager(cls.db, cls.risk)

    def setUp(self):
        with self.db.get_connection() as conn:
            conn.execute("DELETE FROM signals")
            conn.execute("DELETE FROM trade_management_log")
            conn.execute("DELETE FROM risk_state")
            conn.commit()

    def test_tp1_hit_and_partial_close(self):
        now_str = datetime.now(pytz.timezone(TIMEZONE)).isoformat()
        with self.db.get_connection() as conn:
            conn.execute("""
                INSERT INTO signals (
                    trade_id, signal_uuid, timestamp, mode, direction, entry_price,
                    tp1, tp2, sl, suggested_lot, status, result
                ) VALUES (
                    1, 'TEST-TP-01', ?, 'PAPER', 'BUY', 2680.0,
                    2685.0, 2690.0, 2676.0, 0.10, 'ACTIVE', 'PENDING'
                )
            """, (now_str,))
            conn.commit()

        actions = self.tm.process_open_trades(current_price=2685.50, current_spread=0.25)
        self.assertEqual(len(actions), 1)
        self.assertEqual(actions[0]["event"], "TP1_HIT")
        self.assertGreater(actions[0]["partial_pnl"], 0)

        with self.db.get_connection() as conn:
            trade = conn.execute("SELECT * FROM signals WHERE signal_uuid = 'TEST-TP-01'").fetchone()
            self.assertEqual(trade["status"], "ACTIVE")
            self.assertEqual(trade["tp1_hit"], 1)
            self.assertEqual(trade["partial_closed"], 1)
            self.assertGreater(trade["sl"], 2676.0)

    def test_tp2_hit_closes_runner(self):
        now_str = datetime.now(pytz.timezone(TIMEZONE)).isoformat()
        with self.db.get_connection() as conn:
            conn.execute("""
                INSERT INTO signals (
                    trade_id, signal_uuid, timestamp, mode, direction, entry_price,
                    tp1, tp2, sl, suggested_lot, status, result, tp1_hit, partial_closed, be_moved
                ) VALUES (
                    2, 'TEST-TP2-01', ?, 'PAPER', 'BUY', 2680.0,
                    2685.0, 2690.0, 2680.10, 0.10, 'ACTIVE', 'PENDING', 1, 1, 1
                )
            """, (now_str,))
            conn.commit()

        actions = self.tm.process_open_trades(current_price=2690.50, current_spread=0.25)
        self.assertEqual(len(actions), 1)
        self.assertEqual(actions[0]["event"], "TP2_HIT")

        with self.db.get_connection() as conn:
            trade = conn.execute("SELECT * FROM signals WHERE signal_uuid = 'TEST-TP2-01'").fetchone()
            self.assertEqual(trade["status"], "CLOSED")
            self.assertEqual(trade["result"], "TP2_HIT")
            self.assertEqual(trade["tp2_hit"], 1)

    def test_stop_loss_hit_and_cooldown_trigger(self):
        now_str = datetime.now(pytz.timezone(TIMEZONE)).isoformat()
        with self.db.get_connection() as conn:
            conn.execute("""
                INSERT INTO signals (
                    trade_id, signal_uuid, timestamp, mode, direction, entry_price,
                    tp1, tp2, sl, suggested_lot, status, result
                ) VALUES (
                    3, 'TEST-SL-01', ?, 'PAPER', 'BUY', 2680.0,
                    2685.0, 2690.0, 2676.0, 0.10, 'ACTIVE', 'PENDING'
                )
            """, (now_str,))
            conn.commit()

        actions = self.tm.process_open_trades(current_price=2675.80, current_spread=0.25)
        self.assertEqual(len(actions), 1)
        self.assertEqual(actions[0]["event"], "SL_HIT")
        self.assertLess(actions[0]["net_pnl"], 0)

        state = self.db.get_or_create_daily_risk_state()
        self.assertIsNotNone(state.get("cooldown_until"))

    def test_break_even_sl_exit_after_tp1(self):
        now_str = datetime.now(pytz.timezone(TIMEZONE)).isoformat()
        with self.db.get_connection() as conn:
            conn.execute("""
                INSERT INTO signals (
                    trade_id, signal_uuid, timestamp, mode, direction, entry_price,
                    tp1, tp2, sl, suggested_lot, status, result, tp1_hit, partial_closed, be_moved
                ) VALUES (
                    4, 'TEST-BE-01', ?, 'PAPER', 'BUY', 2680.0,
                    2685.0, 2690.0, 2680.10, 0.10, 'ACTIVE', 'PENDING', 1, 1, 1
                )
            """, (now_str,))
            conn.commit()

        actions = self.tm.process_open_trades(current_price=2680.00, current_spread=0.25)
        self.assertEqual(len(actions), 1)
        self.assertEqual(actions[0]["event"], "SL_HIT")

        with self.db.get_connection() as conn:
            trade = conn.execute("SELECT * FROM signals WHERE signal_uuid = 'TEST-BE-01'").fetchone()
            self.assertEqual(trade["status"], "CLOSED")
            self.assertEqual(trade["result"], "SL_HIT")
            self.assertEqual(trade["tp2_hit"], 0)


if __name__ == "__main__":
    unittest.main()
