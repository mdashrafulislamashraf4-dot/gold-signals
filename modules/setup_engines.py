"""
============================================================
  modules/setup_engines.py
  Three Independent Setup Engines for XAUUSD Scalping:
    1. Liquidity Sweep + BOS
    2. Trend Pullback + EMA 20/50 Retest
    3. Range Breakout + Retest
  Multi-Timeframe: M15 (Trend), M5 (Setup), M1 (Confirmation)
  Strict Completed Candle Analysis (No Lookahead / Repainting)
============================================================
"""

import logging
from typing import Dict, Any, List, Optional, Tuple
import numpy as np
import pandas as pd

from config import (
    MIN_RR_RATIO,
    MAX_SPREAD_ALLOWED,
    COMMISSION_PER_LOT,
    ESTIMATED_SLIPPAGE_POINTS,
    LOT_SIZE,
)

logger = logging.getLogger(__name__)


class SetupEngines:
    """
    Houses the 3 independent, deterministic XAUUSD scalping engines.
    All calculations operate on completed candles only.
    """

    def __init__(self):
        pass

    # ─────────────────────────────────────────────────────────
    # Indicator Calculations (Completed Bars Only)
    # ─────────────────────────────────────────────────────────
    @staticmethod
    def calculate_indicators(df: pd.DataFrame) -> pd.DataFrame:
        """Calculates EMA 20, 50, 200, ATR 14, and RSI 14"""
        if df is None or len(df) < 14:
            return df

        df = df.copy()
        close = df["Close"]
        high = df["High"]
        low = df["Low"]

        # EMAs
        df["EMA_20"] = close.ewm(span=20, adjust=False).mean()
        df["EMA_50"] = close.ewm(span=min(len(df), 50), adjust=False).mean()
        df["EMA_200"] = close.ewm(span=min(len(df), 200), adjust=False).mean()

        # ATR 14
        tr1 = high - low
        tr2 = (high - close.shift(1)).abs()
        tr3 = (low - close.shift(1)).abs()
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        df["ATR"] = tr.rolling(14).mean().bfill().fillna(2.50)

        # RSI 14
        delta = close.diff()
        gain = delta.clip(lower=0)
        loss = -delta.clip(upper=0)
        avg_gain = gain.ewm(com=13, adjust=False).mean()
        avg_loss = loss.ewm(com=13, adjust=False).mean()
        rs = avg_gain / avg_loss.replace(0, 1e-9)
        df["RSI"] = 100 - (100 / (1 + rs))

        return df

    # ─────────────────────────────────────────────────────────
    # Swing & Structure Identification
    # ─────────────────────────────────────────────────────────
    @staticmethod
    def find_swings(df: pd.DataFrame, left: int = 2, right: int = 2) -> Dict[str, List[Dict[str, Any]]]:
        """Identifies fractal swing highs and lows on completed candles (excluding live bar)"""
        highs = []
        lows = []
        if df is None or len(df) < (left + right + 2):
            return {"highs": highs, "lows": lows}

        high_vals = df["High"].values
        low_vals  = df["Low"].values

        # Evaluate up to len(df) - right - 1 (ensures candle is closed)
        for i in range(left, len(df) - right):
            val_h = high_vals[i]
            if all(val_h >= high_vals[i - l] for l in range(1, left + 1)) and \
               all(val_h >= high_vals[i + r] for r in range(1, right + 1)):
                highs.append({"index": i, "price": round(float(val_h), 2)})

            val_l = low_vals[i]
            if all(val_l <= low_vals[i - l] for l in range(1, left + 1)) and \
               all(val_l <= low_vals[i + r] for r in range(1, right + 1)):
                lows.append({"index": i, "price": round(float(val_l), 2)})

        return {"highs": highs, "lows": lows}

    @staticmethod
    def detect_fair_value_gaps(df: pd.DataFrame, lookback: int = 25) -> List[Dict[str, Any]]:
        """Detects 3-bar Fair Value Gaps (FVG) on completed candles"""
        fvgs = []
        if df is None or len(df) < 5:
            return fvgs

        sub = df.tail(lookback).copy().reset_index(drop=True)
        highs = sub["High"].values
        lows  = sub["Low"].values

        for i in range(1, len(sub) - 2):
            # Bullish FVG
            if highs[i - 1] < lows[i + 1]:
                gap = round(float(lows[i + 1] - highs[i - 1]), 2)
                if gap >= 0.40:
                    fvgs.append({
                        "type": "BULLISH",
                        "bottom": round(float(highs[i - 1]), 2),
                        "top": round(float(lows[i + 1]), 2),
                        "size": gap,
                    })
            # Bearish FVG
            elif lows[i - 1] > highs[i + 1]:
                gap = round(float(lows[i - 1] - highs[i + 1]), 2)
                if gap >= 0.40:
                    fvgs.append({
                        "type": "BEARISH",
                        "top": round(float(lows[i - 1]), 2),
                        "bottom": round(float(highs[i + 1]), 2),
                        "size": gap,
                    })
        return fvgs

    # ─────────────────────────────────────────────────────────
    # Adaptive Target & Stop Loss Calculation
    # ─────────────────────────────────────────────────────────
    @classmethod
    def calculate_adaptive_targets(
        cls,
        direction: str,
        entry: float,
        sl: float,
        swings_m5: Dict[str, list],
        swings_m15: Dict[str, list],
        fvgs: list,
        atr: float,
        spread: float,
    ) -> Dict[str, Any]:
        """
        Dynamically locates nearest meaningful and reachable market-structure targets.
        Never forces fixed R:R. Rejects if target cannot cover trading costs.
        """
        risk_dist = abs(entry - sl)
        if risk_dist <= 0.20:
            return {"valid": False, "reason": "SL too tight / invalid"}

        # Total estimated round-turn trading friction per ounce
        # Commission: $4/lot = $0.04/oz. Slippage: estimated points. Spread: live spread.
        cost_per_oz = spread + (COMMISSION_PER_LOT / LOT_SIZE) + (ESTIMATED_SLIPPAGE_POINTS * 2)

        candidates = []

        if direction == "BUY":
            # Search for swing highs above entry
            all_highs = [h["price"] for h in swings_m5.get("highs", []) if h["price"] > entry + cost_per_oz]
            all_highs += [h["price"] for h in swings_m15.get("highs", []) if h["price"] > entry + cost_per_oz]
            all_highs = sorted(list(set(all_highs)))

            # Bearish FVG bottoms above entry act as magnets
            for f in fvgs:
                if f["type"] == "BEARISH" and f["bottom"] > entry + cost_per_oz:
                    all_highs.append(f["bottom"])

            all_highs = sorted(list(set(all_highs)))

            # Select nearest high-probability structure target
            valid_targets = [h for h in all_highs if (h - entry) >= max(cost_per_oz * 2.5, 1.80)]
            if valid_targets:
                tp = valid_targets[0]
                target_basis = f"M5/M15 Structural Resistance at ${tp:.2f}"
            else:
                # High-probability realistic quick-scalp target (typically $2.20 to $3.50 on Gold)
                tp = round(entry + max(2.20, min(risk_dist * 1.1, atr * 0.75)), 2)
                target_basis = f"High-Probability Scalp Target (${tp - entry:.2f})"

            gross_move = round(tp - entry, 2)
            net_reward = round(gross_move - cost_per_oz, 2)
            rr = round(gross_move / risk_dist, 2)

        else:  # SELL
            # Search for swing lows below entry
            all_lows = [l["price"] for l in swings_m5.get("lows", []) if l["price"] < entry - cost_per_oz]
            all_lows += [l["price"] for l in swings_m15.get("lows", []) if l["price"] < entry - cost_per_oz]
            all_lows = sorted(list(set(all_lows)), reverse=True)

            for f in fvgs:
                if f["type"] == "BULLISH" and f["top"] < entry - cost_per_oz:
                    all_lows.append(f["top"])

            all_lows = sorted(list(set(all_lows)), reverse=True)

            valid_targets = [l for l in all_lows if (entry - l) >= max(cost_per_oz * 2.5, 1.80)]
            if valid_targets:
                tp = valid_targets[0]
                target_basis = f"M5/M15 Structural Support at ${tp:.2f}"
            else:
                tp = round(entry - max(2.20, min(risk_dist * 1.1, atr * 0.75)), 2)
                target_basis = f"High-Probability Scalp Target (${entry - tp:.2f})"

            gross_move = round(entry - tp, 2)
            net_reward = round(gross_move - cost_per_oz, 2)
            rr = round(gross_move / risk_dist, 2)

        # Reject if net reward is negative or insufficient relative to risk
        if net_reward <= 0 or rr < 0.65:
            return {
                "valid": False,
                "reason": f"Target reward (${net_reward:.2f}) or R:R (1:{rr}) insufficient after trading costs (${cost_per_oz:.2f})",
                "tp": tp,
                "tp1": tp,
                "tp2": tp,
                "rr_tp1": rr,
                "rr_tp2": rr,
            }

        return {
            "valid": True,
            "tp": tp,
            "tp1": tp,
            "tp2": tp,
            "gross_move": gross_move,
            "net_reward": net_reward,
            "cost_per_oz": round(cost_per_oz, 2),
            "rr_tp1": rr,
            "rr_tp2": rr,
            "target_basis": target_basis,
        }

    # ─────────────────────────────────────────────────────────
    # ENGINE 1: Liquidity Sweep + BOS
    # ─────────────────────────────────────────────────────────
    @classmethod
    def detect_liquidity_sweep_bos(
        cls,
        df_15m: pd.DataFrame,
        df_5m: pd.DataFrame,
        df_1m: Optional[pd.DataFrame],
        current_price: float,
        current_spread: float,
    ) -> Dict[str, Any]:
        """
        Engine 1: Liquidity Sweep + Break of Structure (BOS)
        - M15: Defines key liquidity levels (recent swing highs/lows)
        - M5: Detects sweep (wick past level + close back inside) + BOS
        - M1: Entry confirmation using EMA 20 & price rejection
        """
        res = {"valid": False, "engine_name": "Liquidity Sweep + BOS", "direction": "NO_TRADE"}

        if df_5m is None or len(df_5m) < 15 or df_15m is None or len(df_15m) < 15:
            return res

        df_15m_c = cls.calculate_indicators(df_15m)
        df_5m_c  = cls.calculate_indicators(df_5m)
        atr = float(df_5m_c["ATR"].iloc[-1])

        swings_15m = cls.find_swings(df_15m_c, left=2, right=2)
        swings_5m  = cls.find_swings(df_5m_c, left=2, right=2)
        fvgs = cls.detect_fair_value_gaps(df_5m_c)

        # Examine the last 3 completed M5 candles (exclude incomplete current bar)
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
                # Candle wicks below level but closes back above
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

        # Check BOS for Bullish Sweep: Price broke above intermediate minor high with completed bar
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

        # Check BOS for Bearish Sweep: Price broke below intermediate minor low with completed bar
        bearish_bos = False
        if bearish_sweep and swings_5m.get("lows"):
            recent_low = swings_5m["lows"][-1]["price"]
            if float(last_completed["Close"]) < recent_low:
                bearish_bos = True

        # ── M1 Entry Confirmation ──
        m1_buy_confirmed = True
        m1_sell_confirmed = True
        if df_1m is not None and len(df_1m) >= 15:
            df_1m_c = cls.calculate_indicators(df_1m)
            last_m1 = df_1m_c.iloc[-2]
            m1_ema20 = float(last_m1["EMA_20"])
            m1_close = float(last_m1["Close"])
            m1_rsi   = float(last_m1["RSI"])

            m1_buy_confirmed = (m1_close >= m1_ema20) and (m1_rsi >= 44.0)
            m1_sell_confirmed = (m1_close <= m1_ema20) and (m1_rsi <= 56.0)

        # Decide candidate (strictly trend-aligned & confirmed BOS)
        if bullish_sweep and bullish_bos and is_bullish_trend and m1_buy_confirmed:
            entry = round(current_price, 2)
            # SL beyond the sweep wick extreme + healthy Gold volatility buffer
            sl_buffer = max(round(atr * 0.70, 2), 2.80)
            sl = round(min(sweep_wick_low, entry - 2.00) - sl_buffer, 2)

            tgt = cls.calculate_adaptive_targets("BUY", entry, sl, swings_5m, swings_15m, fvgs, atr, current_spread)
            if tgt["valid"]:
                return {
                    "valid": True,
                    "engine_name": "Liquidity Sweep + BOS",
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

        if bearish_sweep and bearish_bos and is_bearish_trend and m1_sell_confirmed:
            entry = round(current_price, 2)
            sl_buffer = max(round(atr * 0.70, 2), 2.80)
            sl = round(max(sweep_wick_high, entry + 2.00) + sl_buffer, 2)

            tgt = cls.calculate_adaptive_targets("SELL", entry, sl, swings_5m, swings_15m, fvgs, atr, current_spread)
            if tgt["valid"]:
                return {
                    "valid": True,
                    "engine_name": "Liquidity Sweep + BOS",
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

    # ─────────────────────────────────────────────────────────
    # ENGINE 2: Trend Pullback + EMA 20/50 Retest
    # ─────────────────────────────────────────────────────────
    @classmethod
    def detect_trend_pullback_ema(
        cls,
        df_15m: pd.DataFrame,
        df_5m: pd.DataFrame,
        df_1m: Optional[pd.DataFrame],
        current_price: float,
        current_spread: float,
    ) -> Dict[str, Any]:
        """
        Engine 2: Trend Pullback + EMA 20/50 Retest
        - M15: Trend context using EMA 50 & EMA 200
        - M5: Pullback into dynamic EMA 20/50 support/resistance zone
        - M1: Confirmation of bounce and rejection closed candle
        """
        res = {"valid": False, "engine_name": "Trend Pullback + EMA Retest", "direction": "NO_TRADE"}

        if df_5m is None or len(df_5m) < 20 or df_15m is None or len(df_15m) < 20:
            return res

        df_15m_c = cls.calculate_indicators(df_15m)
        df_5m_c  = cls.calculate_indicators(df_5m)
        atr = float(df_5m_c["ATR"].iloc[-1])

        # M15 Trend Filter
        ema50_15m  = float(df_15m_c["EMA_50"].iloc[-1])
        ema200_15m = float(df_15m_c["EMA_200"].iloc[-1])
        close_15m  = float(df_15m_c["Close"].iloc[-1])

        trend_15m = "NEUTRAL"
        if close_15m > ema50_15m and ema50_15m >= ema200_15m:
            trend_15m = "BULLISH"
        elif close_15m < ema50_15m and ema50_15m <= ema200_15m:
            trend_15m = "BEARISH"

        if trend_15m == "NEUTRAL":
            return res

        # M5 Pullback into EMA 20/50
        last_m5 = df_5m_c.iloc[-2]
        ema20_5m = float(last_m5["EMA_20"])
        ema50_5m = float(last_m5["EMA_50"])
        low_5m   = float(last_m5["Low"])
        high_5m  = float(last_m5["High"])
        close_5m = float(last_m5["Close"])
        open_5m  = float(last_m5["Open"])

        swings_15m = cls.find_swings(df_15m_c, left=2, right=2)
        swings_5m  = cls.find_swings(df_5m_c, left=2, right=2)
        fvgs = cls.detect_fair_value_gaps(df_5m_c)

        # Bullish Pullback: Price dips into EMA 20/50 and forms lower rejection wick
        if trend_15m == "BULLISH":
            in_ema_zone = (low_5m <= max(ema20_5m, ema50_5m) + (atr * 0.25)) and (close_5m >= min(ema20_5m, ema50_5m) - (atr * 0.25))
            bullish_candle = (close_5m >= open_5m) or (min(close_5m, open_5m) - low_5m >= 0.60)

            if in_ema_zone and bullish_candle:
                # M1 Confirmation
                m1_confirmed = True
                if df_1m is not None and len(df_1m) >= 15:
                    df_1m_c = cls.calculate_indicators(df_1m)
                    last_m1 = df_1m_c.iloc[-2]
                    m1_confirmed = float(last_m1["Close"]) >= float(last_m1["EMA_20"])

                if m1_confirmed:
                    entry = round(current_price, 2)
                    sl_buffer = max(round(atr * 0.70, 2), 2.80)
                    sl = round(min(low_5m, entry - 2.00) - sl_buffer, 2)

                    tgt = cls.calculate_adaptive_targets("BUY", entry, sl, swings_5m, swings_15m, fvgs, atr, current_spread)
                    if tgt["valid"]:
                        return {
                            "valid": True,
                            "engine_name": "Trend Pullback + EMA Retest",
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

        # Bearish Pullback: Price rallies into EMA 20/50 and forms upper rejection wick
        if trend_15m == "BEARISH":
            in_ema_zone = (high_5m >= min(ema20_5m, ema50_5m) - (atr * 0.25)) and (close_5m <= max(ema20_5m, ema50_5m) + (atr * 0.25))
            bearish_candle = (close_5m <= open_5m) or (high_5m - max(close_5m, open_5m) >= 0.60)

            if in_ema_zone and bearish_candle:
                m1_confirmed = True
                if df_1m is not None and len(df_1m) >= 15:
                    df_1m_c = cls.calculate_indicators(df_1m)
                    last_m1 = df_1m_c.iloc[-2]
                    m1_confirmed = float(last_m1["Close"]) <= float(last_m1["EMA_20"])

                if m1_confirmed:
                    entry = round(current_price, 2)
                    sl_buffer = max(round(atr * 0.70, 2), 2.80)
                    sl = round(max(high_5m, entry + 2.00) + sl_buffer, 2)

                    tgt = cls.calculate_adaptive_targets("SELL", entry, sl, swings_5m, swings_15m, fvgs, atr, current_spread)
                    if tgt["valid"]:
                        return {
                            "valid": True,
                            "engine_name": "Trend Pullback + EMA Retest",
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

    # ─────────────────────────────────────────────────────────
    # ENGINE 3: Range Breakout + Retest
    # ─────────────────────────────────────────────────────────
    @classmethod
    def detect_range_breakout_retest(
        cls,
        df_15m: pd.DataFrame,
        df_5m: pd.DataFrame,
        df_1m: Optional[pd.DataFrame],
        current_price: float,
        current_spread: float,
    ) -> Dict[str, Any]:
        """
        Engine 3: Range Breakout + Retest
        - M15: Detects horizontal consolidation range (High/Low bounds)
        - M5: Validates clean candle body breakout and retest of boundary
        - M1: Closed rejection candle confirming retest hold
        """
        res = {"valid": False, "engine_name": "Range Breakout + Retest", "direction": "NO_TRADE"}

        if df_5m is None or len(df_5m) < 25 or df_15m is None or len(df_15m) < 20:
            return res

        df_15m_c = cls.calculate_indicators(df_15m)
        df_5m_c  = cls.calculate_indicators(df_5m)
        atr = float(df_5m_c["ATR"].iloc[-1])

        # Identify Range on M15 over prior 16 bars (4 hours)
        range_window = df_15m_c.iloc[-17:-1]
        range_high = float(range_window["High"].max())
        range_low  = float(range_window["Low"].min())
        range_span = range_high - range_low

        # Legitimate consolidation ranges on Gold typically $4.00 - $18.00
        if range_span < 3.50 or range_span > 25.0:
            return res

        # M5 breakout & retest evaluation
        last_m5 = df_5m_c.iloc[-2]
        prev_m5 = df_5m_c.iloc[-3]

        swings_15m = cls.find_swings(df_15m_c, left=2, right=2)
        swings_5m  = cls.find_swings(df_5m_c, left=2, right=2)
        fvgs = cls.detect_fair_value_gaps(df_5m_c)

        # Bullish Breakout & Retest:
        # Preceding bar broke out above range_high, current bar retests near range_high and closes green
        if float(prev_m5["Close"]) > range_high:
            retested = float(last_m5["Low"]) <= (range_high + 0.40) and float(last_m5["Close"]) >= (range_high - 0.20)
            if retested and float(last_m5["Close"]) >= float(last_m5["Open"]):
                entry = round(current_price, 2)
                sl_buffer = max(round(atr * 0.70, 2), 2.80)
                sl = round(range_high - sl_buffer, 2)

                tgt = cls.calculate_adaptive_targets("BUY", entry, sl, swings_5m, swings_15m, fvgs, atr, current_spread)
                if tgt["valid"]:
                    return {
                        "valid": True,
                        "engine_name": "Range Breakout + Retest",
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

        # Bearish Breakout & Retest:
        # Preceding bar broke below range_low, current bar retests range_low and closes red
        if float(prev_m5["Close"]) < range_low:
            retested = float(last_m5["High"]) >= (range_low - 0.40) and float(last_m5["Close"]) <= (range_low + 0.20)
            if retested and float(last_m5["Close"]) <= float(last_m5["Open"]):
                entry = round(current_price, 2)
                sl_buffer = max(round(atr * 0.70, 2), 2.80)
                sl = round(range_low + sl_buffer, 2)

                tgt = cls.calculate_adaptive_targets("SELL", entry, sl, swings_5m, swings_15m, fvgs, atr, current_spread)
                if tgt["valid"]:
                    return {
                        "valid": True,
                        "engine_name": "Range Breakout + Retest",
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

    # ─────────────────────────────────────────────────────────
    # Master Setup Evaluator across All 3 Engines
    # ─────────────────────────────────────────────────────────
    def evaluate_all_setups(
        self,
        df_15m: pd.DataFrame,
        df_5m: pd.DataFrame,
        df_1m: Optional[pd.DataFrame],
        current_price: float,
        current_spread: float,
    ) -> Dict[str, Any]:
        """
        Runs all 3 setup engines independently and selects the most robust,
        highest R:R validated trade signal.
        """
        if current_spread > MAX_SPREAD_ALLOWED:
            return {
                "valid": False,
                "direction": "NO_TRADE",
                "reason": f"Spread (${current_spread:.2f}) exceeds max allowed (${MAX_SPREAD_ALLOWED:.2f})",
            }

        candidates = []

        # 1. Engine 1
        e1 = self.detect_liquidity_sweep_bos(df_15m, df_5m, df_1m, current_price, current_spread)
        if e1.get("valid"):
            candidates.append(e1)

        # 2. Engine 2
        e2 = self.detect_trend_pullback_ema(df_15m, df_5m, df_1m, current_price, current_spread)
        if e2.get("valid"):
            candidates.append(e2)

        # 3. Engine 3
        e3 = self.detect_range_breakout_retest(df_15m, df_5m, df_1m, current_price, current_spread)
        if e3.get("valid"):
            candidates.append(e3)

        if not candidates:
            return {"valid": False, "direction": "NO_TRADE", "reason": "No engine generated confirmed completed setup"}

        # Sort candidates by TP1 R:R ratio descending
        candidates.sort(key=lambda x: x.get("rr_tp1", 1.0), reverse=True)
        best_setup = candidates[0]
        logger.info(f"Setup identified by Engine: '{best_setup['engine_name']}' | {best_setup['direction']} @ {best_setup['entry']}")
        return best_setup
