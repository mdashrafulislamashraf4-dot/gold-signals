"""
============================================================
  modules/setup_engines.py
  Modular Multi-Engine Interface for Gold QuickScalp AI
  Delegates to 3 Independent Decoupled Strategy Engines:
    1. LiquiditySweepEngine   (modules.engines.sweep_engine)
    2. TrendPullbackEngine    (modules.engines.trend_engine)
    3. RangeBreakoutEngine    (modules.engines.range_engine)
    + SignalArbiter           (modules.engines.signal_arbiter)
============================================================
"""

import logging
from typing import Dict, Any, List, Optional
import pandas as pd

from modules.engines.base_engine import BaseSetupEngine
from modules.engines.sweep_engine import LiquiditySweepEngine
from modules.engines.trend_engine import TrendPullbackEngine
from modules.engines.range_engine import RangeBreakoutEngine
from modules.engines.signal_arbiter import SignalArbiter

logger = logging.getLogger(__name__)


class SetupEngines:
    """
    Unified entry point delegating to 3 independent, specialized strategy engines.
    Maintains 100% backward compatibility with all existing callers and tests.
    """

    # Static utility delegates
    calculate_indicators = staticmethod(BaseSetupEngine.calculate_indicators)
    find_swings          = staticmethod(BaseSetupEngine.find_swings)
    detect_fair_value_gaps = staticmethod(BaseSetupEngine.detect_fair_value_gaps)
    calculate_adaptive_targets = staticmethod(BaseSetupEngine.calculate_adaptive_targets)

    def __init__(
        self,
        enable_sweep: bool = True,
        enable_trend: bool = True,
        enable_range: bool = True,
    ):
        self.arbiter = SignalArbiter(
            enable_sweep=enable_sweep,
            enable_trend=enable_trend,
            enable_range=enable_range,
        )
        self.sweep_engine = self.arbiter.sweep_engine
        self.trend_engine = self.arbiter.trend_engine
        self.range_engine = self.arbiter.range_engine

    def evaluate_all_setups(
        self,
        df_15m: pd.DataFrame,
        df_5m: pd.DataFrame,
        df_1m: Optional[pd.DataFrame],
        current_price: float,
        current_spread: float,
    ) -> Dict[str, Any]:
        """Runs all 3 independent engines via SignalArbiter"""
        return self.arbiter.evaluate_all(
            df_15m=df_15m,
            df_5m=df_5m,
            df_1m=df_1m,
            current_price=current_price,
            current_spread=current_spread,
        )

    # ─────────────────────────────────────────────────────────
    # Individual Engine Callers (Backward-Compatible Delegates)
    # ─────────────────────────────────────────────────────────
    def detect_liquidity_sweep_bos(
        self,
        df_15m: pd.DataFrame,
        df_5m: pd.DataFrame,
        df_1m: Optional[pd.DataFrame],
        current_price: float,
        current_spread: float,
    ) -> Dict[str, Any]:
        """Engine 1: Liquidity Sweep + BOS"""
        return self.sweep_engine.analyze(
            df_15m=df_15m,
            df_5m=df_5m,
            df_1m=df_1m,
            current_price=current_price,
            current_spread=current_spread,
        )

    def detect_trend_pullback_ema(
        self,
        df_15m: pd.DataFrame,
        df_5m: pd.DataFrame,
        df_1m: Optional[pd.DataFrame],
        current_price: float,
        current_spread: float,
    ) -> Dict[str, Any]:
        """Engine 2: Trend Pullback + EMA Retest"""
        return self.trend_engine.analyze(
            df_15m=df_15m,
            df_5m=df_5m,
            df_1m=df_1m,
            current_price=current_price,
            current_spread=current_spread,
        )

    def detect_range_breakout_retest(
        self,
        df_15m: pd.DataFrame,
        df_5m: pd.DataFrame,
        df_1m: Optional[pd.DataFrame],
        current_price: float,
        current_spread: float,
    ) -> Dict[str, Any]:
        """Engine 3: Range Breakout + Retest"""
        return self.range_engine.analyze(
            df_15m=df_15m,
            df_5m=df_5m,
            df_1m=df_1m,
            current_price=current_price,
            current_spread=current_spread,
        )
