"""
============================================================
  modules/engines/signal_arbiter.py
  Master Multi-Strategy Coordinator (Signal Arbiter)
  Coordinates 3 Independent Engines with Individual Toggles
============================================================
"""

import logging
from typing import Dict, Any, List, Optional
import pandas as pd

from config import MAX_SPREAD_ALLOWED
from .sweep_engine import LiquiditySweepEngine
from .trend_engine import TrendPullbackEngine
from .range_engine import RangeBreakoutEngine

logger = logging.getLogger(__name__)


class SignalArbiter:
    """
    Coordinates 3 independent, decoupled scalping engines:
      1. LiquiditySweepEngine   (Sweep + BOS)
      2. TrendPullbackEngine    (Trend Pullback + EMA Retest)
      3. RangeBreakoutEngine    (Range Breakout + Retest)
    Enforces single-position execution discipline, prevents duplicate conflicts,
    and supports independent runtime enabling/disabling of engines.
    """

    def __init__(
        self,
        enable_sweep: bool = True,
        enable_trend: bool = True,
        enable_range: bool = True,
    ):
        self.sweep_engine = LiquiditySweepEngine(enabled=enable_sweep)
        self.trend_engine = TrendPullbackEngine(enabled=enable_trend)
        self.range_engine = RangeBreakoutEngine(enabled=enable_range)

        self.engines = [self.sweep_engine, self.trend_engine, self.range_engine]

    def evaluate_all(
        self,
        df_15m: pd.DataFrame,
        df_5m: pd.DataFrame,
        df_1m: Optional[pd.DataFrame],
        current_price: float,
        current_spread: float,
    ) -> Dict[str, Any]:
        """
        Runs all enabled engines independently and selects the most robust,
        highest R:R validated trade signal.
        """
        if current_spread > MAX_SPREAD_ALLOWED:
            return {
                "valid": False,
                "direction": "NO_TRADE",
                "reason": f"Spread (${current_spread:.2f}) exceeds max allowed (${MAX_SPREAD_ALLOWED:.2f})",
            }

        candidates = []

        # Run each enabled engine completely independently
        for engine in self.engines:
            if not engine.enabled:
                continue
            try:
                res = engine.analyze(
                    df_15m=df_15m,
                    df_5m=df_5m,
                    df_1m=df_1m,
                    current_price=current_price,
                    current_spread=current_spread,
                )
                if res.get("valid") and res.get("direction") in ("BUY", "SELL"):
                    candidates.append(res)
            except Exception as e:
                logger.error(f"Error in engine '{engine.name}': {e}")

        if not candidates:
            return {
                "valid": False,
                "direction": "NO_TRADE",
                "reason": "No engine generated confirmed completed setup",
            }

        # Sort candidates by R:R ratio descending
        candidates.sort(key=lambda x: x.get("rr_tp1", 1.0), reverse=True)
        best_setup = candidates[0]

        logger.info(
            f"Validated Setup Selected from '{best_setup['engine_name']}': "
            f"{best_setup['direction']} @ {best_setup['entry']} | TP: {best_setup.get('tp')} | SL: {best_setup.get('sl')}"
        )
        return best_setup

    def get_status(self) -> Dict[str, bool]:
        """Returns enabled state of all engines"""
        return {e.name: e.enabled for e in self.engines}

    def set_engine_state(self, engine_name: str, enabled: bool) -> bool:
        """Enables or disables an individual engine at runtime"""
        for e in self.engines:
            if e.name.lower() == engine_name.lower():
                e.enabled = enabled
                logger.info(f"Engine '{e.name}' set to {'ENABLED' if enabled else 'DISABLED'}")
                return True
        return False
