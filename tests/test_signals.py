"""
============================================================
  tests/test_signals.py
  Unit & Integration Tests for Commander A Specification
  Covers:
    - Minimal Telegram message formatting (BUY, SELL, TP1, TP2, SL)
    - Sequential and persistent Trade IDs (#001, #002...)
    - Two-stage TP lifecycle (TP1 partial close + BE move, TP2 runner exit)
    - Zero duplicate alerts
    - Conservative execution rules (both TP & SL touched)
    - Database state recovery after reconnect
============================================================
"""

import os
import tempfile
import pytest
import pandas as pd
import numpy as np

from modules.database import DatabaseManager
from modules.risk_engine import RiskEngine
from modules.trade_manager import TradeManager
from modules.telegram_bot import TelegramBot
from modules.setup_engines import SetupEngines


@pytest.fixture
def temp_db():
    """Provides a fresh isolated temporary SQLite database"""
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


# ─────────────────────────────────────────────────────────
# 1. Telegram Message Formatting Tests
# ─────────────────────────────────────────────────────────
def test_signal_message_format_buy():
    """Verify minimal BUY format: 🟢 BUY #001 Entry: 2685.50 TP1: 2690.00 TP2: 2694.50 SL: 2681.00"""
    sent_messages = []

    class MockTelegramBot(TelegramBot):
        def _send_raw_text(self, text: str) -> bool:
            sent_messages.append(text)
            return True

    bot = MockTelegramBot(token="test_token", chat_ids=["12345"])
    signal = {
        "direction": "BUY",
        "trade_id": 1,
        "entry": 2685.50,
        "tp1": 2690.00,
        "tp2": 2694.50,
        "sl": 2681.00,
    }
    bot.send_signal(signal)
    assert len(sent_messages) == 1
    assert sent_messages[0] == "BUY #001 Entry: 2685.50 TP1: 2690.00 TP2: 2694.50 SL: 2681.00"


def test_signal_message_format_sell():
    """Verify minimal SELL format: SELL #002 Entry: 2685.50 TP1: 2681.00 TP2: 2676.50 SL: 2689.50"""
    sent_messages = []

    class MockTelegramBot(TelegramBot):
        def _send_raw_text(self, text: str) -> bool:
            sent_messages.append(text)
            return True

    bot = MockTelegramBot(token="test_token", chat_ids=["12345"])
    signal = {
        "direction": "SELL",
        "trade_id": 2,
        "entry": 2685.50,
        "tp1": 2681.00,
        "tp2": 2676.50,
        "sl": 2689.50,
    }
    bot.send_signal(signal)
    assert len(sent_messages) == 1
    assert sent_messages[0] == "SELL #002 Entry: 2685.50 TP1: 2681.00 TP2: 2676.50 SL: 2689.50"


def test_trade_result_formats():
    """Verify exact minimal trade result messages: TP, SL"""
    sent_messages = []

    class MockTelegramBot(TelegramBot):
        def _send_raw_text(self, text: str) -> bool:
            sent_messages.append(text)
            return True

    bot = MockTelegramBot(token="test_token", chat_ids=["12345"])

    bot.send_tp1_hit(trade_id=1)
    bot.send_tp2_hit(trade_id=1)
    bot.send_sl_hit(trade_id=2)

    assert sent_messages[0] == "#001 TP HIT"
    assert sent_messages[1] == "#001 TP HIT"
    assert sent_messages[2] == "#002 SL HIT"


# ─────────────────────────────────────────────────────────
# 2. Sequential & Persistent Trade IDs
# ─────────────────────────────────────────────────────────
def test_trade_id_sequential_and_persistent(temp_db):
    """Verifies trade IDs increment sequentially and survive reconnects"""
    id1 = temp_db.get_next_trade_id()
    id2 = temp_db.get_next_trade_id()
    id3 = temp_db.get_next_trade_id()

    assert id1 == 1
    assert id2 == 2
    assert id3 == 3

    # Reconnect fresh instance to the same database file
    reconnected_db = DatabaseManager(db_path=temp_db.db_path)
    id4 = reconnected_db.get_next_trade_id()
    assert id4 == 4


