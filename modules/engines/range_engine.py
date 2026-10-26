"""
============================================================
  modules/engines/range_engine.py
  Engine 3: Range Breakout + Retest
  Specialized for consolidation expansion & boundary retests
============================================================
"""

import logging
from typing import Dict, Any, Optional
import pandas as pd

from .base_engine import BaseSetupEngine

logger = logging.getLogger(__name__)


class RangeBreakoutEngine(BaseSetupEngine):
    """
    Engine 3: Range Breakout + Retest
    - Identifies consolidation range on M15 (min 8 bars, max $25 span).
    - Requires confirmed breakout of range high or range low.
    - Requires subsequent completed retest candle on M5 confirming rejection.
    - Tailored for high-momentum breakout moves ($3.00 - $5.00 targets).
    """

    def __init__(self, enabled: bool = True):
        super().__init__(name="Range Breakout + Retest", enabled=enabled)

    def analyze(
        self,
        df_15m: pd.DataFrame,
        df_5m: pd.DataFrame,
        df_1m: Optional[pd.DataFrame],
        current_price: float,
        current_spread: float,
    ) -> Dict[str, Any]:
        res = {"valid": False, "engine_name": self.name, "direction": "NO_TRADE"}
        if not self.enabled:
            return res

        if df_5m is None or len(df_5m) < 20 or df_15m is None or len(df_15m) < 20:
            return res

        df_15m_c = self.calculate_indicators(df_15m)
        df_5m_c  = self.calculate_indicators(df_5m)

        atr = float(df_5m_c["ATR"].iloc[-1])

        # Define consolidation range over prior 10 to 20 completed M15 bars
        lookback_bars = df_15m_c.iloc[-18:-2]
        if len(lookback_bars) < 8:
            return res

        range_high = float(lookback_bars["High"].max())
        range_low  = float(lookback_bars["Low"].min())
        range_span = range_high - range_low

        # Gold consolidation ranges typically $3.50 - $25.00
        if range_span < 3.50 or range_span > 25.0:
            return res

        last_m5 = df_5m_c.iloc[-2]
        prev_m5 = df_5m_c.iloc[-3]

        swings_15m = self.find_swings(df_15m_c, left=2, right=2)
        swings_5m  = self.find_swings(df_5m_c, left=2, right=2)
        fvgs = self.detect_fair_value_gaps(df_5m_c)

        # ── Bullish Breakout & Retest ──
        if float(prev_m5["Close"]) > range_high:
            retested = float(last_m5["Low"]) <= (range_high + 0.40) and float(last_m5["Close"]) >= (range_high - 0.20)
            if retested and float(last_m5["Close"]) >= float(last_m5["Open"]):
                entry = round(current_price, 2)
                sl_buffer = max(round(atr * 0.70, 2), 2.80)
                sl = round(range_high - sl_buffer, 2)

                tgt = self.calculate_adaptive_targets(
                    direction="BUY",
                    entry=entry,
                    sl=sl,
                    swings_m5=swings_5m,
                    swings_m15=swings_15m,
                    fvgs=fvgs,
                    atr=atr,
                    spread=current_spread,
                    min_move=2.50,
                    target_multiplier=0.85,
                )
                if tgt["valid"]:
                    return {
                        "valid": True,
                        "engine_name": self.name,
                        "direction": "BUY",
                        "entry": entry,
                        "tp": tgt["tp"],
                        "tp1": tgt["tp1"],
                        "tp2": tgt["tp2"],
                        "sl": sl,
                        "rr_tp1": tgt["rr_tp1"],
                        "rr_tp2": tgt["rr_tp2"],
                        "target_basis": tgt["target_basis"],
                        "sl_reason": f"Below retested range boundary ${range_high:.2f}",
                        "reasoning": f"Bullish breakout above M15 Range (${range_high:.2f}); retest confirmed on M5.",
                    }

        # ── Bearish Breakout & Retest ──
        if float(prev_m5["Close"]) < range_low:
            retested = float(last_m5["High"]) >= (range_low - 0.40) and float(last_m5["Close"]) <= (range_low + 0.20)
            if retested and float(last_m5["Close"]) <= float(last_m5["Open"]):
                entry = round(current_price, 2)
                sl_buffer = max(round(atr * 0.70, 2), 2.80)
                sl = round(range_low + sl_buffer, 2)

                tgt = self.calculate_adaptive_targets(
                    direction="SELL",
                    entry=entry,
                    sl=sl,
                    swings_m5=swings_5m,
                    swings_m15=swings_15m,
                    fvgs=fvgs,
                    atr=atr,
                    spread=current_spread,
                    min_move=2.50,
                    target_multiplier=0.85,
                )
                if tgt["valid"]:
                    return {
                        "valid": True,
                        "engine_name": self.name,
                        "direction": "SELL",
                        "entry": entry,
                        "tp": tgt["tp"],
                        "tp1": tgt["tp1"],
                        "tp2": tgt["tp2"],
                        "sl": sl,
                        "rr_tp1": tgt["rr_tp1"],
                        "rr_tp2": tgt["rr_tp2"],
                        "target_basis": tgt["target_basis"],
                        "sl_reason": f"Above retested range boundary ${range_low:.2f}",
                        "reasoning": f"Bearish breakout below M15 Range (${range_low:.2f}); retest confirmed on M5.",
                    }

        return res
