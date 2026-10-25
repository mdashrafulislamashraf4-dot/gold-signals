"""
============================================================
  tests/test_risk.py
  Unit & Integration Tests for Risk Engine (Commander A Specification)
  Covers:
    - 0.25% default risk & 0.50% maximum ceiling
    - Single simultaneous trade restriction
    - 1% initial daily drawdown stop
    - 3 consecutive losses halt & explicit /reset recovery
    - Spread ceiling filter
    - News risk warning (does NOT silently kill strategy)
============================================================
"""

import os
import tempfile
import pytest

from modules.database import DatabaseManager
from modules.risk_engine import RiskEngine
from config import MAX_SPREAD_ALLOWED


@pytest.fixture
def temp_db():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    db = DatabaseManager(db_path=path)
    yield db
    del db
    import gc
    gc.collect()
    try:
        if os.path.exists(path):
            os.remove(path)
    except Exception:
        pass


def test_position_sizing_broker_specs(temp_db):
    """
    Validates position sizing with broker contract spec:
    Account: $10,000
    Risk: 0.25% ($25.00)
    Stop distance: $2.50
    $1.00 move for 1 lot = $100 -> Risk per lot = $250
    Lot size = $25 / $250 = 0.10 lot
    """
    risk = RiskEngine(temp_db)
    res = risk.calculate_position_size(account_equity=10000.0, risk_distance=2.50)

    assert res["valid"] is True
    assert res["lot"] == 0.10
    assert res["dollar_risk"] == 25.00
    assert res["risk_pct"] == 0.25


def test_position_sizing_rejects_oversized_min_lot(temp_db):
    """
    If the required stop distance causes the minimum broker lot (0.01)
    to exceed the hard ceiling (0.50% of equity = $50 on $10,000), trade must be rejected.
    """
    risk = RiskEngine(temp_db)
    # Stop distance of $60: 0.01 lot risk = 0.01 * 60 * 100 = $60.00 > $50.00 ceiling
    res = risk.calculate_position_size(account_equity=10000.0, risk_distance=60.00)

    assert res["valid"] is False
    assert "exceed maximum permitted risk ceiling" in res["reason"]


def test_single_active_position_restriction(temp_db):
    """Only 1 open simulated trade at a time"""
    risk = RiskEngine(temp_db)

    # 1. Initially no trades -> approved
    app1 = risk.evaluate_trade_approval(current_spread=0.25, current_atr=2.50, avg_atr=2.50)
    assert app1["approved"] is True

    # 2. Add active trade to database
    temp_db.save_signal({
        "trade_id": 1,
        "direction": "BUY",
        "entry": 2685.00,
        "sl": 2680.00,
        "tp1": 2690.00,
        "tp2": 2695.00,
    })

    # 3. New trade evaluation must be blocked
    app2 = risk.evaluate_trade_approval(current_spread=0.25, current_atr=2.50, avg_atr=2.50)
    assert app2["approved"] is False
    assert app2["reason"] == "MAX_POSITION_REACHED"


def test_daily_drawdown_stop_1_pct(temp_db):
    """Initial daily drawdown stop at 1.0% ($100 on $10,000)"""
    risk = RiskEngine(temp_db)

    # Record cumulative daily losses of $105.00
    temp_db.record_trade_loss(50.00)
    temp_db.record_trade_loss(55.00)

    app = risk.evaluate_trade_approval(current_spread=0.25, current_atr=2.50, avg_atr=2.50)
    assert app["approved"] is False
    assert app["reason"] in ("DAILY_DRAWDOWN_STOP_REACHED", "DAILY_LOSS_LIMIT_REACHED")


def test_three_consecutive_losses_does_not_halt(temp_db):
    """
    User instruction: Consecutive loss halt rule removed.
    Three consecutive losses must NOT halt trading.
    """
    risk = RiskEngine(temp_db)

    # 3 consecutive losses
    temp_db.record_trade_loss(10.00)
    temp_db.record_trade_loss(10.00)
    temp_db.record_trade_loss(10.00)

    # Check that trading continues and is NOT halted
    app = risk.evaluate_trade_approval(current_spread=0.25, current_atr=2.50, avg_atr=2.50)
    assert app["approved"] is True


def test_spread_ceiling_filter(temp_db):
    """Trades must be rejected when current spread exceeds MAX_SPREAD_ALLOWED"""
    risk = RiskEngine(temp_db)
    app = risk.evaluate_trade_approval(
        current_spread=MAX_SPREAD_ALLOWED + 0.20,
        current_atr=2.50,
        avg_atr=2.50,
    )
    assert app["approved"] is False
    assert app["reason"] in ("SPREAD_EXCEEDS_LIMIT", "SPREAD_TOO_HIGH")


def test_news_risk_warning_does_not_silently_kill_strategy(temp_db):
    """
    Commander A Rule:
    'News risk may be shown as a warning; it must not silently disable the strategy solely because of the clock.'
    """
    risk = RiskEngine(temp_db)
    app = risk.evaluate_trade_approval(
        current_spread=0.25,
        current_atr=2.50,
        avg_atr=2.50,
        is_news_blackout=True,
        news_event_name="FOMC Decision",
    )
    # Trade should still be approved, but carry a prominent warning
    assert app["approved"] is True
    assert "FOMC Decision" in app["news_warning"]
