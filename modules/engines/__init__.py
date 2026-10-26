"""
============================================================
  modules/engines/__init__.py
  Independent Modular Scalping Engines for XAUUSD:
    1. LiquiditySweepEngine   (Liquidity Sweep + BOS)
    2. TrendPullbackEngine    (Trend Pullback + EMA 20/50 Retest)
    3. RangeBreakoutEngine    (Range Breakout + Retest)
    4. SignalArbiter          (Master Multi-Strategy Coordinator)
============================================================
"""

from .base_engine import BaseSetupEngine
from .sweep_engine import LiquiditySweepEngine
from .trend_engine import TrendPullbackEngine
from .range_engine import RangeBreakoutEngine
from .signal_arbiter import SignalArbiter

__all__ = [
    "BaseSetupEngine",
    "LiquiditySweepEngine",
    "TrendPullbackEngine",
    "RangeBreakoutEngine",
    "SignalArbiter",
]
