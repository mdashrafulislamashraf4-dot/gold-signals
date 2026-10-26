"""
Unit tests for the 3 Independent Modular Scalping Engines and Signal Arbiter
"""

import pytest
import pandas as pd
import numpy as np

from modules.engines.sweep_engine import LiquiditySweepEngine
from modules.engines.trend_engine import TrendPullbackEngine
from modules.engines.range_engine import RangeBreakoutEngine
from modules.engines.signal_arbiter import SignalArbiter


@pytest.fixture
def sample_market_data():
    dates_15m = pd.date_range("2026-10-23 00:00", periods=50, freq="15min")
    df_15m = pd.DataFrame({
        "Open": np.linspace(4000, 4015, 50),
        "High": np.linspace(4002, 4018, 50),
        "Low": np.linspace(3998, 4013, 50),
        "Close": np.linspace(4001, 4016, 50),
        "Volume": [1000] * 50
    }, index=dates_15m)

    dates_5m = pd.date_range("2026-10-23 00:00", periods=60, freq="5min")
    df_5m = pd.DataFrame({
        "Open": np.linspace(4005, 4015, 60),
        "High": np.linspace(4007, 4018, 60),
        "Low": np.linspace(4003, 4013, 60),
        "Close": np.linspace(4006, 4016, 60),
        "Volume": [500] * 60
    }, index=dates_5m)

    dates_1m = pd.date_range("2026-10-23 00:00", periods=80, freq="1min")
    df_1m = pd.DataFrame({
        "Open": np.linspace(4010, 4016, 80),
        "High": np.linspace(4011, 4017, 80),
        "Low": np.linspace(4009, 4015, 80),
        "Close": np.linspace(4010.5, 4016.5, 80),
        "Volume": [100] * 80
    }, index=dates_1m)

    return df_15m, df_5m, df_1m


def test_independent_sweep_engine(sample_market_data):
    df_15m, df_5m, df_1m = sample_market_data
    engine = LiquiditySweepEngine(enabled=True)
    res = engine.analyze(df_15m, df_5m, df_1m, current_price=4016.0, current_spread=0.25)
    assert "valid" in res
    assert res["engine_name"] == "Liquidity Sweep + BOS"


def test_independent_trend_engine(sample_market_data):
    df_15m, df_5m, df_1m = sample_market_data
    engine = TrendPullbackEngine(enabled=True)
    res = engine.analyze(df_15m, df_5m, df_1m, current_price=4016.0, current_spread=0.25)
    assert "valid" in res
    assert res["engine_name"] == "Trend Pullback + EMA Retest"


def test_independent_range_engine(sample_market_data):
    df_15m, df_5m, df_1m = sample_market_data
    engine = RangeBreakoutEngine(enabled=True)
    res = engine.analyze(df_15m, df_5m, df_1m, current_price=4016.0, current_spread=0.25)
    assert "valid" in res
    assert res["engine_name"] == "Range Breakout + Retest"


def test_signal_arbiter_engine_toggles():
    arbiter = SignalArbiter(enable_sweep=True, enable_trend=True, enable_range=False)
    status = arbiter.get_status()
    assert status["Liquidity Sweep + BOS"] is True
    assert status["Trend Pullback + EMA Retest"] is True
    assert status["Range Breakout + Retest"] is False

    # Toggle range engine to True
    ok = arbiter.set_engine_state("Range Breakout + Retest", True)
    assert ok is True
    assert arbiter.range_engine.enabled is True
