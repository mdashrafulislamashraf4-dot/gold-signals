"""
============================================================
  modules/technical.py
  সব ধরনের টেকনিক্যাল ইন্ডিকেটর এবং প্যাটার্ন এনালাইসিস
============================================================
"""

import logging
from typing import Optional

import numpy as np
import pandas as pd
import pandas_ta as ta

logger = logging.getLogger(__name__)


class TechnicalAnalyzer:
    """সম্পূর্ণ টেকনিক্যাল এনালাইসিস করে XAUUSD-এর জন্য"""

    def __init__(self):
        pass

    # ─────────────────────────────────────────────────────────
    # Calculate All Indicators
    # ─────────────────────────────────────────────────────────
    def calculate_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        সব টেকনিক্যাল ইন্ডিকেটর calculate করে
        """
        if df is None or len(df) < 50:
            logger.warning("Not enough data for indicators")
            return df

        try:
            close = df["Close"]
            high  = df["High"]
            low   = df["Low"]
            vol   = df.get("Volume", pd.Series([0] * len(df), index=df.index))

            # ── Trend Indicators ──────────────────────────────
            df["EMA_20"]  = ta.ema(close, length=20)
            df["EMA_50"]  = ta.ema(close, length=50)
            df["EMA_200"] = ta.ema(close, length=200)
            df["SMA_20"]  = ta.sma(close, length=20)

            # ── MACD ──────────────────────────────────────────
            macd = ta.macd(close, fast=12, slow=26, signal=9)
            if macd is not None and not macd.empty:
                df["MACD"]        = macd.iloc[:, 0]
                df["MACD_Signal"] = macd.iloc[:, 2]
                df["MACD_Hist"]   = macd.iloc[:, 1]

            # ── RSI ───────────────────────────────────────────
            df["RSI"] = ta.rsi(close, length=14)

            # ── Bollinger Bands ───────────────────────────────
            bbands = ta.bbands(close, length=20, std=2)
            if bbands is not None and not bbands.empty:
                df["BB_Upper"]  = bbands.iloc[:, 0]
                df["BB_Mid"]    = bbands.iloc[:, 1]
                df["BB_Lower"]  = bbands.iloc[:, 2]
                df["BB_Width"]  = bbands.iloc[:, 3]
                df["BB_Pct"]    = bbands.iloc[:, 4]

            # ── Stochastic ────────────────────────────────────
            stoch = ta.stoch(high, low, close, k=14, d=3)
            if stoch is not None and not stoch.empty:
                df["STOCH_K"] = stoch.iloc[:, 0]
                df["STOCH_D"] = stoch.iloc[:, 1]

            # ── ATR (Stop Loss calculation) ───────────────────
            df["ATR"] = ta.atr(high, low, close, length=14)

            # ── ADX (Trend Strength) ──────────────────────────
            adx = ta.adx(high, low, close, length=14)
            if adx is not None and not adx.empty:
                df["ADX"]    = adx.iloc[:, 0]
                df["DI_POS"] = adx.iloc[:, 1]
                df["DI_NEG"] = adx.iloc[:, 2]

            # ── Williams %R ───────────────────────────────────
            df["WILLR"] = ta.willr(high, low, close, length=14)

            # ── CCI ───────────────────────────────────────────
            df["CCI"] = ta.cci(high, low, close, length=20)

            # ── Ichimoku Cloud ────────────────────────────────
            ichimoku = ta.ichimoku(high, low, close)
            if ichimoku is not None and len(ichimoku) >= 2:
                ichi_df = ichimoku[0]
                if ichi_df is not None and not ichi_df.empty:
                    df["ICH_CONV"]  = ichi_df.iloc[:, 0]  # Tenkan-sen
                    df["ICH_BASE"]  = ichi_df.iloc[:, 1]  # Kijun-sen
                    df["ICH_SPA"]   = ichi_df.iloc[:, 2]  # Span A
                    df["ICH_SPB"]   = ichi_df.iloc[:, 3]  # Span B

            # ── VWAP ─────────────────────────────────────────
            try:
                df["VWAP"] = ta.vwap(high, low, close, vol)
            except Exception:
                pass

            # ── Momentum ─────────────────────────────────────
            df["MOM"] = ta.mom(close, length=10)
            df["ROC"] = ta.roc(close, length=10)

        except Exception as e:
            logger.error(f"Indicator calculation error: {e}")

        return df

    # ─────────────────────────────────────────────────────────
    # Candlestick Pattern Detection
    # ─────────────────────────────────────────────────────────
    def detect_patterns(self, df: pd.DataFrame) -> list:
        """ক্যান্ডেলস্টিক প্যাটার্ন ডিটেক্ট করে"""
        patterns = []
        if df is None or len(df) < 3:
            return patterns

        o = df["Open"].values
        h = df["High"].values
        l = df["Low"].values
        c = df["Close"].values

        i = len(c) - 1  # last candle

        body   = abs(c[i] - o[i])
        range_ = h[i] - l[i]
        body_pct = (body / range_ * 100) if range_ > 0 else 0

        # ── Doji ─────────────────────────────────────────────
        if body_pct < 5:
            patterns.append(("DOJI", "Neutral", "অনিশ্চয়তা — দিক পরিবর্তনের সম্ভাবনা"))

        # ── Hammer (Bullish) ──────────────────────────────────
        lower_wick = (min(o[i], c[i]) - l[i])
        upper_wick = (h[i] - max(o[i], c[i]))
        if lower_wick > body * 2 and upper_wick < body * 0.5 and c[i] > o[i]:
            patterns.append(("HAMMER", "Bullish", "🔨 Hammer — বুলিশ রিভার্সাল সিগনাল"))

        # ── Shooting Star (Bearish) ───────────────────────────
        if upper_wick > body * 2 and lower_wick < body * 0.5 and c[i] < o[i]:
            patterns.append(("SHOOTING_STAR", "Bearish", "💫 Shooting Star — বেয়ারিশ রিভার্সাল"))

        # ── Engulfing ─────────────────────────────────────────
        if i > 0:
            prev_body = abs(c[i-1] - o[i-1])
            # Bullish Engulfing
            if c[i-1] < o[i-1] and c[i] > o[i] and o[i] < c[i-1] and c[i] > o[i-1]:
                if body > prev_body:
                    patterns.append(("BULLISH_ENGULFING", "Bullish", "🟢 Bullish Engulfing — শক্তিশালী বুলিশ সিগনাল"))
            # Bearish Engulfing
            if c[i-1] > o[i-1] and c[i] < o[i] and o[i] > c[i-1] and c[i] < o[i-1]:
                if body > prev_body:
                    patterns.append(("BEARISH_ENGULFING", "Bearish", "🔴 Bearish Engulfing — শক্তিশালী বেয়ারিশ সিগনাল"))

        # ── Three White Soldiers (Bullish) ────────────────────
        if i >= 2:
            if (c[i] > c[i-1] > c[i-2] and
                o[i] > o[i-1] > o[i-2] and
                c[i] > o[i] and c[i-1] > o[i-1] and c[i-2] > o[i-2]):
                patterns.append(("THREE_WHITE_SOLDIERS", "Bullish", "🟢🟢🟢 Three White Soldiers — মজবুত আপট্রেন্ড"))

        # ── Three Black Crows (Bearish) ────────────────────────
        if i >= 2:
            if (c[i] < c[i-1] < c[i-2] and
                o[i] < o[i-1] < o[i-2] and
                c[i] < o[i] and c[i-1] < o[i-1] and c[i-2] < o[i-2]):
                patterns.append(("THREE_BLACK_CROWS", "Bearish", "🔴🔴🔴 Three Black Crows — মজবুত ডাউনট্রেন্ড"))

        # ── Morning Star (Bullish) ────────────────────────────
        if i >= 2:
            if (c[i-2] < o[i-2] and                  # bearish candle
                abs(c[i-1] - o[i-1]) < abs(c[i-2] - o[i-2]) * 0.3 and  # small body
                c[i] > o[i] and c[i] > (o[i-2] + c[i-2]) / 2):          # bullish candle
                patterns.append(("MORNING_STAR", "Bullish", "🌅 Morning Star — বুলিশ রিভার্সাল"))

        # ── Spinning Top ──────────────────────────────────────
        if 10 < body_pct < 30 and lower_wick > body and upper_wick > body:
            patterns.append(("SPINNING_TOP", "Neutral", "🔄 Spinning Top — অনিশ্চয়তা"))

        return patterns

    # ─────────────────────────────────────────────────────────
    # Fibonacci Retracement
    # ─────────────────────────────────────────────────────────
    def fibonacci_levels(self, df: pd.DataFrame, lookback: int = 50) -> dict:
        """Fibonacci Retracement লেভেল বের করে"""
        if df is None or len(df) < lookback:
            return {}

        recent = df.tail(lookback)
        swing_high = recent["High"].max()
        swing_low  = recent["Low"].min()
        diff = swing_high - swing_low

        levels = {
            "0.0":   round(swing_high, 2),
            "23.6":  round(swing_high - 0.236 * diff, 2),
            "38.2":  round(swing_high - 0.382 * diff, 2),
            "50.0":  round(swing_high - 0.500 * diff, 2),
            "61.8":  round(swing_high - 0.618 * diff, 2),
            "78.6":  round(swing_high - 0.786 * diff, 2),
            "100.0": round(swing_low, 2),
        }
        return levels

    # ─────────────────────────────────────────────────────────
    # Generate Technical Score
    # ─────────────────────────────────────────────────────────
    def get_technical_score(self, df: pd.DataFrame) -> dict:
        """
        টেকনিক্যাল ইন্ডিকেটর থেকে BUY/SELL স্কোর বের করে
        Returns: {score, direction, signals, details}
        """
        if df is None or df.empty:
            return {"score": 50, "direction": "NEUTRAL", "signals": [], "details": {}}

        df = self.calculate_indicators(df)
        last = df.iloc[-1]

        buy_signals  = []
        sell_signals = []

        close   = last["Close"]
        details = {}

        # ── RSI ───────────────────────────────────────────────
        rsi = last.get("RSI", np.nan)
        if not np.isnan(rsi):
            details["RSI"] = round(rsi, 1)
            if rsi < 30:
                buy_signals.append(f"RSI {rsi:.0f} → Oversold (BUY)")
            elif rsi > 70:
                sell_signals.append(f"RSI {rsi:.0f} → Overbought (SELL)")
            elif rsi < 50:
                buy_signals.append(f"RSI {rsi:.0f} → Bullish zone")
            else:
                sell_signals.append(f"RSI {rsi:.0f} → Bearish zone")

        # ── MACD ──────────────────────────────────────────────
        macd   = last.get("MACD", np.nan)
        macd_s = last.get("MACD_Signal", np.nan)
        macd_h = last.get("MACD_Hist", np.nan)
        if not (np.isnan(macd) or np.isnan(macd_s)):
            details["MACD"] = round(macd, 2)
            if macd > macd_s:
                buy_signals.append("MACD → Bullish crossover")
            else:
                sell_signals.append("MACD → Bearish crossover")
            if not np.isnan(macd_h) and macd_h > 0:
                buy_signals.append("MACD Histogram → Positive (momentum bullish)")
            elif not np.isnan(macd_h):
                sell_signals.append("MACD Histogram → Negative (momentum bearish)")

        # ── EMA Trend ─────────────────────────────────────────
        ema20  = last.get("EMA_20", np.nan)
        ema50  = last.get("EMA_50", np.nan)
        ema200 = last.get("EMA_200", np.nan)
        if not np.isnan(ema20):
            details["EMA_20"]  = round(ema20, 2)
            details["EMA_50"]  = round(ema50, 2) if not np.isnan(ema50) else "N/A"
            details["EMA_200"] = round(ema200, 2) if not np.isnan(ema200) else "N/A"

            if close > ema20:
                buy_signals.append("Price > EMA20 (Bullish)")
            else:
                sell_signals.append("Price < EMA20 (Bearish)")

            if not np.isnan(ema50):
                if ema20 > ema50:
                    buy_signals.append("EMA20 > EMA50 → Golden cross zone")
                else:
                    sell_signals.append("EMA20 < EMA50 → Death cross zone")

            if not np.isnan(ema200):
                if close > ema200:
                    buy_signals.append("Price above EMA200 → Long-term bullish")
                else:
                    sell_signals.append("Price below EMA200 → Long-term bearish")

        # ── Bollinger Bands ───────────────────────────────────
        bb_up  = last.get("BB_Upper", np.nan)
        bb_low = last.get("BB_Lower", np.nan)
        bb_pct = last.get("BB_Pct", np.nan)
        if not np.isnan(bb_up):
            details["BB_Upper"] = round(bb_up, 2)
            details["BB_Lower"] = round(bb_low, 2)
            if close < bb_low:
                buy_signals.append("Price below BB Lower → Oversold bounce expected")
            elif close > bb_up:
                sell_signals.append("Price above BB Upper → Overbought")
            elif not np.isnan(bb_pct) and bb_pct < 0.2:
                buy_signals.append("BB% < 20% → Near lower band (BUY zone)")

        # ── Stochastic ────────────────────────────────────────
        stk = last.get("STOCH_K", np.nan)
        std = last.get("STOCH_D", np.nan)
        if not np.isnan(stk):
            details["Stochastic_K"] = round(stk, 1)
            if stk < 20 and std < 20:
                buy_signals.append(f"Stochastic {stk:.0f} → Oversold")
            elif stk > 80 and std > 80:
                sell_signals.append(f"Stochastic {stk:.0f} → Overbought")
            if not np.isnan(std) and stk > std:
                buy_signals.append("Stochastic K > D → Bullish")
            elif not np.isnan(std):
                sell_signals.append("Stochastic K < D → Bearish")

        # ── ADX Trend Strength ────────────────────────────────
        adx    = last.get("ADX", np.nan)
        di_pos = last.get("DI_POS", np.nan)
        di_neg = last.get("DI_NEG", np.nan)
        if not np.isnan(adx):
            details["ADX"] = round(adx, 1)
            if adx > 25:
                if not np.isnan(di_pos) and di_pos > di_neg:
                    buy_signals.append(f"ADX {adx:.0f} — Strong uptrend (+DI > -DI)")
                elif not np.isnan(di_neg):
                    sell_signals.append(f"ADX {adx:.0f} — Strong downtrend (-DI > +DI)")

        # ── Williams %R ───────────────────────────────────────
        willr = last.get("WILLR", np.nan)
        if not np.isnan(willr):
            details["Williams_R"] = round(willr, 1)
            if willr < -80:
                buy_signals.append(f"Williams %R {willr:.0f} → Oversold")
            elif willr > -20:
                sell_signals.append(f"Williams %R {willr:.0f} → Overbought")

        # ── Ichimoku ──────────────────────────────────────────
        ich_conv = last.get("ICH_CONV", np.nan)
        ich_base = last.get("ICH_BASE", np.nan)
        if not (np.isnan(ich_conv) or np.isnan(ich_base)):
            if close > ich_conv and close > ich_base:
                buy_signals.append("Price above Ichimoku cloud → Bullish")
            elif close < ich_conv and close < ich_base:
                sell_signals.append("Price below Ichimoku cloud → Bearish")

        # ── Calculate Final Score ─────────────────────────────
        total    = len(buy_signals) + len(sell_signals)
        if total == 0:
            score     = 50
            direction = "NEUTRAL"
        else:
            buy_weight  = len(buy_signals)
            sell_weight = len(sell_signals)
            score = int((buy_weight / total) * 100)

            if score >= 65:
                direction = "BUY"
            elif score <= 35:
                direction = "SELL"
            else:
                direction = "NEUTRAL"

        # ── ATR for SL/TP ─────────────────────────────────────
        atr = last.get("ATR", np.nan)
        if not np.isnan(atr):
            details["ATR"] = round(atr, 2)

        return {
            "score":       score,
            "direction":   direction,
            "buy_signals": buy_signals,
            "sell_signals":sell_signals,
            "details":     details,
            "patterns":    self.detect_patterns(df),
            "fibonacci":   self.fibonacci_levels(df),
        }
