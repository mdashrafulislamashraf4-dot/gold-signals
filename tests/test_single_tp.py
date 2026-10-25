"""
Unit tests for Single TP High-Probability Scalp Strategy
"""
import pytest
from modules.telegram_bot import TelegramBot
from modules.setup_engines import SetupEngines
import pandas as pd
import numpy as np

def test_single_tp_message_format():
    sent = []
    class MockBot(TelegramBot):
        def _send_raw_text(self, text: str) -> bool:
            sent.append(text)
            return True

    bot = MockBot("token", ["12345"])
    
    # Single TP signal
    bot.send_signal({
        "direction": "BUY",
        "trade_id": 1,
        "entry": 4010.50,
        "tp": 4013.50,
        "sl": 4006.80,
    })
    assert sent[0] == "🟢 BUY #001 Entry: 4010.50 TP: 4013.50 SL: 4006.80"

    bot.send_signal({
        "direction": "SELL",
        "trade_id": 2,
        "entry": 4020.00,
        "tp": 4017.00,
        "sl": 4024.00,
    })
    assert sent[1] == "🔴 SELL #002 Entry: 4020.00 TP: 4017.00 SL: 4024.00"

    bot.send_tp_hit(trade_id=1)
    assert sent[2] == "✅ #001 TP HIT"

    bot.send_sl_hit(trade_id=2)
    assert sent[3] == "❌ #002 SL HIT"

def test_setup_engines_return_single_tp():
    engines = SetupEngines()
    # Mock data
    dates = pd.date_range("2026-10-23 09:00", periods=40, freq="5min")
    df_5m = pd.DataFrame({
        "Open": np.linspace(4000, 4010, 40),
        "High": np.linspace(4001, 4012, 40),
        "Low": np.linspace(3999, 4009, 40),
        "Close": np.linspace(4000.5, 4011.5, 40),
        "Volume": [1000] * 40
    }, index=dates)
    
    # Calculate adaptive target
    tgt = engines.calculate_adaptive_targets(
        direction="BUY",
        entry=4010.0,
        sl=4006.0,
        swings_m5={"highs": [{"price": 4013.0, "time": "t"}], "lows": []},
        swings_m15={"highs": [], "lows": []},
        fvgs=[],
        atr=3.5,
        spread=0.25
    )
    assert tgt["valid"] is True
    assert "tp" in tgt
    assert tgt["tp"] >= 4012.0