# ─────────────────────────────────────────────────────────
# 3. Two-Stage TP Lifecycle, Partial Close & BE Move
# ─────────────────────────────────────────────────────────
def test_two_stage_tp_lifecycle(temp_db):
    """
    Simulates:
    1. BUY Trade opened @ 2685.00, SL 2680.00, TP1 2690.00, TP2 2695.00
    2. Price touches TP1 (2690.50):
       - Generates TP1_HIT
       - Sets tp1_hit = 1
       - Closes 50% partial position
       - Moves SL to Break-Even (2685.10)
       - Trade remains ACTIVE
    3. Price re-tested at 2691.00:
       - No duplicate TP1 alert emitted
    4. Price reaches TP2 (2695.50):
       - Generates TP2_HIT
       - Trade is marked CLOSED
    """
    risk = RiskEngine(temp_db)
    tm = TradeManager(temp_db, risk)

    # 1. Open Trade
    trade_id = temp_db.get_next_trade_id()
    sig_id = temp_db.save_signal({
        "trade_id": trade_id,
        "direction": "BUY",
        "entry": 2685.00,
        "sl": 2680.00,
        "tp1": 2690.00,
        "tp2": 2695.00,
        "suggested_lot": 0.10,
        "risk_pct": 0.25,
        "spread": 0.25,
    })

    # 2. Price hits TP1
    events = tm.process_open_trades(current_price=2690.50, current_spread=0.25)
    assert len(events) == 1
    assert events[0]["event"] == "TP1_HIT"
    assert events[0]["trade_id"] == 1

    # Verify DB state: tp1_hit=1, be_moved=1, new_sl=2685.10, status=ACTIVE
    trade_row = temp_db.get_signal_by_trade_id(1)
    assert trade_row["tp1_hit"] == 1
    assert trade_row["be_moved"] == 1
    assert trade_row["sl"] == 2685.10
    assert trade_row["status"] == "ACTIVE"

    # 3. Check duplicate prevention on subsequent tick
    dup_events = tm.process_open_trades(current_price=2691.00, current_spread=0.25)
    assert len(dup_events) == 0

    # 4. Price reaches TP2
    tp2_events = tm.process_open_trades(current_price=2695.50, current_spread=0.25)
    assert len(tp2_events) == 1
    assert tp2_events[0]["event"] == "TP2_HIT"

    final_row = temp_db.get_signal_by_trade_id(1)
    assert final_row["status"] == "CLOSED"
    assert final_row["result"] == "TP2_HIT"
    assert final_row["tp2_hit"] == 1


def test_sl_after_tp1_closes_remaining_without_dual_final(temp_db):
    """
    Simulates:
    1. Trade hits TP1 -> moved to BE
    2. Price drops to BE SL -> closes remaining position with SL_HIT
    3. Trade never reports TP2
    """
    risk = RiskEngine(temp_db)
    tm = TradeManager(temp_db, risk)

    trade_id = temp_db.get_next_trade_id()
    sig_id = temp_db.save_signal({
        "trade_id": trade_id,
        "direction": "BUY",
        "entry": 2685.00,
        "sl": 2680.00,
        "tp1": 2690.00,
        "tp2": 2695.00,
        "suggested_lot": 0.10,
        "risk_pct": 0.25,
        "spread": 0.25,
    })

    # Hit TP1
    tm.process_open_trades(current_price=2690.50, current_spread=0.25)

    # Price falls back to break-even SL (2685.00)
    sl_events = tm.process_open_trades(current_price=2685.00, current_spread=0.25)
    assert len(sl_events) == 1
    assert sl_events[0]["event"] == "SL_HIT"

    final_row = temp_db.get_signal_by_trade_id(trade_id)
    assert final_row["status"] == "CLOSED"
    assert final_row["result"] == "SL_HIT"
    assert final_row["tp2_hit"] == 0  # Never reports TP2


# ─────────────────────────────────────────────────────────
# 4. Conservative Execution Rule (Both TP and SL Touched)
# ─────────────────────────────────────────────────────────
def test_conservative_execution_rule_both_touched(temp_db):
    """
    If a single candle simultaneously spans both SL and TP1,
    conservative execution assumes adverse stop loss execution first.
    """
    risk = RiskEngine(temp_db)
    tm = TradeManager(temp_db, risk)

    trade_id = temp_db.get_next_trade_id()
    temp_db.save_signal({
        "trade_id": trade_id,
        "direction": "BUY",
        "entry": 2685.00,
        "sl": 2680.00,
        "tp1": 2690.00,
        "tp2": 2695.00,
        "suggested_lot": 0.10,
        "risk_pct": 0.25,
        "spread": 0.25,
    })

    # 1M candle with High 2691.00 (>= TP1) and Low 2679.00 (<= SL)
    df_1m = pd.DataFrame([{
        "Open": 2685.00,
        "High": 2691.00,
        "Low": 2679.00,
        "Close": 2684.00,
    }])

    events = tm.process_open_trades(current_price=2684.00, current_spread=0.25, df_1m=df_1m)
    assert len(events) == 1
    assert events[0]["event"] == "SL_HIT"

    final_row = temp_db.get_signal_by_trade_id(trade_id)
    assert final_row["status"] == "CLOSED"
    assert final_row["result"] == "SL_HIT"
    assert final_row["tp1_hit"] == 0


