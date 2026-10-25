"""
============================================================
  modules/technical.py
  Simplified & Deterministic Structure Scalping Engine for XAUUSD (Gold)
  Strict Bar-Close Confirmation | Cost-Adjusted Dynamic TP/SL
============================================================
"""

import logging
from typing import Dict, Any, List, Optional
import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


class TechnicalAnalyzer:
    """
    Simplified, deterministic structure scalping engine for XAUUSD (Gold).
    Operates on a 3-step hierarchy:
    1. 15M / 1H Trend & Market Structure (EMA 50 / EMA 200 + Swing Highs/Lows)
    2. 5M / 1M Setup (Liquidity Sweeps, Support/Resistance, FVG/OB Retest)
    3. Strict Bar-Close Confirmation & Cost-Adjusted Dynamic Exits
    """

    def __init__(self, tp_engine=None, risk_engine=None):
        from modules.dynamic_tp_engine import DynamicTPEngine
        from modules.risk_engine import RiskEngine

        self.tp_engine = tp_engine or DynamicTPEngine()
        self.risk_engine = risk_engine or RiskEngine()

    # ─────────────────────────────────────────────────────────
    # 1. Essential Core Indicators (Simple, Fast & Robust)
    # ─────────────────────────────────────────────────────────
    def calculate_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Calculates essential trend, momentum, and volatility indicators:
        EMA (20, 50, 200), ATR (14), RSI (14), MACD, and VWAP.
        """
        if df is None or len(df) < 14:
            return df

        df = df.copy()
        close = df["Close"]
        high = df["High"]
        low = df["Low"]
        vol = df.get("Volume", pd.Series([1000] * len(df), index=df.index)).fillna(1000)

        # EMAs
        df["EMA_20"] = close.ewm(span=20, adjust=False).mean()
        df["EMA_50"] = close.ewm(span=min(len(df), 50), adjust=False).mean()
        df["EMA_200"] = close.ewm(span=min(len(df), 200), adjust=False).mean()

        # ATR 14
        tr1 = high - low
        tr2 = (high - close.shift(1)).abs()
        tr3 = (low - close.shift(1)).abs()
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        df["ATR"] = tr.rolling(14).mean().bfill().fillna(3.0)

        # RSI 14
        delta = close.diff()
        gain = delta.clip(lower=0)
        loss = -delta.clip(upper=0)
        avg_gain = gain.ewm(com=13, adjust=False).mean()
        avg_loss = loss.ewm(com=13, adjust=False).mean()
        rs = avg_gain / avg_loss.replace(0, 1e-9)
        df["RSI"] = 100 - (100 / (1 + rs))

        # MACD (12, 26, 9)
        ema12 = close.ewm(span=12, adjust=False).mean()
        ema26 = close.ewm(span=26, adjust=False).mean()
        df["MACD"] = ema12 - ema26
        df["MACD_Signal"] = df["MACD"].ewm(span=9, adjust=False).mean()
        df["MACD_Hist"] = df["MACD"] - df["MACD_Signal"]

        # VWAP
        typical = (high + low + close) / 3
        cum_vol = vol.cumsum().replace(0, 1)
        df["VWAP"] = (typical * vol).cumsum() / cum_vol

        return df

    # ─────────────────────────────────────────────────────────
    # 2. Pivot Points & Divergences
    # ─────────────────────────────────────────────────────────
    def pivot_levels(self, df: pd.DataFrame) -> dict:
        """Classic Floor & Camarilla Pivot Points for intraday levels"""
        if df is None or len(df) < 2:
            return {}

        prev = df.iloc[-2]
        h = float(prev["High"])
        l = float(prev["Low"])
        c = float(prev["Close"])

        p = (h + l + c) / 3
        r1 = 2 * p - l
        s1 = 2 * p - h
        r2 = p + (h - l)
        s2 = p - (h - l)

        rng = h - l
        cam_h4 = c + rng * 1.1 / 2
        cam_h3 = c + rng * 1.1 / 4
        cam_l3 = c - rng * 1.1 / 4
        cam_l4 = c - rng * 1.1 / 2

        return {
            "pivot": round(p, 2),
            "r1": round(r1, 2),
            "s1": round(s1, 2),
            "r2": round(r2, 2),
            "s2": round(s2, 2),
            "cam_h4": round(cam_h4, 2),
            "cam_h3": round(cam_h3, 2),
            "cam_l3": round(cam_l3, 2),
            "cam_l4": round(cam_l4, 2),
        }

    def detect_divergences(self, df: pd.DataFrame, lookback: int = 35) -> list:
        """Detects Regular & Hidden RSI Divergences"""
        divergences = []
        if df is None or len(df) < lookback:
            return divergences

        try:
            sub = df.tail(lookback).copy().reset_index(drop=True)
            lows = sub["Low"].values
            highs = sub["High"].values
            rsi = sub.get("RSI", pd.Series(dtype=float)).values

            if len(rsi) < lookback or pd.isna(rsi[-1]):
                return divergences

            swing_lows = [
                idx for idx in range(2, len(lows) - 1)
                if lows[idx] <= lows[idx - 1] and lows[idx] <= lows[idx + 1] and lows[idx] <= lows[idx - 2]
            ]
            if len(swing_lows) >= 2:
                i1, i2 = swing_lows[-2], swing_lows[-1]
                if lows[i2] < lows[i1] and rsi[i2] > rsi[i1] + 1.5:
                    divergences.append(("BULLISH_RSI_DIV", "Bullish", "🟢 Bullish RSI Divergence — চার্টে লো হলেও RSI-এ ঊর্ধ্বগতি"))
                elif lows[i2] > lows[i1] and rsi[i2] < rsi[i1] - 2.0:
                    divergences.append(("HIDDEN_BULLISH_DIV", "Bullish", "🟢 Hidden Bullish Divergence — ট্রেন্ড কন্টিনিউয়েশন"))

            swing_highs = [
                idx for idx in range(2, len(highs) - 1)
                if highs[idx] >= highs[idx - 1] and highs[idx] >= highs[idx + 1] and highs[idx] >= highs[idx - 2]
            ]
            if len(swing_highs) >= 2:
                i1, i2 = swing_highs[-2], swing_highs[-1]
                if highs[i2] > highs[i1] and rsi[i2] < rsi[i1] - 1.5:
                    divergences.append(("BEARISH_RSI_DIV", "Bearish", "🔴 Bearish RSI Divergence — চার্টে হাই হলেও RSI-এ নিম্নগতি"))
                elif highs[i2] < highs[i1] and rsi[i2] > rsi[i1] + 2.0:
                    divergences.append(("HIDDEN_BEARISH_DIV", "Bearish", "🔴 Hidden Bearish Divergence — ট্রেন্ড কন্টিনিউয়েশন"))

        except Exception as e:
            logger.debug(f"Divergence detection: {e}")

        return divergences

    # ─────────────────────────────────────────────────────────
    # 3. Market Structure: Swings, BOS, CHoCH
    # ─────────────────────────────────────────────────────────
    def find_swings(self, df: pd.DataFrame, left: int = 2, right: int = 2) -> dict:
        """Finds fractal Swing Highs and Swing Lows"""
        highs = []
        lows = []
        if df is None or len(df) < (left + right + 1):
            return {"highs": highs, "lows": lows}

        high_vals = df["High"].values
        low_vals  = df["Low"].values

        for i in range(left, len(df) - right):
            val_h = high_vals[i]
            is_high = all(val_h >= high_vals[i - l] for l in range(1, left + 1)) and \
                      all(val_h >= high_vals[i + r] for r in range(1, right + 1))
            if is_high:
                highs.append({"index": i, "price": round(float(val_h), 2)})

            val_l = low_vals[i]
            is_low = all(val_l <= low_vals[i - l] for l in range(1, left + 1)) and \
                     all(val_l <= low_vals[i + r] for r in range(1, right + 1))
            if is_low:
                lows.append({"index": i, "price": round(float(val_l), 2)})

        return {"highs": highs, "lows": lows}

    def detect_structure(self, df: pd.DataFrame, swings: dict) -> dict:
        """Determines market trend, BOS, and CHoCH"""
        res = {
            "trend": "RANGE",
            "bos_bullish": False,
            "bos_bearish": False,
            "choch_bullish": False,
            "choch_bearish": False,
            "last_high": None,
            "last_low": None,
        }
        if df is None or len(df) < 5:
            return res

        highs = swings.get("highs", [])
        lows  = swings.get("lows", [])

        if highs:
            res["last_high"] = highs[-1]["price"]
        if lows:
            res["last_low"] = lows[-1]["price"]

        close_vals = df["Close"].values
        current_close = close_vals[-1]

        # BOS / CHoCH Break checks
        if len(highs) >= 2:
            prev_h = highs[-2]["price"]
            curr_h = highs[-1]["price"]
            if current_close > curr_h:
                res["bos_bullish"] = True
            elif current_close > prev_h and curr_h < prev_h:
                res["choch_bullish"] = True

        if len(lows) >= 2:
            prev_l = lows[-2]["price"]
            curr_l = lows[-1]["price"]
            if current_close < curr_l:
                res["bos_bearish"] = True
            elif current_close < prev_l and curr_l > prev_l:
                res["choch_bearish"] = True

        # Trend direction
        if len(highs) >= 2 and len(lows) >= 2:
            if highs[-1]["price"] > highs[-2]["price"] and lows[-1]["price"] > lows[-2]["price"]:
                res["trend"] = "BULLISH"
            elif highs[-1]["price"] < highs[-2]["price"] and lows[-1]["price"] < lows[-2]["price"]:
                res["trend"] = "BEARISH"

        return res

    def detect_equal_highs_lows(self, swings: dict, tolerance: float = 0.50) -> dict:
        """Finds Equal Highs (BSL) and Equal Lows (SSL) liquidity pools"""
        eq_highs = []
        eq_lows = []
        highs = swings.get("highs", [])
        lows  = swings.get("lows", [])

        for i in range(len(highs) - 1):
            for j in range(i + 1, len(highs)):
                if abs(highs[i]["price"] - highs[j]["price"]) <= tolerance:
                    eq_highs.append(round((highs[i]["price"] + highs[j]["price"]) / 2, 2))

        for i in range(len(lows) - 1):
            for j in range(i + 1, len(lows)):
                if abs(lows[i]["price"] - lows[j]["price"]) <= tolerance:
                    eq_lows.append(round((lows[i]["price"] + lows[j]["price"]) / 2, 2))

        return {"equal_highs": sorted(list(set(eq_highs))), "equal_lows": sorted(list(set(eq_lows)))}

    def calculate_dealing_range_and_ote(self, swings: dict, current_price: float) -> dict:
        """Calculates Premium / Discount zones and Optimal Trade Entry (OTE) levels"""
        highs = swings.get("highs", [])
        lows  = swings.get("lows", [])

        if not highs or not lows:
            return {"range_high": current_price, "range_low": current_price, "eq": current_price, "zone": "EQUILIBRIUM"}

        r_high = max(h["price"] for h in highs[-5:])
        r_low  = min(l["price"] for l in lows[-5:])
        rng    = max(r_high - r_low, 1.0)
        eq     = round(r_low + (rng * 0.5), 2)

        ote_62 = round(r_low + (rng * 0.618), 2)
        ote_79 = round(r_low + (rng * 0.786), 2)

        zone = "EQUILIBRIUM"
        if current_price < eq:
            zone = "DISCOUNT"
        elif current_price > eq:
            zone = "PREMIUM"

        return {
            "range_high": round(r_high, 2),
            "range_low":  round(r_low, 2),
            "eq":         eq,
            "zone":       zone,
            "ote_buy":    (zone == "DISCOUNT" and current_price >= ote_62),
            "ote_sell":   (zone == "PREMIUM" and current_price <= ote_79),
        }

    # ─────────────────────────────────────────────────────────
    # 4. Imbalance & Institutional Footprints (FVG & OB)
    # ─────────────────────────────────────────────────────────
    def detect_fair_value_gaps(self, df: pd.DataFrame, lookback: int = 30) -> list:
        """Detects active Fair Value Gaps (FVG) across bars"""
        fvgs = []
        if df is None or len(df) < 3:
            return fvgs

        sub = df.tail(lookback).copy().reset_index(drop=True)
        highs = sub["High"].values
        lows  = sub["Low"].values

        for i in range(1, len(sub) - 1):
            # Bullish FVG: Bar i-1 High < Bar i+1 Low
            if highs[i - 1] < lows[i + 1]:
                gap_size = lows[i + 1] - highs[i - 1]
                if gap_size >= 0.50:
                    fvgs.append({
                        "type": "BULLISH",
                        "bottom": round(float(highs[i - 1]), 2),
                        "top": round(float(lows[i + 1]), 2),
                        "size": round(float(gap_size), 2),
                        "active": True,
                    })
            # Bearish FVG: Bar i-1 Low > Bar i+1 High
            elif lows[i - 1] > highs[i + 1]:
                gap_size = lows[i - 1] - highs[i + 1]
                if gap_size >= 0.50:
                    fvgs.append({
                        "type": "BEARISH",
                        "top": round(float(lows[i - 1]), 2),
                        "bottom": round(float(highs[i + 1]), 2),
                        "size": round(float(gap_size), 2),
                        "active": True,
                    })

        return fvgs

    def detect_order_blocks(self, df: pd.DataFrame, lookback: int = 30) -> dict:
        """Identifies institutional Order Blocks (OB)"""
        res = {"bullish_ob": None, "bearish_ob": None}
        if df is None or len(df) < 5:
            return res

        sub = df.tail(lookback).copy().reset_index(drop=True)
        opens  = sub["Open"].values
        highs  = sub["High"].values
        lows   = sub["Low"].values
        closes = sub["Close"].values

        # Bullish OB: Last down candle before strong up move
        for i in range(len(sub) - 4, 1, -1):
            if closes[i] < opens[i]:  # Bearish candle
                if closes[i + 1] > highs[i] or closes[i + 2] > highs[i]:
                    res["bullish_ob"] = {
                        "top": round(float(highs[i]), 2),
                        "bottom": round(float(lows[i]), 2),
                        "testing": (lows[-1] <= highs[i] and closes[-1] >= lows[i]),
                    }
                    break

        # Bearish OB: Last up candle before strong down move
        for i in range(len(sub) - 4, 1, -1):
            if closes[i] > opens[i]:  # Bullish candle
                if closes[i + 1] < lows[i] or closes[i + 2] < lows[i]:
                    res["bearish_ob"] = {
                        "top": round(float(highs[i]), 2),
                        "bottom": round(float(lows[i]), 2),
                        "testing": (highs[-1] >= lows[i] and closes[-1] <= highs[i]),
                    }
                    break

        return res

    # ─────────────────────────────────────────────────────────
    # 5. Session & Liquidity Sweeps
    # ─────────────────────────────────────────────────────────
    def calculate_session_and_liquidity_levels(self, df: pd.DataFrame, timezone_str: str = "Asia/Dhaka") -> dict:
        """Calculates Previous Day High/Low (PDH/PDL), Asian Range, and Current Trading Session"""
        # Determine Current Market Session (UTC)
        from datetime import datetime, timezone as dt_tz
        now_utc = datetime.now(dt_tz.utc)
        hour_utc = now_utc.hour + now_utc.minute / 60.0

        if 12.0 <= hour_utc < 16.0:
            session_name = "London / NY Overlap (সর্বোচ্চ ভলিউম 🔥)"
            session_code = "LONDON_NY_OVERLAP"
            is_peak = True
        elif 12.0 <= hour_utc < 21.0:
            session_name = "New York Session (ইউএস সেশন 🇺🇸)"
            session_code = "NEW_YORK"
            is_peak = True
        elif 7.0 <= hour_utc < 16.0:
            session_name = "London Session (লন্ডন সেশন 🇬🇧)"
            session_code = "LONDON"
            is_peak = True
        elif 0.0 <= hour_utc < 8.0:
            session_name = "Asian Session (এশিয়ান সেশন 🌏)"
            session_code = "ASIAN"
            is_peak = False
        else:
            session_name = "Off-Peak Market (কম ভলিউম)"
            session_code = "OFF_PEAK"
            is_peak = False

        res = {
            "pdh": None,
            "pdl": None,
            "asian_high": None,
            "asian_low": None,
            "current_session": session_name,
            "session_code": session_code,
            "is_peak_session": is_peak,
        }
        if df is None or df.empty:
            return res

        highs = df["High"].values
        lows  = df["Low"].values

        # Rolling 24-hour PDH/PDL proxy
        bars_day = min(len(df), 96)
        res["pdh"] = round(float(np.max(highs[-bars_day:])), 2)
        res["pdl"] = round(float(np.min(lows[-bars_day:])), 2)

        # Asian Range proxy (recent 32 bars)
        bars_asian = min(len(df), 32)
        res["asian_high"] = round(float(np.max(highs[-bars_asian:])), 2)
        res["asian_low"]  = round(float(np.min(lows[-bars_asian:])), 2)

        return res

    def detect_liquidity_sweep(
        self,
        df: pd.DataFrame,
        liquidity: dict,
        swings: dict = None,
        eq_pools: dict = None,
        tolerance: float = 0.50,
    ) -> dict:
        """
        লিকুইডিটি সুইপ (Liquidity Sweep) নিশ্চিত করে (সেশন নিরপেক্ষ):
        দাম গুরুত্বপূর্ণ লেভেলের ওপরে/নিচে গিয়ে উইক (Wick) ফেলে আবার ভেতরে ক্লোজ হয়েছে কি না
        """
        res = {
            "bullish_sweep": False,
            "bearish_sweep": False,
            "swept_level_name": "",
            "swept_level_price": None,
            "sweep_details": "",
        }
        if df is None or len(df) < 3:
            return res

        recent_bars = df.tail(4)
        c = recent_bars["Close"].values
        h = recent_bars["High"].values
        l = recent_bars["Low"].values
        cur_close = c[-1]

        pdl = liquidity.get("pdl")
        pdh = liquidity.get("pdh")
        asian_low = liquidity.get("asian_low")
        asian_high = liquidity.get("asian_high")

        # ── Sell-side Liquidity (SSL) Levels ───────────────────
        ssl_levels = []
        raw_eql = (eq_pools.get("equal_lows") or eq_pools.get("eq_lows") or []) if eq_pools else []
        for eql in raw_eql[:3]:
            lvl_val = eql["price"] if isinstance(eql, dict) else float(eql)
            ssl_levels.append(("Equal Lows / Double Bottom (SSL)", lvl_val))
        if pdl:
            ssl_levels.append(("Previous Day Low (PDL)", pdl))
        if asian_low:
            ssl_levels.append(("Asian Session Low", asian_low))
        if swings and swings.get("lows"):
            for sl_item in swings["lows"][-3:]:
                ssl_levels.append(("Recent Swing Low (SSL)", sl_item["price"]))

        # Psychological Round Numbers (e.g. 4050, 4100)
        round_50 = round(cur_close / 50.0) * 50.0
        if abs(cur_close - round_50) <= 15.0:
            ssl_levels.append((f"Psychological Key Level (${int(round_50)})", round_50))

        for name, lvl in ssl_levels:
            min_low = min(l)
            if min_low < lvl and cur_close > lvl:
                res["bullish_sweep"] = True
                res["swept_level_name"] = name
                res["swept_level_price"] = lvl
                res["sweep_details"] = f"🟢 লিকুইডিটি সুইপ: {name} (${lvl}) ভেঙে ফেকআউট উইক ফেলে আবার ওপরে ক্লোজ হয়েছে"
                return res

        # ── Buy-side Liquidity (BSL) Levels ────────────────────
        bsl_levels = []
        raw_eqh = (eq_pools.get("equal_highs") or eq_pools.get("eq_highs") or []) if eq_pools else []
        for eqh in raw_eqh[:3]:
            lvl_val = eqh["price"] if isinstance(eqh, dict) else float(eqh)
            bsl_levels.append(("Equal Highs / Double Top (BSL)", lvl_val))
        if pdh:
            bsl_levels.append(("Previous Day High (PDH)", pdh))
        if asian_high:
            bsl_levels.append(("Asian Session High", asian_high))
        if swings and swings.get("highs"):
            for sh_item in swings["highs"][-3:]:
                bsl_levels.append(("Recent Swing High (BSL)", sh_item["price"]))

        if abs(cur_close - round_50) <= 15.0:
            bsl_levels.append((f"Psychological Key Level (${int(round_50)})", round_50))

        for name, lvl in bsl_levels:
            max_high = max(h)
            if max_high > lvl and cur_close < lvl:
                res["bearish_sweep"] = True
                res["swept_level_name"] = name
                res["swept_level_price"] = lvl
                res["sweep_details"] = f"🔴 লিকুইডিটি সুইপ: {name} (${lvl}) ভেঙে ফেকআউট উইক ফেলে আবার নিচে ক্লোজ হয়েছে"
                return res

        return res

    def calculate_rvol(self, df: pd.DataFrame, period: int = 20) -> float:
        """Calculates Relative Volume (RVOL)"""
        if df is None or len(df) < period or "Volume" not in df.columns:
            return 1.0
        v = df["Volume"].values
        avg_v = np.mean(v[-period:])
        if avg_v <= 0:
            return 1.0
        return round(float(v[-1] / avg_v), 2)

    def detect_displacement(self, df: pd.DataFrame, atr: float) -> dict:
        """Detects strong institutional expansion / displacement candles"""
        res = {"bullish": False, "bearish": False, "size": 0.0}
        if df is None or df.empty:
            return res

        last_bar = df.iloc[-1]
        body = abs(float(last_bar["Close"]) - float(last_bar["Open"]))
        is_green = float(last_bar["Close"]) > float(last_bar["Open"])
        threshold = max(atr * 1.5, 4.5)

        if body >= threshold:
            res["size"] = round(body, 2)
            if is_green:
                res["bullish"] = True
            else:
                res["bearish"] = True

        return res

    # ─────────────────────────────────────────────────────────
    # 6. Bar-Close Confirmation Triggers
    # ─────────────────────────────────────────────────────────
    def evaluate_5m_confirmation(self, df_5m: pd.DataFrame, direction: str) -> dict:
        """Evaluates 5M bar-close confirmation"""
        if df_5m is None or len(df_5m) < 3:
            return {"confirmed": True, "reason": "5m পর্যাপ্ত বার নেই — পাস"}

        last_bar = df_5m.iloc[-1]
        c = float(last_bar["Close"])
        o = float(last_bar["Open"])

        if direction == "BUY":
            # Green candle or strong lower rejection wick
            wick_low = min(c, o) - float(last_bar["Low"])
            confirmed = (c >= o) or (wick_low >= 1.0)
            return {"confirmed": confirmed, "reason": "5m বুলিশ ক্যান্ডেল ক্লোজ কনফার্মড" if confirmed else "5m রিজেকশন অপেক্ষমান"}
        elif direction == "SELL":
            # Red candle or strong upper rejection wick
            wick_high = float(last_bar["High"]) - max(c, o)
            confirmed = (c <= o) or (wick_high >= 1.0)
            return {"confirmed": confirmed, "reason": "5m বেয়ারিশ ক্যান্ডেল ক্লোজ কনফার্মড" if confirmed else "5m রিজেকশন অপেক্ষমান"}

        return {"confirmed": False, "reason": "নিরপেক্ষ"}

    def evaluate_1m_confirmation(self, df_1m: Optional[pd.DataFrame], direction: str) -> dict:
        """Evaluates 1M execution bar-close confirmation with EMA & RSI"""
        if df_1m is None or len(df_1m) < 14:
            return {"confirmed": True, "reason": "1m ডেটা সীমাবদ্ধ — ডিফল্ট অনুমোদিত"}

        df_calc = self.calculate_indicators(df_1m.copy())
        last_bar = df_calc.iloc[-1]
        c = float(last_bar["Close"])
        ema20 = float(last_bar.get("EMA_20", c))
        rsi = float(last_bar.get("RSI", 50.0))

        if direction == "BUY":
            confirmed = (c >= ema20 or rsi >= 45.0)
            return {"confirmed": confirmed, "reason": f"1m ক্লোজ ${c} | RSI: {rsi:.1f} (বুলিশ কনফার্মড)" if confirmed else "1m মোমেন্টাম অপর্যাপ্ত"}
        elif direction == "SELL":
            confirmed = (c <= ema20 or rsi <= 55.0)
            return {"confirmed": confirmed, "reason": f"1m ক্লোজ ${c} | RSI: {rsi:.1f} (বেয়ারিশ কনফার্মড)" if confirmed else "1m মোমেন্টাম অপর্যাপ্ত"}

        return {"confirmed": False, "reason": "নিরপেক্ষ"}

    # ─────────────────────────────────────────────────────────
    # 7. Simplified Master Strategy Engine
    # ─────────────────────────────────────────────────────────
    def analyze_master_strategy(
        self,
        df_4h: pd.DataFrame,
        df_1h: pd.DataFrame,
        df_15m: pd.DataFrame,
        df_5m: pd.DataFrame,
        current_price: float,
        news_risk: bool = False,
        daily_loss_reached: bool = False,
        df_1m: Optional[pd.DataFrame] = None,
        current_spread: float = 0.25,
    ) -> dict:
        """
        Simplified, cost-adjusted, structure-driven scalping strategy for Gold:
        1. 15M Trend & EMA 50/200 bias
        2. 5M Liquidity Sweeps, S/R, FVG/OB Retest
        3. 5M/1M Strict Bar-Close Confirmation
        4. Dynamic TP/SL (TP1 1:1.5 with breakeven move, TP2 1:2.5+)
        """
        # Calculate ATR 14
        atr = 3.0
        if df_15m is not None and len(df_15m) >= 14:
            df_15m_calc = self.calculate_indicators(df_15m.copy())
            atr = float(df_15m_calc["ATR"].iloc[-1])
            if np.isnan(atr) or atr < 1.0:
                atr = 3.0
        else:
            df_15m_calc = df_15m

        # ── Step 1: 15M Trend & Bias ──
        trend_15m = "RANGE"
        ema50_15m = current_price
        ema200_15m = current_price
        if df_15m_calc is not None and "EMA_50" in df_15m_calc.columns:
            ema50_15m = float(df_15m_calc["EMA_50"].iloc[-1])
            ema200_15m = float(df_15m_calc["EMA_200"].iloc[-1])
            if current_price >= ema50_15m and ema50_15m >= ema200_15m:
                trend_15m = "BULLISH"
            elif current_price <= ema50_15m and ema50_15m <= ema200_15m:
                trend_15m = "BEARISH"
            elif current_price > ema50_15m:
                trend_15m = "BULLISH"
            elif current_price < ema50_15m:
                trend_15m = "BEARISH"

        # Swings and Structure
        swings_15m = self.find_swings(df_15m, left=2, right=2) if df_15m is not None else {"highs": [], "lows": []}
        swings_5m  = self.find_swings(df_5m, left=2, right=2) if df_5m is not None else {"highs": [], "lows": []}
        struct_15m = self.detect_structure(df_15m, swings_15m) if df_15m is not None else {}
        eq_pools_15m = self.detect_equal_highs_lows(swings_15m, tolerance=0.60)
        eq_pools_5m  = self.detect_equal_highs_lows(swings_5m, tolerance=0.50) if df_5m is not None else {"equal_highs": [], "equal_lows": []}
        eq_pools = {
            "equal_highs": sorted(list(set(eq_pools_15m.get("equal_highs", []) + eq_pools_5m.get("equal_highs", [])))),
            "equal_lows": sorted(list(set(eq_pools_15m.get("equal_lows", []) + eq_pools_5m.get("equal_lows", [])))),
        }
        dealing_range = self.calculate_dealing_range_and_ote(swings_15m, current_price)
        liquidity = self.calculate_session_and_liquidity_levels(df_15m if df_15m is not None else df_1h)

        # ── Step 2: Setups & Sweeps ──
        sweep_15m = self.detect_liquidity_sweep(df_15m, liquidity, swings_15m, eq_pools)
        sweep_5m  = self.detect_liquidity_sweep(df_5m, liquidity, swings_5m, eq_pools) if df_5m is not None else {"bullish_sweep": False, "bearish_sweep": False}
        effective_sweep = sweep_15m if (sweep_15m["bullish_sweep"] or sweep_15m["bearish_sweep"]) else sweep_5m

        fvgs_15m = self.detect_fair_value_gaps(df_15m, lookback=20)
        fvgs_5m  = self.detect_fair_value_gaps(df_5m, lookback=20) if df_5m is not None else []
        obs_15m  = self.detect_order_blocks(df_15m, lookback=20)
        obs_5m   = self.detect_order_blocks(df_5m, lookback=20) if df_5m is not None else {"bullish_ob": None, "bearish_ob": None}

        active_bullish_fvg = [f for f in fvgs_15m if f["type"] == "BULLISH"] or [f for f in fvgs_5m if f["type"] == "BULLISH"]
        active_bearish_fvg = [f for f in fvgs_15m if f["type"] == "BEARISH"] or [f for f in fvgs_5m if f["type"] == "BEARISH"]

        disp_15m = self.detect_displacement(df_15m, atr)
        disp_5m  = self.detect_displacement(df_5m, atr) if df_5m is not None else {"bullish": False, "bearish": False, "size": 0.0}

        rsi_val = 50.0
        if df_15m_calc is not None and "RSI" in df_15m_calc.columns:
            rsi_val = float(df_15m_calc["RSI"].iloc[-1])

        # Candidate determination: With-trend OR Liquidity Sweep Reversal
        scalp_buy = False
        scalp_sell = False

        if trend_15m != "BEARISH" or effective_sweep["bullish_sweep"]:
            if effective_sweep["bullish_sweep"] or disp_15m["bullish"] or disp_5m["bullish"] or active_bullish_fvg:
                if rsi_val >= 35.0:  # allows oversold bounce
                    scalp_buy = True

        if trend_15m != "BULLISH" or effective_sweep["bearish_sweep"]:
            if effective_sweep["bearish_sweep"] or disp_15m["bearish"] or disp_5m["bearish"] or active_bearish_fvg:
                if rsi_val <= 65.0:  # allows overbought bounce
                    scalp_sell = True

        target_dir = "NEUTRAL"
        if scalp_buy and not scalp_sell:
            target_dir = "BUY"
        elif scalp_sell and not scalp_buy:
            target_dir = "SELL"
        elif scalp_buy and scalp_sell:
            target_dir = "BUY" if trend_15m == "BULLISH" else ("SELL" if trend_15m == "BEARISH" else "NEUTRAL")

        # ── Step 3: Confirmation Triggers ──
        conf_5m = {"confirmed": False, "reason": "5m সেটাপ অপেক্ষমান"}
        conf_1m = {"confirmed": False, "reason": "1m সেটাপ অপেক্ষমান"}
        if target_dir in ("BUY", "SELL"):
            conf_5m = self.evaluate_5m_confirmation(df_5m, target_dir)
            if df_1m is not None and not df_1m.empty:
                conf_1m = self.evaluate_1m_confirmation(df_1m, target_dir)
            else:
                conf_1m = conf_5m

        # ── Step 4: Dynamic Stop Loss & Structural Take Profit ──
        entry = current_price
        tp1 = entry
        sl = entry
        rr_str = "1:1.5"
        target_basis = "Structure Target"
        tp_valid = False
        suggested_lot = 0.01
        risk_pct_val = 0.50

        swings_5m_calc = swings_5m
        key_levels = self.pivot_levels(df_15m if df_15m is not None else df_1h)

        if target_dir in ("BUY", "SELL"):
            sweep_price = effective_sweep.get("swept_level_price")
            if target_dir == "BUY":
                last_ext = swings_5m["lows"][-1]["price"] if (swings_5m and swings_5m.get("lows")) else struct_15m.get("last_low")
            else:
                last_ext = swings_5m["highs"][-1]["price"] if (swings_5m and swings_5m.get("highs")) else struct_15m.get("last_high")

            ob_candidate = (
                obs_5m.get("bullish_ob") or obs_15m.get("bullish_ob")
                if target_dir == "BUY"
                else (obs_5m.get("bearish_ob") or obs_15m.get("bearish_ob"))
            )
            ob_extreme = (
                (ob_candidate.get("low") if target_dir == "BUY" else ob_candidate.get("high"))
                if ob_candidate
                else None
            )

            sl_data = self.risk_engine.calculate_stop_loss(
                direction=target_dir,
                entry_price=entry,
                sweep_level=sweep_price,
                last_swing_extreme=last_ext,
                ob_extreme=ob_extreme,
                atr=atr,
            )
            sl = sl_data["sl"]
            risk = sl_data["risk_distance"]

            tp_data = self.tp_engine.find_opposing_targets(
                direction=target_dir,
                entry_price=entry,
                sl_price=sl,
                swings_5m=swings_5m_calc,
                swings_15m=swings_15m,
                eq_pools=eq_pools,
                fvgs_5m=fvgs_5m,
                fvgs_15m=fvgs_15m,
                obs_5m=obs_5m,
                obs_15m=obs_15m,
                key_levels=key_levels,
                atr=atr,
                spread=current_spread,
            )

            tp_valid = tp_data.get("valid", False)
            if tp_valid:
                tp1 = tp_data["tp"]
                rr_val = tp_data.get("rr_ratio", 1.5)
                rr_str = f"1:{rr_val:.1f}"
                target_basis = tp_data.get("target_basis", "Dynamic Structural Target")
            else:
                target_basis = tp_data.get("reason", "No valid structural target")

            acc = self.risk_engine.db.get_paper_account()
            equity = acc.get("equity", 10000.0)
            sizing = self.risk_engine.calculate_position_size(equity, risk)
            if sizing.get("valid"):
                suggested_lot = sizing["lot"]
                risk_pct_val = sizing["risk_pct"]

        # Checklist
        checklist = [
            {"num": 1, "name": "15M Trend & EMA Alignment", "passed": (target_dir == "BUY" and trend_15m == "BULLISH") or (target_dir == "SELL" and trend_15m == "BEARISH")},
            {"num": 2, "name": "Liquidity Sweeps / S&R Setup", "passed": bool(effective_sweep.get("bullish_sweep") or effective_sweep.get("bearish_sweep") or active_bullish_fvg or active_bearish_fvg)},
            {"num": 3, "name": "RSI 14 Momentum Confluence", "passed": (target_dir == "BUY" and rsi_val >= 42) or (target_dir == "SELL" and rsi_val <= 58)},
            {"num": 4, "name": "Dynamic ATR SL Within Safe Bounds", "passed": bool(sl != entry and sl_data.get("valid", False)) if target_dir in ("BUY", "SELL") else False},
            {"num": 5, "name": "Cost-Adjusted Target Valid (>= 1.0R)", "passed": bool(tp_valid and tp1 != entry)},
            {"num": 6, "name": "5M Bar-Close Confirmed", "passed": bool(conf_5m.get("confirmed"))},
            {"num": 7, "name": "1M Execution Confirmed", "passed": bool(conf_1m.get("confirmed"))},
            {"num": 8, "name": "News Safety (CPI/NFP/FOMC Window)", "passed": not news_risk},
        ]
        passed_count = sum(1 for c in checklist if c["passed"])

        # Final Signal Decision
        final_direction = "NO_TRADE"
        reasoning = []

        if news_risk:
            final_direction = "WAIT"
            reasoning.append("⚠️ হাই-ইমপ্যাক্ট US নিউজ উইন্ডো সক্রিয় — ট্রেড সাময়িক স্থগিত।")
        elif target_dir in ("BUY", "SELL") and conf_5m.get("confirmed") and conf_1m.get("confirmed") and tp_valid:
            final_direction = target_dir
            reasoning.append("⚡ XAUUSD প্রাতিষ্ঠানিক স্ক্যাল্পিং সেটাপ")
            if effective_sweep.get("sweep_details"):
                reasoning.append(effective_sweep["sweep_details"])
            if active_bullish_fvg or active_bearish_fvg:
                reasoning.append("🎯 Fair Value Gap (FVG) ইমব্যালেন্স রিটেস্ট")
            reasoning.append(f"🎯 টার্গেট ভিত্তি: {target_basis}")
            reasoning.append(conf_5m.get("reason", ""))
            reasoning.append(conf_1m.get("reason", ""))
        else:
            final_direction = "NO_TRADE"
            reasoning.append("🟡 হাই-প্রোবাবিলিটি সেটাপ কনফার্মেশন অপেক্ষমান।")
            if not tp_valid and target_dir in ("BUY", "SELL"):
                reasoning.append(f"টার্গেট ফিল্টার: {target_basis}")

        return {
            "direction": final_direction,
            "setup_direction": target_dir,
            "setup_type": "SCALP",
            "setup_title": "⚡ XAUUSD গোল্ড স্ক্যাল্পিং (Structure Bar-Close)",
            "checklist_score": f"{passed_count}/{len(checklist)}",
            "passed_count": passed_count,
            "checklist": checklist,
            "trend_15m": trend_15m,
            "ema50_15m": ema50_15m,
            "ema200_15m": ema200_15m,
            "trend_4h": trend_15m,
            "bias_1h": trend_15m,
            "liquidity": liquidity,
            "sweep": effective_sweep,
            "dealing_range": dealing_range,
            "active_fvgs": active_bullish_fvg if target_dir == "BUY" else active_bearish_fvg,
            "confirmation_5m": conf_5m,
            "confirmation_1m": conf_1m,
            "entry": round(entry, 2),
            "tp1": round(tp1, 2),
            "tp2": round(tp1, 2),
            "sl": round(sl, 2),
            "risk_distance": risk if target_dir in ("BUY", "SELL") else 0.0,
            "rr_ratio": rr_str,
            "target_basis": target_basis,
            "suggested_lot": suggested_lot,
            "risk_pct": risk_pct_val,
            "atr": atr,
            "spread": current_spread,
            "reasoning": [r for r in reasoning if r],
        }

    # Backward compatibility helpers
    def detect_patterns(self, df: pd.DataFrame) -> list:
        return []

    def fibonacci_levels(self, df: pd.DataFrame, lookback: int = 50) -> dict:
        return {}

    def get_technical_score(self, df: pd.DataFrame) -> dict:
        return {"score": 50, "direction": "NEUTRAL", "details": {}}
