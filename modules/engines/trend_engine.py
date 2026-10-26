"""
============================================================
  modules/engines/trend_engine.py
  Engine 2: Trend Pullback + EMA 20/50 Retest
  Specialized for trend continuation & momentum expansion
============================================================
"""

import logging
from typing import Dict, Any, Optional
import pandas as pd

from .base_engine import BaseSetupEngine

logger = logging.getLogger(__name__)


class TrendPullbackEngine(BaseSetupEngine):
    """
    Engine 2: Trend Pullback + EMA 20/50 Retest
    - Follows M15 dominant trend (EMA 50 & structure).
    - Detects shallow pullback on M5 into EMA 20 / EMA 50 dynamic zone.
    - Confirms rejection wick on completed bar.
    - Confirms with closed-bar M1 alignment (EMA 20 & RSI).
    - Tailored for high R:R trend moves ($3.00 - $4.50 targets).
    """

    def __init__(self, enabled: bool = True):
        super().__init__(name="Trend Pullback + EMA Retest", enabled=enabled)

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
        swings_15m = self.find_swings(df_15m_c, left=2, right=2)
        swings_5m  = self.find_swings(df_5m_c, left=2, right=2)
        fvgs = self.detect_fair_value_gaps(df_5m_c)

        # M15 Trend Direction
        last_m15 = df_15m_c.iloc[-2]
        close_15m = float(last_m15["Close"])
        ema50_15m = float(last_m15["EMA_50"])

        trend_15m = "BULLISH" if close_15m > ema50_15m else "BEARISH"

        # M5 Pullback Candle (last completed bar)
        last_m5  = df_5m_c.iloc[-2]
        ema20_5m = float(last_m5["EMA_20"])
        ema50_5m = float(last_m5["EMA_50"])
        high_5m  = float(last_m5["High"])
        low_5m   = float(last_m5["Low"])
        close_5m = float(last_m5["Close"])
        open_5m  = float(last_m5["Open"])

        # ── Bullish Pullback Evaluation ──
        if trend_15m == "BULLISH":
            # Price dips into EMA 20/50 zone
            in_ema_zone = (low_5m <= max(ema20_5m, ema50_5m) + (atr * 0.25)) and (close_5m >= min(ema20_5m, ema50_5m) - (atr * 0.25))
            bullish_candle = (close_5m >= open_5m) or (min(close_5m, open_5m) - low_5m >= 0.60)

            if in_ema_zone and bullish_candle:
                # M1 Confirmation
                m1_confirmed = True
                if df_1m is not None and len(df_1m) >= 15:
                    df_1m_c = self.calculate_indicators(df_1m)
                    last_m1 = df_1m_c.iloc[-2]
                    m1_confirmed = float(last_m1["Close"]) >= float(last_m1["EMA_20"]) and float(last_m1["RSI"]) >= 45.0

                if m1_confirmed:
                    entry = round(current_price, 2)
                    sl_buffer = max(round(atr * 0.70, 2), 2.80)
                    sl = round(min(low_5m, entry - 2.00) - sl_buffer, 2)

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
                            "sl_reason": f"Below M5 pullback low ${low_5m:.2f} + buffer",
                            "reasoning": "M15 Bullish trend; M5 pullback retested EMA 20/50 zone with wick rejection.",
                        }

        # ── Bearish Pullback Evaluation ──
        if trend_15m == "BEARISH":
            # Price rallies into EMA 20/50 zone
            in_ema_zone = (high_5m >= min(ema20_5m, ema50_5m) - (atr * 0.25)) and (close_5m <= max(ema20_5m, ema50_5m) + (atr * 0.25))
            bearish_candle = (close_5m <= open_5m) or (high_5m - max(close_5m, open_5m) >= 0.60)

            if in_ema_zone and bearish_candle:
                m1_confirmed = True
                if df_1m is not None and len(df_1m) >= 15:
                    df_1m_c = self.calculate_indicators(df_1m)
                    last_m1 = df_1m_c.iloc[-2]
                    m1_confirmed = float(last_m1["Close"]) <= float(last_m1["EMA_20"]) and float(last_m1["RSI"]) <= 55.0

                if m1_confirmed:
                    entry = round(current_price, 2)
                    sl_buffer = max(round(atr * 0.70, 2), 2.80)
                    sl = round(max(high_5m, entry + 2.00) + sl_buffer, 2)

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
                            "sl_reason": f"Above M5 pullback high ${high_5m:.2f} + buffer",
                            "reasoning": "M15 Bearish trend; M5 rally retested EMA 20/50 zone with upper rejection.",
                        }

        return res