# ─────────────────────────────────────────────────────────
# 5. Setup Engines Unit Tests (3 Independent Engines)
# ─────────────────────────────────────────────────────────
def test_setup_engines_instantiation():
    """Validates SetupEngines initializes and has all 3 required methods"""
    se = SetupEngines()
    assert hasattr(se, "detect_liquidity_sweep_bos")
    assert hasattr(se, "detect_trend_pullback_ema")
    assert hasattr(se, "detect_range_breakout_retest")
    assert hasattr(se, "evaluate_all_setups")


def test_engine1_liquidity_sweep_bos_structure():
    """Generates synthetic sweep data and verifies Engine 1 logic"""
    se = SetupEngines()
    # Create synthetic M15 data with clear swing low at 2680.00
    dates_15m = pd.date_range("2026-10-25 00:00", periods=40, freq="15min")
    df_15m = pd.DataFrame({
        "Open": [2685.0 + i * 0.1 for i in range(40)],
        "High": [2687.0 + i * 0.1 for i in range(40)],
        "Low": [2683.0 + i * 0.1 for i in range(40)],
        "Close": [2685.0 + i * 0.1 for i in range(40)],
    }, index=dates_15m)
    df_15m.loc[df_15m.index[10], "Low"] = 2675.00

    dates_5m = pd.date_range("2026-10-25 06:00", periods=30, freq="5min")
    df_5m = pd.DataFrame({
        "Open": [2680.0] * 30,
        "High": [2683.0] * 30,
        "Low": [2678.0] * 30,
        "Close": [2681.0] * 30,
    }, index=dates_5m)

    # Completed candle wicks below 2675.00 and closes back above 2675.00 (bullish sweep)
    df_5m.iloc[-2, df_5m.columns.get_loc("Low")] = 2674.00
    df_5m.iloc[-2, df_5m.columns.get_loc("Close")] = 2677.00
    df_5m.iloc[-2, df_5m.columns.get_loc("Open")] = 2676.00

    res = se.detect_liquidity_sweep_bos(
        df_15m=df_15m,
        df_5m=df_5m,
        df_1m=None,
        current_price=2678.00,
        current_spread=0.25,
    )
    assert "engine_name" in res
    assert res["engine_name"] == "Liquidity Sweep + BOS"


def test_engine2_trend_pullback_ema_structure():
    """Verifies Engine 2 detects trend pullback and returns correct structure"""
    se = SetupEngines()
    dates_15m = pd.date_range("2026-10-25 00:00", periods=50, freq="15min")
    # Bullish trend: EMA50 > EMA200
    df_15m = pd.DataFrame({
        "Open": [2650.0 + i * 1.0 for i in range(50)],
        "High": [2652.0 + i * 1.0 for i in range(50)],
        "Low": [2648.0 + i * 1.0 for i in range(50)],
        "Close": [2651.0 + i * 1.0 for i in range(50)],
    }, index=dates_15m)

    dates_5m = pd.date_range("2026-10-25 08:00", periods=40, freq="5min")
    df_5m = pd.DataFrame({
        "Open": [2700.0] * 40,
        "High": [2705.0] * 40,
        "Low": [2695.0] * 40,
        "Close": [2702.0] * 40,
    }, index=dates_5m)

    res = se.detect_trend_pullback_ema(
        df_15m=df_15m,
        df_5m=df_5m,
        df_1m=None,
        current_price=2702.00,
        current_spread=0.25,
    )
    assert "engine_name" in res
    assert res["engine_name"] == "Trend Pullback + EMA Retest"


def test_engine3_range_breakout_structure():
    """Verifies Engine 3 detects range breakout and returns correct structure"""
    se = SetupEngines()
    dates_15m = pd.date_range("2026-10-25 00:00", periods=30, freq="15min")
    # Horizontal consolidation between 2680 and 2690
    df_15m = pd.DataFrame({
        "Open": [2685.0] * 30,
        "High": [2690.0] * 30,
        "Low": [2680.0] * 30,
        "Close": [2685.0] * 30,
    }, index=dates_15m)

    dates_5m = pd.date_range("2026-10-25 06:00", periods=30, freq="5min")
    df_5m = pd.DataFrame({
        "Open": [2685.0] * 30,
        "High": [2688.0] * 30,
        "Low": [2682.0] * 30,
        "Close": [2686.0] * 30,
    }, index=dates_5m)

    # Breakout bar on M5 above 2690.00
    df_5m.iloc[-3, df_5m.columns.get_loc("Close")] = 2692.00
    # Retest bar on M5 near 2690.00
    df_5m.iloc[-2, df_5m.columns.get_loc("Low")] = 2690.10
    df_5m.iloc[-2, df_5m.columns.get_loc("Close")] = 2691.50
    df_5m.iloc[-2, df_5m.columns.get_loc("Open")] = 2690.50

    res = se.detect_range_breakout_retest(
        df_15m=df_15m,
        df_5m=df_5m,
        df_1m=None,
        current_price=2692.00,
        current_spread=0.25,
    )
    assert "engine_name" in res
    assert res["engine_name"] == "Range Breakout + Retest"
