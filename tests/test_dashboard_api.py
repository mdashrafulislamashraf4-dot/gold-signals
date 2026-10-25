"""
============================================================
  tests/test_dashboard_api.py
  Unit Tests for Web Dashboard API & TradingView Webhook
============================================================
"""

import unittest
from flask import Flask
from config import WEBHOOK_SECRET
from dashboard.routes import dashboard_bp, init_dashboard_context
from modules.database import DatabaseManager
from modules.risk_engine import RiskEngine
from modules.signal_engine import SignalEngine
from modules.trade_manager import TradeManager


class DummyMarketData:
    def get_market_snapshot(self):
        return {
            "price": 2680.50,
            "bid": 2680.35,
            "ask": 2680.65,
            "spread": 0.30,
            "is_stale": False,
            "provider": "TestFeed",
        }

    def get_health_status(self):
        return {"status": "HEALTHY"}


class TestDashboardAPI(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.app = Flask(__name__, template_folder="../dashboard/templates")
        cls.app.register_blueprint(dashboard_bp)
        cls.client = cls.app.test_client()

        cls.db = DatabaseManager("database/test_api.db")
        cls.risk = RiskEngine(cls.db)
        cls.trade_mgr = TradeManager(cls.db, cls.risk)
        cls.signal_eng = SignalEngine(cls.db, cls.risk)

        init_dashboard_context(
            market_data=DummyMarketData(),
            technical=None,
            news_analyzer=None,
            signal_engine=cls.signal_eng,
            trade_manager=cls.trade_mgr,
            db_manager=cls.db,
            risk_engine=cls.risk,
        )

    def setUp(self):
        # Reset kill switch and clear test signals
        self.risk.trigger_kill_switch(False)
        with self.db.get_connection() as conn:
            conn.execute("DELETE FROM signals")
            conn.execute("DELETE FROM risk_state")
            conn.commit()

    def test_api_status_endpoint(self):
        res = self.client.get("/api/status")
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertIn("market", data)
        self.assertEqual(data["market"]["price"], 2680.50)
        self.assertIn("account", data)

    def test_killswitch_toggle(self):
        res = self.client.post("/api/killswitch")
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data["success"])
        self.assertTrue(data["kill_switch"])

    def test_tradingview_webhook_unauthorized(self):
        res = self.client.post("/api/webhook/tradingview", json={"secret": "wrong"})
        self.assertEqual(res.status_code, 401)

    def test_tradingview_webhook_valid(self):
        # Ensure kill switch is off
        self.risk.trigger_kill_switch(False)
        payload = {
            "secret": WEBHOOK_SECRET,
            "action": "BUY",
            "symbol": "XAUUSD",
            "entry": 2680.0,
            "sl": 2676.0,
            "tp": 2685.0,
            "risk_pct": 0.25,
        }
        res = self.client.post("/api/webhook/tradingview", json=payload)
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertEqual(data["status"], "accepted")
        self.assertIn("signal_uuid", data)


if __name__ == "__main__":
    unittest.main()
