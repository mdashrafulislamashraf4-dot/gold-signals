"""
============================================================
  modules/engines/sweep_engine.py
  Engine 1: Liquidity Sweep + Break of Structure (BOS)
  Specialized for rapid structural reversal scalps
============================================================
"""

import logging
from typing import Dict, Any, Optional
import pandas as pd

from .base_engine import BaseSetupEngine

logger = logging.getLogger(__name__)


class LiquiditySweepEngine(BaseSetupEngine):
    """
    Engine 1: Liquidity Sweep + BOS
    - Identifies M15/M5 key swing extremes (BSL / SSL).
    - Detects sweep on M5 (wick through level + close back inside).
    - Requires strict completed-bar BOS (price closes beyond intermediate swing).
    - Aligned with M15 HTF trend direction.
    - Tailored for high-winrate quick scalps ($2.00 - $3.00 targets).
    """

    def __init__(self, enabled: bool = True):
        super().__init__(name="Liquidity Sweep + BOS", enabled=enabled)

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

        if df_5m is None or len(df_5m) < 15 or df_15m is None or len(df_15m) < 15:
            return res

        df_15m_c = self.calculate_indicators(df_15m)
        df_5m_c  = self.calculate_indicators(df_5m)
        atr = float(df_5m_c["ATR"].iloc[-1])

        swings_15m = self.find_swings(df_15m_c, left=2, right=2)
        swings_5m  = self.find_swings(df_5m_c, left=2, right=2)
        fvgs = self.detect_fair_value_gaps(df_5m_c)

        completed_bars = df_5m_c.iloc[-4:-1]
        last_completed = df_5m_c.iloc[-2]

        # ── Check Bullish Sweep (Sell-side liquidity grabbed) ──
        recent_lows = [l["price"] for l in swings_15m.get("lows", [])[-4:]] + \
                      [l["price"] for l in swings_5m.get("lows", [])[-4:]]
        recent_lows = sorted(list(set(recent_lows)))

        bullish_sweep = False
        swept_low = None
        sweep_wick_low = None

        for lvl in recent_lows:
            for _, bar in completed_bars.iterrows():
                if float(bar["Low"]) < lvl and float(bar["Close"]) > lvl:
                    bullish_sweep = True
                    swept_low = lvl
                    sweep_wick_low = float(bar["Low"])
                    break
            if bullish_sweep:
                break

        # ── M15 Trend Direction Context ──
        m15_close = float(df_15m_c["Close"].iloc[-2])
        m15_ema50 = float(df_15m_c["EMA_50"].iloc[-2]) if "EMA_50" in df_15m_c.columns else m15_close
        is_bullish_trend = m15_close >= (m15_ema50 - 0.80)
        is_bearish_trend = m15_close <= (m15_ema50 + 0.80)

        # Strict BOS for Bullish Sweep: Price closed above intermediate minor high
        bullish_bos = False
        if bullish_sweep and swings_5m.get("highs"):
            recent_high = swings_5m["highs"][-1]["price"]
            if float(last_completed["Close"]) > recent_high:
                bullish_bos = True

        # ── Check Bearish Sweep (Buy-side liquidity grabbed) ──
        recent_highs = [h["price"] for h in swings_15m.get("highs", [])[-4:]] + \
                       [h["price"] for h in swings_5m.get("highs", [])[-4:]]
        recent_highs = sorted(list(set(recent_highs)))

        bearish_sweep = False
        swept_high = None
        sweep_wick_high = None

        for lvl in recent_highs:
            for _, bar in completed_bars.iterrows():
                if float(bar["High"]) > lvl and float(bar["Close"]) < lvl:
                    bearish_sweep = True
                    swept_high = lvl
                    sweep_wick_high = float(bar["High"])
                    break
            if bearish_sweep:
                break

        # Strict BOS for Bearish Sweep: Price closed below intermediate minor low
        bearish_bos = False
        if bearish_sweep and swings_5m.get("lows"):
            recent_low = swings_5m["lows"][-1]["price"]
            if float(last_completed["Close"]) < recent_low:
                bearish_bos = True

        # ── M1 Entry Confirmation ──
        m1_buy_confirmed = True
        m1_sell_confirmed = True
        if df_1m is not None and len(df_1m) >= 15:
            df_1m_c = self.calculate_indicators(df_1m)
            last_m1 = df_1m_c.iloc[-2]
            m1_ema20 = float(last_m1["EMA_20"])
            m1_close = float(last_m1["Close"])
            m1_rsi   = float(last_m1["RSI"])

            m1_buy_confirmed = (m1_close >= m1_ema20) and (m1_rsi >= 44.0)
            m1_sell_confirmed = (m1_close <= m1_ema20) and (m1_rsi <= 56.0)

        # ── BUY Setup Evaluation ──
        if bullish_sweep and bullish_bos and is_bullish_trend and m1_buy_confirmed:
            entry = round(current_price, 2)
            sl_buffer = max(round(atr * 0.70, 2), 2.80)
            sl = round(min(sweep_wick_low, entry - 2.00) - sl_buffer, 2)

            tgt = self.calculate_adaptive_targets(
                direction="BUY",
                entry=entry,
                sl=sl,
                swings_m5=swings_5m,
                swings_m15=swings_15m,
                fvgs=fvgs,
                atr=atr,
                spread=current_spread,
                min_move=2.00,
                target_multiplier=0.70,
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
                    "sl_reason": f"Below sweep low ${swept_low} with ${sl_buffer} buffer",
                    "reasoning": f"Swept SSL at ${swept_low:.2f}, BOS confirmed on M5, M1 aligned.",
                }

        # ── SELL Setup Evaluation ──
        if bearish_sweep and bearish_bos and is_bearish_trend and m1_sell_confirmed:
            entry = round(current_price, 2)
            sl_buffer = max(round(atr * 0.70, 2), 2.80)
            sl = round(max(sweep_wick_high, entry + 2.00) + sl_buffer, 2)

            tgt = self.calculate_adaptive_targets(
                direction="SELL",
                entry=entry,
                sl=sl,
                swings_m5=swings_5m,
                swings_m15=swings_15m,
                fvgs=fvgs,
                atr=atr,
                spread=current_spread,
                min_move=2.00,
                target_multiplier=0.70,
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
                    "sl_reason": f"Above sweep high ${swept_high} with ${sl_buffer} buffer",
                    "reasoning": f"Swept BSL at ${swept_high:.2f}, BOS confirmed on M5, M1 aligned.",
                }

        return res
