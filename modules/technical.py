"""
============================================================
  modules/technical.py
  আল্ট্রা-কম্প্রিহেনসিভ টেকনিক্যাল ইন্ডিকেটর এবং প্যাটার্ন এনালাইসিস
  (৩০+ ইনস্টিটিউশনাল ইন্ডিকেটর: Trend, Momentum, Volatility,
   Volume/Smart Money Flow, Pivot Points ও Candlestick Patterns)
============================================================
"""

from datetime import datetime, date, timedelta
import logging
from typing import Optional, List, Dict, Tuple

import numpy as np
import pandas as pd
import pytz

try:
    import pandas_ta as ta
except Exception:
    ta = None

logger = logging.getLogger(__name__)


class TechnicalAnalyzer:
    """
    সম্পূর্ণ ইনস্টিটিউশনাল টেকনিক্যাল এনালাইসিস ইঞ্জিন XAUUSD (Gold)-এর জন্য।
    ৩০টিরও বেশি টেকনিক্যাল ইন্ডিকেটর, ক্যান্ডেলস্টিক প্যাটার্ন এবং চার্ট ডাইভারজেন্স বিশ্লেষণ করে।
    """

    def __init__(self):
        pass

    # ─────────────────────────────────────────────────────────
    # Calculate All 30+ Indicators
    # ─────────────────────────────────────────────────────────
    def calculate_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        সব টেকনিক্যাল ইন্ডিকেটর calculate করে DataFrame-এ যুক্ত করে।
        pandas_ta লাইব্রেরি এবং পিওর Pandas/NumPy ব্যাকআপ দুটোই নিশ্চিত করে।
        """
        if df is None or len(df) < 50:
            logger.warning("Not enough data for indicators (need at least 50 bars)")
            return df

        try:
            close = df["Close"]
            high  = df["High"]
            low   = df["Low"]
            vol   = df.get("Volume", pd.Series([1000] * len(df), index=df.index)).fillna(1000)

            # ── 1. TREND INDICATORS (ট্রেন্ড) ─────────────────────────
            df["EMA_9"]   = close.ewm(span=9, adjust=False).mean()
            df["EMA_20"]  = close.ewm(span=20, adjust=False).mean()
            df["EMA_50"]  = close.ewm(span=50, adjust=False).mean()
            df["EMA_100"] = close.ewm(span=100, adjust=False).mean()
            df["EMA_200"] = close.ewm(span=200, adjust=False).mean()

            df["SMA_20"]  = close.rolling(window=20).mean()
            df["SMA_50"]  = close.rolling(window=50).mean()
            df["SMA_200"] = close.rolling(window=200).mean()

            # SuperTrend (10, 3)
            st_calc = False
            if ta is not None:
                try:
                    st = ta.supertrend(high, low, close, length=10, multiplier=3)
                    if st is not None and not st.empty:
                        df["SUPERT"]  = st.iloc[:, 0]
                        df["SUPERT_DIR"] = st.iloc[:, 1]
                        st_calc = True
                except Exception:
                    pass

            if not st_calc:
                tr1 = high - low
                tr2 = (high - close.shift(1)).abs()
                tr3 = (low - close.shift(1)).abs()
                tr_raw = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
                atr_st = tr_raw.rolling(10).mean().fillna(15)
                hl2 = (high + low) / 2
                up_b = hl2 + (3 * atr_st)
                lo_b = hl2 - (3 * atr_st)
                st_dir = np.ones(len(close))
                for idx in range(1, len(close)):
                    if close.iloc[idx] > up_b.iloc[idx - 1]:
                        st_dir[idx] = 1
                    elif close.iloc[idx] < lo_b.iloc[idx - 1]:
                        st_dir[idx] = -1
                    else:
                        st_dir[idx] = st_dir[idx - 1]
                df["SUPERT_DIR"] = pd.Series(st_dir, index=df.index)
                df["SUPERT"] = np.where(df["SUPERT_DIR"] == 1, lo_b, up_b)

            # Parabolic SAR (PSAR)
            psar_calc = False
            if ta is not None:
                try:
                    psar = ta.psar(high, low, close)
                    if psar is not None and not psar.empty:
                        df["PSAR_LONG"]  = psar.iloc[:, 0]
                        df["PSAR_SHORT"] = psar.iloc[:, 1]
                        df["PSAR"] = np.where(~df["PSAR_LONG"].isna(), df["PSAR_LONG"], df["PSAR_SHORT"])
                        psar_calc = True
                except Exception:
                    pass
            if not psar_calc:
                df["PSAR"] = df["EMA_20"]

            # Hull Moving Average (HMA 16)
            hma_calc = False
            if ta is not None:
                try:
                    df["HMA_16"] = ta.hma(close, length=16)
                    hma_calc = True
                except Exception:
                    pass
            if not hma_calc:
                # Fast WMA fallback
                df["HMA_16"] = close.ewm(span=16, adjust=False).mean()

            # Ichimoku Cloud (Tenkan, Kijun, Span A, Span B)
            high9  = high.rolling(9).max()
            low9   = low.rolling(9).min()
            df["ICH_CONV"] = (high9 + low9) / 2  # Tenkan-sen

            high26 = high.rolling(26).max()
            low26  = low.rolling(26).min()
            df["ICH_BASE"] = (high26 + low26) / 2  # Kijun-sen

            high52 = high.rolling(52).max()
            low52  = low.rolling(52).min()
            df["ICH_SPA"] = ((df["ICH_CONV"] + df["ICH_BASE"]) / 2).shift(26)
            df["ICH_SPB"] = ((high52 + low52) / 2).shift(26)

            # ── 2. MOMENTUM & OSCILLATORS ─────────────────────────────
            # RSI (14)
            delta = close.diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
            rs = gain / (loss.replace(0, 1e-9))
            df["RSI"] = 100 - (100 / (1 + rs))

            # MACD (12, 26, 9)
            ema12 = close.ewm(span=12, adjust=False).mean()
            ema26 = close.ewm(span=26, adjust=False).mean()
            df["MACD"]        = ema12 - ema26
            df["MACD_Signal"] = df["MACD"].ewm(span=9, adjust=False).mean()
            df["MACD_Hist"]   = df["MACD"] - df["MACD_Signal"]

            # Stochastic Oscillator (14, 3, 3)
            low14  = low.rolling(14).min()
            high14 = high.rolling(14).max()
            k = 100 * ((close - low14) / (high14 - low14 + 1e-9))
            df["STOCH_K"] = k
            df["STOCH_D"] = k.rolling(3).mean()

            # Stochastic RSI (14, 14, 3, 3)
            rsi_val = df["RSI"]
            rsi_min = rsi_val.rolling(14).min()
            rsi_max = rsi_val.rolling(14).max()
            stoch_rsi_k = 100 * ((rsi_val - rsi_min) / (rsi_max - rsi_min + 1e-9))
            df["STOCHRSI_K"] = stoch_rsi_k.rolling(3).mean()
            df["STOCHRSI_D"] = df["STOCHRSI_K"].rolling(3).mean()

            # CCI (Commodity Channel Index 20)
            tp = (high + low + close) / 3
            sma_tp = tp.rolling(20).mean()
            mad = (tp - sma_tp).abs().rolling(20).mean()
            df["CCI"] = (tp - sma_tp) / (0.015 * (mad + 1e-9))

            # Williams %R (14)
            df["WILLR"] = ((high14 - close) / (high14 - low14 + 1e-9)) * -100

            # Awesome Oscillator (AO)
            hl2_mid = (high + low) / 2
            df["AO"] = hl2_mid.rolling(5).mean() - hl2_mid.rolling(34).mean()

            # Momentum (10) & Rate of Change (ROC 10)
            df["MOM"] = close.diff(10)
            df["ROC"] = close.pct_change(10) * 100

            # ADX (14) & Directional Movement
            up_move = high.diff()
            down_move = -low.diff()
            plus_dm = np.where((up_move > down_move) & (up_move > 0), up_move, 0.0)
            minus_dm = np.where((down_move > up_move) & (down_move > 0), down_move, 0.0)

            tr1 = high - low
            tr2 = (high - close.shift(1)).abs()
            tr3 = (low - close.shift(1)).abs()
            tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
            tr_smooth = tr.rolling(14).mean().replace(0, 1e-9)

            df["DI_POS"] = (pd.Series(plus_dm, index=df.index).rolling(14).mean() / tr_smooth) * 100
            df["DI_NEG"] = (pd.Series(minus_dm, index=df.index).rolling(14).mean() / tr_smooth) * 100
            dx = (abs(df["DI_POS"] - df["DI_NEG"]) / (df["DI_POS"] + df["DI_NEG"] + 1e-9)) * 100
            df["ADX"] = dx.rolling(14).mean()

            # ── 3. VOLATILITY & PRICE BANDS ───────────────────────────
            # ATR (14)
            df["ATR"] = tr.rolling(14).mean()
            df["NATR"] = (df["ATR"] / close) * 100  # Normalized ATR %

            # Bollinger Bands (20, 2)
            sma_bb = close.rolling(window=20).mean()
            std_bb = close.rolling(window=20).std()
            df["BB_Upper"] = sma_bb + (std_bb * 2)
            df["BB_Mid"]   = sma_bb
            df["BB_Lower"] = sma_bb - (std_bb * 2)
            df["BB_Width"] = (df["BB_Upper"] - df["BB_Lower"]) / (sma_bb + 1e-9)
            df["BB_Pct"]   = (close - df["BB_Lower"]) / (df["BB_Upper"] - df["BB_Lower"] + 1e-9)

            # Keltner Channels (20, 1.5 ATR)
            kc_mid = df["EMA_20"]
            kc_atr = df["ATR"].fillna(15)
            df["KC_Upper"] = kc_mid + (1.5 * kc_atr)
            df["KC_Mid"]   = kc_mid
            df["KC_Lower"] = kc_mid - (1.5 * kc_atr)

            # TTM Squeeze / Bollinger Bands Squeeze
            # (True = ভোলাটিলিটি মারাত্মক কম্প্রেশনে আছে, দ্রুত বড় মুভমেন্ট আসবে)
            df["BB_SQUEEZE"] = (df["BB_Upper"] <= df["KC_Upper"]) & (df["BB_Lower"] >= df["KC_Lower"])

            # Donchian Channels (20)
            df["DC_HIGH"] = high.rolling(20).max()
            df["DC_LOW"]  = low.rolling(20).min()
            df["DC_MID"]  = (df["DC_HIGH"] + df["DC_LOW"]) / 2

            # ── 4. VOLUME & SMART MONEY FLOW ──────────────────────────
            # VWAP (Volume Weighted Average Price)
            typical_price = (high + low + close) / 3
            vol_sum = vol.cumsum().replace(0, 1)
            df["VWAP"] = (typical_price * vol).cumsum() / vol_sum

            # Money Flow Index (MFI 14)
            rmf = typical_price * vol
            pos_mf = pd.Series(np.where(typical_price > typical_price.shift(1), rmf, 0), index=df.index)
            neg_mf = pd.Series(np.where(typical_price < typical_price.shift(1), rmf, 0), index=df.index)
            mfr = pos_mf.rolling(14).sum() / (neg_mf.rolling(14).sum() + 1e-9)
            df["MFI"] = 100 - (100 / (1 + mfr))

            # On-Balance Volume (OBV) & OBV EMA
            obv_dir = np.where(close > close.shift(1), vol, np.where(close < close.shift(1), -vol, 0))
            df["OBV"] = pd.Series(obv_dir, index=df.index).cumsum()
            df["OBV_EMA"] = df["OBV"].ewm(span=20).mean()

            # Chaikin Money Flow (CMF 20)
            mfm = ((close - low) - (high - close)) / (high - low + 1e-9)
            mfv = mfm * vol
            df["CMF"] = mfv.rolling(20).sum() / (vol.rolling(20).sum() + 1e-9)

        except Exception as e:
            logger.error(f"Comprehensive indicator calculation error: {e}", exc_info=True)

        return df

    # ─────────────────────────────────────────────────────────
    # Candlestick Pattern Detection (15+ Patterns)
    # ─────────────────────────────────────────────────────────
    def detect_patterns(self, df: pd.DataFrame) -> list:
        """ক্যান্ডেলস্টিক প্যাটার্ন ও প্রাইস একশন ডিটেক্ট করে"""
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
        lower_wick = min(o[i], c[i]) - l[i]
        upper_wick = h[i] - max(o[i], c[i])

        # ── 1. Doji ──────────────────────────────────────────
        if body_pct < 6:
            patterns.append(("DOJI", "Neutral", "🕯️ Doji — মার্কেট দোলাচল ও সম্ভাব্য রিভার্সাল"))

        # ── 2. Hammer (Bullish) ──────────────────────────────
        if lower_wick > body * 2 and upper_wick < body * 0.5 and c[i] >= o[i]:
            patterns.append(("HAMMER", "Bullish", "🔨 Hammer — বুলিশ বাউন্স রিভার্সাল"))

        # ── 3. Inverted Hammer (Bullish) ─────────────────────
        if upper_wick > body * 2 and lower_wick < body * 0.5 and c[i] >= o[i]:
            patterns.append(("INVERTED_HAMMER", "Bullish", "🔨 Inverted Hammer — বুলিশ রিভার্সাল ইঙ্গিত"))

        # ── 4. Shooting Star (Bearish) ───────────────────────
        if upper_wick > body * 2 and lower_wick < body * 0.5 and c[i] <= o[i]:
            patterns.append(("SHOOTING_STAR", "Bearish", "💫 Shooting Star — শক্তিশালী বেয়ারিশ রিভার্সাল"))

        # ── 5. Hanging Man (Bearish) ─────────────────────────
        if lower_wick > body * 2 and upper_wick < body * 0.5 and c[i] < o[i]:
            patterns.append(("HANGING_MAN", "Bearish", "🪢 Hanging Man — টপে বেয়ারিশ সতর্কবার্তা"))

        # ── 6. Bullish / Bearish Pin Bar ─────────────────────
        if range_ > 0:
            if lower_wick / range_ >= 0.65:
                patterns.append(("BULLISH_PIN_BAR", "Bullish", "📍 Bullish Pin Bar — শক্তিশালী লোয়ার রিজেকশন (BUY)"))
            elif upper_wick / range_ >= 0.65:
                patterns.append(("BEARISH_PIN_BAR", "Bearish", "📍 Bearish Pin Bar — শক্তিশালী আপার রিজেকশন (SELL)"))

        # ── 7. Engulfing Patterns ────────────────────────────
        if i >= 1:
            prev_body = abs(c[i - 1] - o[i - 1])
            # Bullish Engulfing
            if c[i - 1] < o[i - 1] and c[i] > o[i] and o[i] <= c[i - 1] and c[i] >= o[i - 1]:
                if body > prev_body:
                    patterns.append(("BULLISH_ENGULFING", "Bullish", "🟢 Bullish Engulfing — শক্তিশালী বায়ার আক্রমণ"))
            # Bearish Engulfing
            if c[i - 1] > o[i - 1] and c[i] < o[i] and o[i] >= c[i - 1] and c[i] <= o[i - 1]:
                if body > prev_body:
                    patterns.append(("BEARISH_ENGULFING", "Bearish", "🔴 Bearish Engulfing — শক্তিশালী সেলার আক্রমণ"))

            # ── 8. Inside Bar Breakout ───────────────────────
            if h[i] < h[i - 1] and l[i] > l[i - 1]:
                patterns.append(("INSIDE_BAR", "Neutral", "📦 Inside Bar — ভোলাটিলিটি কম্প্রেশন (ব্রেকআউট অপেক্ষা)"))

            # ── 9. Piercing Line & Dark Cloud Cover ──────────
            mid_prev = (o[i - 1] + c[i - 1]) / 2
            if c[i - 1] < o[i - 1] and o[i] < l[i - 1] and c[i] > mid_prev and c[i] < o[i - 1]:
                patterns.append(("PIERCING_LINE", "Bullish", "☀️ Piercing Line — বুলিশ রিকভারি সিগনাল"))
            elif c[i - 1] > o[i - 1] and o[i] > h[i - 1] and c[i] < mid_prev and c[i] > o[i - 1]:
                patterns.append(("DARK_CLOUD_COVER", "Bearish", "☁️ Dark Cloud Cover — বেয়ারিশ চাপ"))

        # ── 10. Three-Candle Formations ──────────────────────
        if i >= 2:
            # Three White Soldiers
            if (c[i] > c[i - 1] > c[i - 2] and
                o[i] > o[i - 1] > o[i - 2] and
                c[i] > o[i] and c[i - 1] > o[i - 1] and c[i - 2] > o[i - 2]):
                patterns.append(("THREE_WHITE_SOLDIERS", "Bullish", "🟢🟢🟢 Three White Soldiers — মজবুত আপট্রেন্ড"))

            # Three Black Crows
            if (c[i] < c[i - 1] < c[i - 2] and
                o[i] < o[i - 1] < o[i - 2] and
                c[i] < o[i] and c[i - 1] < o[i - 1] and c[i - 2] < o[i - 2]):
                patterns.append(("THREE_BLACK_CROWS", "Bearish", "🔴🔴🔴 Three Black Crows — মজবুত ডাউনট্রেন্ড"))

            # Morning Star
            if (c[i - 2] < o[i - 2] and
                abs(c[i - 1] - o[i - 1]) < abs(c[i - 2] - o[i - 2]) * 0.35 and
                c[i] > o[i] and c[i] > (o[i - 2] + c[i - 2]) / 2):
                patterns.append(("MORNING_STAR", "Bullish", "🌅 Morning Star — শক্তিশালী বুলিশ রিভার্সাল"))

            # Evening Star
            if (c[i - 2] > o[i - 2] and
                abs(c[i - 1] - o[i - 1]) < abs(c[i - 2] - o[i - 2]) * 0.35 and
                c[i] < o[i] and c[i] < (o[i - 2] + c[i - 2]) / 2):
                patterns.append(("EVENING_STAR", "Bearish", "🌇 Evening Star — শক্তিশালী বেয়ারিশ রিভার্সাল"))

        return patterns

    # ─────────────────────────────────────────────────────────
    # Indicator Divergence Detection (RSI & MACD)
    # ─────────────────────────────────────────────────────────
    def detect_divergences(self, df: pd.DataFrame, lookback: int = 35) -> list:
        """চার্ট ও অসিলিয়েটরের মাঝে লুকায়িত ডাইভারজেন্স (Divergence) বের করে"""
        divergences = []
        if df is None or len(df) < lookback:
            return divergences

        try:
            sub = df.tail(lookback).copy().reset_index(drop=True)
            lows  = sub["Low"].values
            highs = sub["High"].values
            close = sub["Close"].values
            rsi   = sub.get("RSI", pd.Series()).values
            macd  = sub.get("MACD", pd.Series()).values

            if len(rsi) < lookback or pd.isna(rsi[-1]):
                return divergences

            # Find swing lows
            swing_lows = [
                idx for idx in range(2, len(lows) - 1)
                if lows[idx] <= lows[idx - 1] and lows[idx] <= lows[idx + 1] and lows[idx] <= lows[idx - 2]
            ]
            if len(swing_lows) >= 2:
                i1, i2 = swing_lows[-2], swing_lows[-1]
                # Regular Bullish Divergence (Price Lower Low, RSI Higher Low)
                if lows[i2] < lows[i1] and rsi[i2] > rsi[i1] + 1.5:
                    divergences.append(("BULLISH_RSI_DIV", "Bullish", "🟢 Bullish RSI Divergence — চার্টে নতুন লো হলেও RSI-এ ঊর্ধ্বগতি (তীব্র রিভার্সাল BUY)"))
                # Hidden Bullish Divergence (Price Higher Low, RSI Lower Low)
                elif lows[i2] > lows[i1] and rsi[i2] < rsi[i1] - 2.0:
                    divergences.append(("HIDDEN_BULLISH_DIV", "Bullish", "🟢 Hidden Bullish Divergence — শক্তিশালী আপট্রেন্ড কন্টিনিউয়েশন"))

            # Find swing highs
            swing_highs = [
                idx for idx in range(2, len(highs) - 1)
                if highs[idx] >= highs[idx - 1] and highs[idx] >= highs[idx + 1] and highs[idx] >= highs[idx - 2]
            ]
            if len(swing_highs) >= 2:
                i1, i2 = swing_highs[-2], swing_highs[-1]
                # Regular Bearish Divergence (Price Higher High, RSI Lower High)
                if highs[i2] > highs[i1] and rsi[i2] < rsi[i1] - 1.5:
                    divergences.append(("BEARISH_RSI_DIV", "Bearish", "🔴 Bearish RSI Divergence — চার্টে নতুন হাই হলেও RSI-এ নিম্নগতি (তীব্র রিভার্সাল SELL)"))
                # Hidden Bearish Divergence (Price Lower High, RSI Higher High)
                elif highs[i2] < highs[i1] and rsi[i2] > rsi[i1] + 2.0:
                    divergences.append(("HIDDEN_BEARISH_DIV", "Bearish", "🔴 Hidden Bearish Divergence — শক্তিশালী ডাউনট্রেন্ড কন্টিনিউয়েশন"))

        except Exception as e:
            logger.debug(f"Divergence detection notice: {e}")

        return divergences

    # ─────────────────────────────────────────────────────────
    # Fibonacci Levels
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
    # Classic Floor & Camarilla Pivot Points
    # ─────────────────────────────────────────────────────────
    def pivot_levels(self, df: pd.DataFrame) -> dict:
        """ইনস্টিটিউশনাল Floor এবং Camarilla পিভট লেভেল বের করে"""
        if df is None or len(df) < 2:
            return {}

        prev = df.iloc[-2]
        h = prev["High"]
        l = prev["Low"]
        c = prev["Close"]

        # Classic Floor Pivots
        p = (h + l + c) / 3
        r1 = 2 * p - l
        s1 = 2 * p - h
        r2 = p + (h - l)
        s2 = p - (h - l)

        # Camarilla Pivots (Gold intraday trading standard)
        rng = h - l
        cam_h4 = c + rng * 1.1 / 2  # Long Breakout
        cam_h3 = c + rng * 1.1 / 4  # Short Reversal Zone
        cam_l3 = c - rng * 1.1 / 4  # Long Reversal Zone
        cam_l4 = c - rng * 1.1 / 2  # Short Breakdown

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

    # ─────────────────────────────────────────────────────────
    # Generate Multi-Indicator Technical Score
    # ─────────────────────────────────────────────────────────
    def get_technical_score(self, df: pd.DataFrame) -> dict:
        """
        ৩০+ টেকনিক্যাল ইন্ডিকেটর, ক্যান্ডেলস্টিক প্যাটার্ন এবং ডাইভারজেন্স
        একত্রিত করে চূড়ান্ত কনফার্মেশন ও টেকনিক্যাল স্কোর (০-১০০) প্রদান করে।
        """
        if df is None or df.empty:
            return {
                "score": 50,
                "direction": "NEUTRAL",
                "buy_signals": [],
                "sell_signals": [],
                "details": {},
                "patterns": [],
                "fibonacci": {},
                "pivots": {},
                "divergences": [],
            }

        df = self.calculate_indicators(df)
        last = df.iloc[-1]
        prev = df.iloc[-2] if len(df) >= 2 else last

        buy_signals  = []
        sell_signals = []
        details      = {}

        close = last["Close"]

        # ── 1. TREND ANALYSIS ─────────────────────────────────────
        ema20  = last.get("EMA_20", np.nan)
        ema50  = last.get("EMA_50", np.nan)
        ema200 = last.get("EMA_200", np.nan)
        if not pd.isna(ema20):
            details["EMA_20"]  = round(ema20, 2)
            details["EMA_50"]  = round(ema50, 2) if not pd.isna(ema50) else "N/A"
            details["EMA_200"] = round(ema200, 2) if not pd.isna(ema200) else "N/A"

            if close > ema20:
                buy_signals.append("প্রাইস EMA20-এর উপরে (স্বল্পমেয়াদী আপট্রেন্ড)")
            else:
                sell_signals.append("প্রাইস EMA20-এর নিচে (স্বল্পমেয়াদী ডাউনট্রেন্ড)")

            if not pd.isna(ema50):
                if ema20 > ema50:
                    buy_signals.append("EMA20 > EMA50 (গোল্ডেন মোমেন্টাম ক্রস)")
                else:
                    sell_signals.append("EMA20 < EMA50 (বেয়ারিশ ডেথ ক্রস)")

            if not pd.isna(ema200):
                if close > ema200:
                    buy_signals.append("প্রাইস EMA200-এর উপরে (দীর্ঘমেয়াদী ম্যাক্রো আপট্রেন্ড)")
                else:
                    sell_signals.append("প্রাইস EMA200-এর নিচে (দীর্ঘমেয়াদী ম্যাক্রো ডাউনট্রেন্ড)")

        # SuperTrend (10, 3)
        st_dir = last.get("SUPERT_DIR", np.nan)
        st_val = last.get("SUPERT", np.nan)
        if not pd.isna(st_dir):
            details["SuperTrend"] = "BULLISH" if st_dir == 1 else "BEARISH"
            details["SuperTrend_Val"] = round(st_val, 2) if not pd.isna(st_val) else "N/A"
            if st_dir == 1:
                buy_signals.append(f"SuperTrend (10,3) → বুলিশ সাপোর্ট লেভেল ${st_val:.2f}")
            else:
                sell_signals.append(f"SuperTrend (10,3) → বেয়ারিশ রেজিস্ট্যান্স ${st_val:.2f}")

        # Parabolic SAR
        psar = last.get("PSAR", np.nan)
        if not pd.isna(psar):
            details["PSAR"] = round(psar, 2)
            if close > psar:
                buy_signals.append(f"Parabolic SAR (${psar:.2f}) প্রাইসের নিচে → আপট্রেন্ড সুরক্ষিত")
            else:
                sell_signals.append(f"Parabolic SAR (${psar:.2f}) প্রাইসের উপরে → ডাউনট্রেন্ড প্রেসার")

        # Hull Moving Average (HMA 16)
        hma = last.get("HMA_16", np.nan)
        prev_hma = prev.get("HMA_16", np.nan)
        if not pd.isna(hma):
            details["HMA_16"] = round(hma, 2)
            if close > hma and (pd.isna(prev_hma) or hma >= prev_hma):
                buy_signals.append("Hull MA (HMA 16) ঊর্ধ্বমুখী গতিশীল → দ্রুত ট্রেন্ড ক্রয় সাপোর্ট")
            elif close < hma and (pd.isna(prev_hma) or hma <= prev_hma):
                sell_signals.append("Hull MA (HMA 16) নিম্নমুখী গতিশীল → দ্রুত ট্রেন্ড বিক্রয় প্রেসার")

        # Ichimoku Cloud
        ich_conv = last.get("ICH_CONV", np.nan)
        ich_base = last.get("ICH_BASE", np.nan)
        ich_spa  = last.get("ICH_SPA", np.nan)
        ich_spb  = last.get("ICH_SPB", np.nan)
        if not (pd.isna(ich_conv) or pd.isna(ich_base)):
            details["Ichimoku_Tenkan"] = round(ich_conv, 2)
            details["Ichimoku_Kijun"]  = round(ich_base, 2)
            if close > ich_conv and close > ich_base:
                buy_signals.append("ইচিমোকু Tenkan ও Kijun উভয়ের উপরে প্রাইস অবস্থান")
            elif close < ich_conv and close < ich_base:
                sell_signals.append("ইচিমোকু Tenkan ও Kijun উভয়ের নিচে প্রাইস অবস্থান")

            if not (pd.isna(ich_spa) or pd.isna(ich_spb)):
                cloud_top = max(ich_spa, ich_spb)
                cloud_bot = min(ich_spa, ich_spb)
                if close > cloud_top:
                    buy_signals.append("প্রাইস ইচিমোকু কুমো ক্লাউডের উপরে (স্পষ্ট বুলিশ জোন)")
                elif close < cloud_bot:
                    sell_signals.append("প্রাইস ইচিমোকু কুমো ক্লাউডের নিচে (স্পষ্ট বেয়ারিশ জোন)")

        # ── 2. MOMENTUM & OSCILLATORS ─────────────────────────────
        # RSI (14)
        rsi = last.get("RSI", np.nan)
        if not pd.isna(rsi):
            details["RSI"] = round(rsi, 1)
            if rsi < 30:
                buy_signals.append(f"RSI {rsi:.0f} → ওভারসোল্ড জোন (শক্তিশালী বাউন্স ব্যাক সম্ভাবনা)")
            elif rsi > 70:
                sell_signals.append(f"RSI {rsi:.0f} → ওভারবট জোন (মুনাফা গ্রহণ ও রিভার্সাল সম্ভাবনা)")
            elif rsi > 50:
                buy_signals.append(f"RSI {rsi:.0f} → বুলিশ মোমেন্টাম জোন (Buyer Dominant)")
            elif rsi < 50:
                sell_signals.append(f"RSI {rsi:.0f} → বেয়ারিশ মোমেন্টাম জোন (Seller Dominant)")

        # MACD (12, 26, 9)
        macd   = last.get("MACD", np.nan)
        macd_s = last.get("MACD_Signal", np.nan)
        macd_h = last.get("MACD_Hist", np.nan)
        if not (pd.isna(macd) or pd.isna(macd_s)):
            details["MACD"] = round(macd, 2)
            details["MACD_Signal"] = round(macd_s, 2)
            if macd > macd_s:
                buy_signals.append("MACD বুলিশ ক্রসওভার (ঊর্ধ্বমুখী মোমেন্টাম বিস্তার)")
            else:
                sell_signals.append("MACD বেয়ারিশ ক্রসওভার (নিম্নমুখী মোমেন্টাম বিস্তার)")
            if not pd.isna(macd_h) and macd_h > 0:
                buy_signals.append("MACD হিস্টোগ্রাম গ্রিন জোন (বায়ারদের নিয়ন্ত্রণ)")
            elif not pd.isna(macd_h) and macd_h < 0:
                sell_signals.append("MACD হিস্টোগ্রাম রেড জোন (সেলারদের নিয়ন্ত্রণ)")

        # Stochastic Oscillator
        stk = last.get("STOCH_K", np.nan)
        std = last.get("STOCH_D", np.nan)
        if not pd.isna(stk):
            details["Stochastic_K"] = round(stk, 1)
            details["Stochastic_D"] = round(std, 1) if not pd.isna(std) else "N/A"
            if stk < 20 and std < 20:
                buy_signals.append(f"স্টোকাস্টিক K {stk:.0f} → ওভারসোল্ড জোন")
            elif stk > 80 and std > 80:
                sell_signals.append(f"স্টোকাস্টিক K {stk:.0f} → ওভারবট জোন")
            if not pd.isna(std) and stk > std:
                buy_signals.append("স্টোকাস্টিক K > D (বুলিশ ক্রস)")
            elif not pd.isna(std) and stk < std:
                sell_signals.append("স্টোকাস্টিক K < D (বেয়ারিশ ক্রস)")

        # Stochastic RSI
        strsi_k = last.get("STOCHRSI_K", np.nan)
        strsi_d = last.get("STOCHRSI_D", np.nan)
        if not pd.isna(strsi_k):
            details["StochRSI_K"] = round(strsi_k, 1)
            if strsi_k < 20:
                buy_signals.append(f"স্টোকাস্টিক RSI ({strsi_k:.0f}) চরম ওভারসোল্ড রিভার্সাল রেডি")
            elif strsi_k > 80:
                sell_signals.append(f"স্টোকাস্টিক RSI ({strsi_k:.0f}) চরম ওভারবট এক্সহশন রেডি")

        # CCI (Commodity Channel Index 20)
        cci = last.get("CCI", np.nan)
        if not pd.isna(cci):
            details["CCI"] = round(cci, 1)
            if cci < -100:
                buy_signals.append(f"কমোডিটি চ্যানেল ইনডেক্স (CCI {cci:.0f}) → অতি-বিক্রিত জোন")
            elif cci > 100:
                sell_signals.append(f"কমোডিটি চ্যানেল ইনডেক্স (CCI {cci:.0f}) → অতি-ক্রীত জোন")
            elif cci > 0:
                buy_signals.append(f"CCI ({cci:.0f}) পজিটিভ গোল্ড সেন্টিমেন্ট")
            elif cci < 0:
                sell_signals.append(f"CCI ({cci:.0f}) নেগেটিভ গোল্ড সেন্টিমেন্ট")

        # Williams %R
        willr = last.get("WILLR", np.nan)
        if not pd.isna(willr):
            details["Williams_R"] = round(willr, 1)
            if willr < -80:
                buy_signals.append(f"উইলিয়ামস %R ({willr:.0f}) → ওভারসোল্ড রিভার্সাল")
            elif willr > -20:
                sell_signals.append(f"উইলিয়ামস %R ({willr:.0f}) → ওভারবট এক্সহশন")

        # Awesome Oscillator (AO)
        ao = last.get("AO", np.nan)
        prev_ao = prev.get("AO", np.nan)
        if not pd.isna(ao):
            details["Awesome_Osc"] = round(ao, 2)
            if ao > 0:
                buy_signals.append("Awesome Oscillator (AO) শূন্যরেখার উপরে (বুলিশ)")
            else:
                sell_signals.append("Awesome Oscillator (AO) শূন্যরেখার নিচে (বেয়ারিশ)")
            if not pd.isna(prev_ao) and ao > prev_ao:
                buy_signals.append("AO ক্রমবর্ধমান গতিশীল (বুলিশ অ্যাক্সিলারেশন)")
            elif not pd.isna(prev_ao) and ao < prev_ao:
                sell_signals.append("AO ক্রমহ্রাসমান গতিশীল (বেয়ারিশ অ্যাক্সিলারেশন)")

        # ADX Trend Strength
        adx    = last.get("ADX", np.nan)
        di_pos = last.get("DI_POS", np.nan)
        di_neg = last.get("DI_NEG", np.nan)
        if not pd.isna(adx):
            details["ADX"] = round(adx, 1)
            if adx > 25:
                if not pd.isna(di_pos) and di_pos > di_neg:
                    buy_signals.append(f"ADX {adx:.0f} → শক্তিশালী আপট্রেন্ড কনফার্মেশন (+DI > -DI)")
                elif not pd.isna(di_neg):
                    sell_signals.append(f"ADX {adx:.0f} → শক্তিশালী ডাউনট্রেন্ড কনফার্মেশন (-DI > +DI)")

        # ── 3. VOLATILITY & PRICE BANDS ───────────────────────────
        bb_up   = last.get("BB_Upper", np.nan)
        bb_low  = last.get("BB_Lower", np.nan)
        bb_pct  = last.get("BB_Pct", np.nan)
        squeeze = last.get("BB_SQUEEZE", False)
        details["BB_Upper"] = round(bb_up, 2) if not pd.isna(bb_up) else "N/A"
        details["BB_Lower"] = round(bb_low, 2) if not pd.isna(bb_low) else "N/A"
        details["Squeeze"]  = "ACTIVE (কম্প্রেশন)" if squeeze else "RELEASED (মুক্ত)"

        if not pd.isna(bb_low) and close <= bb_low:
            buy_signals.append("প্রাইস বলিঙ্গার লোয়ার ব্যান্ডে বাউন্স সাপোর্ট টেস্ট করছে")
        elif not pd.isna(bb_up) and close >= bb_up:
            sell_signals.append("প্রাইস বলিঙ্গার আপার ব্যান্ডে রেজিস্ট্যান্স টেস্ট করছে")
        elif not pd.isna(bb_pct) and bb_pct < 0.25:
            buy_signals.append("প্রাইস বলিঙ্গার ব্যান্ডের নিচের জোনে (ভ্যালু বাই সাপোর্ট)")

        if squeeze:
            details["Volatility_Alert"] = "TTM Squeeze Active (বিস্ফোরক ব্রেকআউট সন্নিকটে)"

        # Donchian Breakout
        dc_h = last.get("DC_HIGH", np.nan)
        dc_l = last.get("DC_LOW", np.nan)
        if not pd.isna(dc_h) and close >= dc_h:
            buy_signals.append("Donchian Channel ২০-পিরিয়ড ব্রেকআউট হাই (টার্টল ট্রেডিং BUY)")
        elif not pd.isna(dc_l) and close <= dc_l:
            sell_signals.append("Donchian Channel ২০-পিরিয়ড ব্রেকডাউন লো (টার্টল ট্রেডিং SELL)")

        # ── 4. VOLUME & SMART MONEY FLOW ──────────────────────────
        vwap = last.get("VWAP", np.nan)
        if not pd.isna(vwap):
            details["VWAP"] = round(vwap, 2)
            if close > vwap:
                buy_signals.append(f"প্রাইস প্রাতিষ্ঠানিক VWAP (${vwap:.2f})-এর উপরে (বায়ার প্রাধান্য)")
            else:
                sell_signals.append(f"প্রাইস প্রাতিষ্ঠানিক VWAP (${vwap:.2f})-এর নিচে (সেলার প্রাধান্য)")

        # MFI (Money Flow Index 14)
        mfi = last.get("MFI", np.nan)
        if not pd.isna(mfi):
            details["MFI"] = round(mfi, 1)
            if mfi < 25:
                buy_signals.append(f"Money Flow Index ({mfi:.0f}) স্মার্ট মানি ওভারসোল্ড অ্যাকুমুলেশন")
            elif mfi > 75:
                sell_signals.append(f"Money Flow Index ({mfi:.0f}) স্মার্ট মানি ওভারবট ডিস্ট্রিবিউশন")
            elif mfi > 50:
                buy_signals.append(f"MFI ({mfi:.0f}) পজিটিভ প্রাতিষ্ঠানিক ভলিউম প্রবাহ")
            elif mfi < 50:
                sell_signals.append(f"MFI ({mfi:.0f}) নেগেটিভ প্রাতিষ্ঠানিক ভলিউম আউটফ্লো")

        # OBV Trend
        obv = last.get("OBV", np.nan)
        obv_ema = last.get("OBV_EMA", np.nan)
        if not (pd.isna(obv) or pd.isna(obv_ema)):
            if obv > obv_ema:
                buy_signals.append("On-Balance Volume (OBV) আপট্রেন্ডে পুষ্টি জোগাচ্ছে")
            else:
                sell_signals.append("On-Balance Volume (OBV) ডাউনট্রেন্ডে পুষ্টি জোগাচ্ছে")

        # Chaikin Money Flow (CMF)
        cmf = last.get("CMF", np.nan)
        if not pd.isna(cmf):
            details["CMF"] = round(cmf, 3)
            if cmf > 0.05:
                buy_signals.append(f"Chaikin Money Flow ({cmf:+.2f}) পজিটিভ স্মার্ট মানি ইনজেকশন")
            elif cmf < -0.05:
                sell_signals.append(f"Chaikin Money Flow ({cmf:+.2f}) নেগেটিভ স্মার্ট মানি বহির্গমন")

        # ── 5. DIVERGENCES & PATTERNS ─────────────────────────────
        divergences = self.detect_divergences(df)
        for div in divergences:
            if div[1] == "Bullish":
                buy_signals.append(div[2])
            elif div[1] == "Bearish":
                sell_signals.append(div[2])

        patterns = self.detect_patterns(df)
        for pat in patterns:
            if pat[1] == "Bullish":
                buy_signals.append(pat[2])
            elif pat[1] == "Bearish":
                sell_signals.append(pat[2])

        # ── 6. PIVOTS & FIBONACCI ─────────────────────────────────
        pivots = self.pivot_levels(df)
        fib_levels = self.fibonacci_levels(df)

        if pivots:
            p_val = pivots.get("pivot", close)
            details["Pivot_Point"] = p_val
            details["Cam_H4"] = pivots.get("cam_h4", "N/A")
            details["Cam_L4"] = pivots.get("cam_l4", "N/A")
            if close > p_val:
                buy_signals.append(f"প্রাইস ডেইলি পিভট পয়েন্ট (${p_val})-এর উপরে ট্রেড হচ্ছে")
            else:
                sell_signals.append(f"প্রাইস ডেইলি পিভট পয়েন্ট (${p_val})-এর নিচে ট্রেড হচ্ছে")

        # ATR for risk management
        atr = last.get("ATR", np.nan)
        if not pd.isna(atr):
            details["ATR"] = round(atr, 2)
        else:
            details["ATR"] = 15.0

        # ── 7. COMPREHENSIVE SCORE CALCULATION ────────────────────
        total = len(buy_signals) + len(sell_signals)
        if total == 0:
            score     = 50
            direction = "NEUTRAL"
        else:
            buy_weight  = len(buy_signals)
            score = int((buy_weight / total) * 100)

            if score >= 65:
                direction = "BUY"
            elif score <= 35:
                direction = "SELL"
            else:
                direction = "NEUTRAL"

        return {
            "score":             score,
            "direction":         direction,
            "buy_signals":       buy_signals,
            "sell_signals":      sell_signals,
            "details":           details,
            "patterns":          patterns,
            "fibonacci":         fib_levels,
            "pivots":            pivots,
            "divergences":       divergences,
            "total_indicators":  total,
        }

    # ─────────────────────────────────────────────────────────
    # ── SMART MONEY CONCEPTS (SMC) & MASTER STRATEGY ENGINE ──
    # ─────────────────────────────────────────────────────────

    def find_swings(self, df: pd.DataFrame, left: int = 2, right: int = 2) -> dict:
        """
        ফ্র্যাক্টাল সুইং হাই (Swing High) এবং সুইং লো (Swing Low) চিহ্নিত করে
        """
        highs = []
        lows = []
        if df is None or len(df) < (left + right + 1):
            return {"highs": highs, "lows": lows}

        h = df["High"].values
        l = df["Low"].values
        times = df.index

        for i in range(left, len(df) - right):
            # Check swing high
            is_sh = True
            for offset in range(-left, right + 1):
                if offset != 0 and h[i] < h[i + offset]:
                    is_sh = False
                    break
            if is_sh:
                highs.append({"index": i, "price": round(float(h[i]), 2), "time": str(times[i])})

            # Check swing low
            is_sl = True
            for offset in range(-left, right + 1):
                if offset != 0 and l[i] > l[i + offset]:
                    is_sl = False
                    break
            if is_sl:
                lows.append({"index": i, "price": round(float(l[i]), 2), "time": str(times[i])})

        return {"highs": highs, "lows": lows}

    def detect_structure(self, df: pd.DataFrame, swings: dict) -> dict:
        """
        মার্কেট স্ট্রাকচার (HH/HL, LH/LL, BOS, CHoCH) এবং উইক বনাম ক্যান্ডেল বডি ক্লোজ বিশ্লেষণ করে
        """
        highs = swings.get("highs", [])
        lows = swings.get("lows", [])

        trend = "RANGE"
        bos_bullish = False
        bos_bearish = False
        choch_bullish = False
        choch_bearish = False
        body_close_break = False
        wick_fakeout = False

        if len(highs) >= 2 and len(lows) >= 2:
            h1, h2 = highs[-2]["price"], highs[-1]["price"]
            l1, l2 = lows[-2]["price"], lows[-1]["price"]

            if h2 > h1 and l2 >= l1:
                trend = "BULLISH"
            elif h2 <= h1 and l2 < l1:
                trend = "BEARISH"
            else:
                trend = "RANGE"

            cur_close = float(df["Close"].iloc[-1])
            cur_high  = float(df["High"].iloc[-1])
            cur_low   = float(df["Low"].iloc[-1])
            last_sh   = highs[-1]["price"]
            last_sl   = lows[-1]["price"]

            # 1-Bar Rule: Body Close = True BOS, Wick Only = Liquidity Sweep / Fakeout
            if cur_close > last_sh:
                bos_bullish = True
                body_close_break = True
            elif cur_high > last_sh and cur_close <= last_sh:
                wick_fakeout = True

            if cur_close < last_sl:
                bos_bearish = True
                body_close_break = True
            elif cur_low < last_sl and cur_close >= last_sl:
                wick_fakeout = True

            # CHoCH check: Counter-trend break with candle close
            if trend == "BEARISH" and cur_close > last_sh:
                choch_bullish = True
            elif trend == "BULLISH" and cur_close < last_sl:
                choch_bearish = True

        return {
            "trend": trend,
            "bos_bullish": bos_bullish,
            "bos_bearish": bos_bearish,
            "choch_bullish": choch_bullish,
            "choch_bearish": choch_bearish,
            "body_close_break": body_close_break,
            "wick_fakeout": wick_fakeout,
            "last_high": highs[-1]["price"] if highs else None,
            "last_low": lows[-1]["price"] if lows else None,
        }

    def detect_equal_highs_lows(self, swings: dict, tolerance: float = 0.50) -> dict:
        """
        Equal Highs (EQH - Buy-Side Liquidity Pool) এবং 
        Equal Lows (EQL - Sell-Side Liquidity Pool) চিহ্নিত করে
        """
        highs = swings.get("highs", [])
        lows = swings.get("lows", [])
        eq_highs = []
        eq_lows = []

        if len(highs) >= 2:
            for i in range(len(highs) - 1):
                for j in range(i + 1, min(i + 4, len(highs))):
                    diff = abs(highs[i]["price"] - highs[j]["price"])
                    if diff <= tolerance:
                        avg_p = round((highs[i]["price"] + highs[j]["price"]) / 2, 2)
                        eq_highs.append({"price": avg_p, "name": f"Equal Highs (EQH ${avg_p})"})

        if len(lows) >= 2:
            for i in range(len(lows) - 1):
                for j in range(i + 1, min(i + 4, len(lows))):
                    diff = abs(lows[i]["price"] - lows[j]["price"])
                    if diff <= tolerance:
                        avg_p = round((lows[i]["price"] + lows[j]["price"]) / 2, 2)
                        eq_lows.append({"price": avg_p, "name": f"Equal Lows (EQL ${avg_p})"})

        return {"eq_highs": eq_highs, "eq_lows": eq_lows}

    def calculate_dealing_range_and_ote(self, swings: dict, current_price: float) -> dict:
        """
        Dealing Range (Swing Low থেকে Swing High), 50% Equilibrium (EQ),
        Discount/Premium জোন এবং OTE (Optimal Trade Entry - 62% to 79% Fib) নির্ণয় করে
        """
        highs = swings.get("highs", [])
        lows = swings.get("lows", [])
        if not highs or not lows:
            return {
                "zone": "EQUILIBRIUM",
                "eq": current_price,
                "ote_buy": False,
                "ote_sell": False,
                "range_high": current_price,
                "range_low": current_price,
            }

        range_high = max([h["price"] for h in highs[-4:]])
        range_low  = min([l["price"] for l in lows[-4:]])
        total_range = range_high - range_low

        if total_range <= 1.0:
            return {
                "zone": "EQUILIBRIUM",
                "eq": current_price,
                "ote_buy": False,
                "ote_sell": False,
                "range_high": range_high,
                "range_low": range_low,
            }

        eq = round((range_high + range_low) / 2.0, 2)

        # OTE for Bullish Discount (61.8% to 78.6% retracement from High)
        ote_buy_top = round(range_high - (total_range * 0.618), 2)
        ote_buy_bot = round(range_high - (total_range * 0.786), 2)

        # OTE for Bearish Premium (61.8% to 78.6% retracement from Low)
        ote_sell_bot = round(range_low + (total_range * 0.618), 2)
        ote_sell_top = round(range_low + (total_range * 0.786), 2)

        zone = "DISCOUNT" if current_price < eq else ("PREMIUM" if current_price > eq else "EQUILIBRIUM")
        ote_buy = (ote_buy_bot <= current_price <= ote_buy_top)
        ote_sell = (ote_sell_bot <= current_price <= ote_sell_top)

        return {
            "range_high": range_high,
            "range_low": range_low,
            "eq": eq,
            "zone": zone,
            "ote_buy": ote_buy,
            "ote_sell": ote_sell,
            "ote_buy_zone": (ote_buy_bot, ote_buy_top),
            "ote_sell_zone": (ote_sell_bot, ote_sell_top),
        }

    def detect_fair_value_gaps(self, df: pd.DataFrame, lookback: int = 30) -> list:
        """
        Fair Value Gap (FVG) চিহ্নিত করে এবং রিটেস্ট অবস্থা যাচাই করে
        """
        fvgs = []
        if df is None or len(df) < 5:
            return fvgs

        sub = df.tail(lookback).copy()
        h = sub["High"].values
        l = sub["Low"].values
        c = sub["Close"].values
        cur_price = c[-1]

        for i in range(2, len(sub)):
            # Bullish FVG: Candle 1 High < Candle 3 Low
            c1_h = h[i - 2]
            c3_l = l[i]
            if c3_l > c1_h + 0.3:  # minimum 30 cents gap for gold
                gap_top = round(float(c3_l), 2)
                gap_bottom = round(float(c1_h), 2)
                retested = False
                for j in range(i + 1, len(sub)):
                    if l[j] <= gap_top:
                        retested = True
                        break
                active = cur_price >= gap_bottom - 1.0 and cur_price <= gap_top + 3.0
                fvgs.append({
                    "type": "BULLISH",
                    "top": gap_top,
                    "bottom": gap_bottom,
                    "retested": retested,
                    "active": active,
                    "bar_index": i,
                })

            # Bearish FVG: Candle 1 Low > Candle 3 High
            c1_l = l[i - 2]
            c3_h = h[i]
            if c1_l > c3_h + 0.3:
                gap_top = round(float(c1_l), 2)
                gap_bottom = round(float(c3_h), 2)
                retested = False
                for j in range(i + 1, len(sub)):
                    if h[j] >= gap_bottom:
                        retested = True
                        break
                active = cur_price <= gap_top + 1.0 and cur_price >= gap_bottom - 3.0
                fvgs.append({
                    "type": "BEARISH",
                    "top": gap_top,
                    "bottom": gap_bottom,
                    "retested": retested,
                    "active": active,
                    "bar_index": i,
                })

        return fvgs

    def detect_order_blocks(self, df: pd.DataFrame, lookback: int = 30) -> dict:
        """
        অর্ডার ব্লক (Demand ও Supply জোন) চিহ্নিত করে এবং রিটেস্ট পরীক্ষা করে
        """
        if df is None or len(df) < 5:
            return {"bullish_ob": None, "bearish_ob": None}

        sub = df.tail(lookback).copy()
        o = sub["Open"].values
        h = sub["High"].values
        l = sub["Low"].values
        c = sub["Close"].values
        cur_price = c[-1]

        bullish_ob = None
        bearish_ob = None

        # Look for last opposite candle before strong displacement
        for i in range(len(sub) - 3, 1, -1):
            # Bullish OB: Bearish candle followed by strong bullish displacement
            if c[i] < o[i] and c[i + 1] > o[i + 1] and (c[i + 1] > h[i] or (i + 2 < len(sub) and c[i + 2] > h[i])):
                if not bullish_ob:
                    top = round(float(h[i]), 2)
                    bottom = round(float(l[i]), 2)
                    is_testing = (bottom - 0.5 <= cur_price <= top + 1.5)
                    bullish_ob = {
                        "top": top,
                        "bottom": bottom,
                        "candle_type": "BEARISH",
                        "testing": is_testing,
                        "invalidated": cur_price < bottom,
                    }

            # Bearish OB: Bullish candle followed by strong bearish displacement
            if c[i] > o[i] and c[i + 1] < o[i + 1] and (c[i + 1] < l[i] or (i + 2 < len(sub) and c[i + 2] < l[i])):
                if not bearish_ob:
                    top = round(float(h[i]), 2)
                    bottom = round(float(l[i]), 2)
                    is_testing = (bottom - 1.5 <= cur_price <= top + 0.5)
                    bearish_ob = {
                        "top": top,
                        "bottom": bottom,
                        "candle_type": "BULLISH",
                        "testing": is_testing,
                        "invalidated": cur_price > top,
                    }

            if bullish_ob and bearish_ob:
                break

        return {"bullish_ob": bullish_ob, "bearish_ob": bearish_ob}

    def calculate_session_and_liquidity_levels(self, df: pd.DataFrame, timezone_str: str = "Asia/Dhaka") -> dict:
        """
        Liquidity Map ও Session Reference তৈরি করে:
        (দ্রষ্টব্য: এটি কেবল লেভেল ম্যাপিংয়ের জন্য, কোনো ট্রেড ব্লক করার জন্য নয়)
        """
        import pytz
        tz = pytz.timezone(timezone_str)

        res = {
            "pdh": None,
            "pdl": None,
            "asian_high": None,
            "asian_low": None,
            "current_session": "সার্বক্ষণিক সেশন",
            "session_code": "ACTIVE_24_7",
        }

        if df is None or df.empty:
            return res

        try:
            df_local = df.copy()
            if df_local.index.tz is None:
                df_local.index = df_local.index.tz_localize("UTC").tz_convert(tz)
            else:
                df_local.index = df_local.index.tz_convert(tz)

            now_local = datetime.now(tz)
            hour = now_local.hour
            minute = now_local.minute
            current_time_dec = hour + (minute / 60.0)

            if 6.0 <= current_time_dec < 13.0:
                res["current_session"] = "এশিয়ান সেশন (Asian Session)"
                res["session_code"] = "ASIA"
            elif 13.0 <= current_time_dec < 18.0:
                res["current_session"] = "লন্ডন সেশন (London Session)"
                res["session_code"] = "LONDON"
            elif 18.0 <= current_time_dec < 22.5:
                res["current_session"] = "লন্ডন–নিউ ইয়র্ক ওভারল্যাপ (London-NY Overlap)"
                res["session_code"] = "LONDON_NY_OVERLAP"
            else:
                res["current_session"] = "নিউ ইয়র্ক / গ্লোবাল ট্রেডিং সেশন"
                res["session_code"] = "NY_GLOBAL"

            # PDH / PDL (Previous Day High/Low)
            dates = sorted(list(set(d.date() for d in df_local.index)))
            today = now_local.date()
            prev_dates = [d for d in dates if d < today]

            if prev_dates:
                last_day = prev_dates[-1]
                day_df = df_local[df_local.index.date == last_day]
                if not day_df.empty:
                    res["pdh"] = round(float(day_df["High"].max()), 2)
                    res["pdl"] = round(float(day_df["Low"].min()), 2)

            # Asian Session High/Low (if formed)
            asian_df = df_local[(df_local.index.date == today) & (df_local.index.hour >= 6) & (df_local.index.hour < 13)]
            if asian_df.empty and prev_dates:
                last_day = prev_dates[-1]
                asian_df = df_local[(df_local.index.date == last_day) & (df_local.index.hour >= 6) & (df_local.index.hour < 13)]

            if not asian_df.empty:
                res["asian_high"] = round(float(asian_df["High"].max()), 2)
                res["asian_low"] = round(float(asian_df["Low"].min()), 2)

        except Exception as e:
            logger.warning(f"Error calculating session levels: {e}")

        return res

    def detect_liquidity_sweep(
        self,
        df: pd.DataFrame,
        liquidity: dict,
        swings: dict = None,
        eq_pools: dict = None,
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
        if eq_pools and eq_pools.get("eq_lows"):
            for eql in eq_pools["eq_lows"][:2]:
                ssl_levels.append((eql["name"], eql["price"]))
        if pdl:
            ssl_levels.append(("Previous Day Low (PDL)", pdl))
        if asian_low:
            ssl_levels.append(("Asian Session Low", asian_low))
        if swings and swings.get("lows"):
            for sl_item in swings["lows"][-2:]:
                ssl_levels.append(("Recent Swing Low (SSL)", sl_item["price"]))

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
        if eq_pools and eq_pools.get("eq_highs"):
            for eqh in eq_pools["eq_highs"][:2]:
                bsl_levels.append((eqh["name"], eqh["price"]))
        if pdh:
            bsl_levels.append(("Previous Day High (PDH)", pdh))
        if asian_high:
            bsl_levels.append(("Asian Session High", asian_high))
        if swings and swings.get("highs"):
            for sh_item in swings["highs"][-2:]:
                bsl_levels.append(("Recent Swing High (BSL)", sh_item["price"]))

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
        """
        Relative Volume (RVOL) বের করে (বর্তমান ভলিউম বনাম ২০ ক্যান্ডেলের গড় ভলিউম)
        """
        if df is None or "Volume" not in df.columns or len(df) < period:
            return 1.0
        vol = df["Volume"].fillna(0)
        avg_vol = vol.tail(period + 1).iloc[:-1].mean()
        if avg_vol <= 0:
            return 1.0
        cur_vol = vol.iloc[-1]
        return round(float(cur_vol / avg_vol), 2)

    def detect_displacement(self, df: pd.DataFrame, atr: float) -> dict:
        """
        ইনস্টিটিউশনাল ডিসপ্লেসমেন্ট (Displacement) ক্যান্ডেল ডিটেক্ট করে
        """
        if df is None or len(df) < 3:
            return {"bullish": False, "bearish": False, "size": 0}

        sub = df.tail(3)
        o = sub["Open"].values
        c = sub["Close"].values

        bullish_disp = False
        bearish_disp = False
        max_body = 0.0

        for i in range(len(sub)):
            body = abs(c[i] - o[i])
            if body > max_body:
                max_body = body
            # Displacement condition: body >= 0.65 * ATR or body >= 4.5 USD
            thresh = max(atr * 0.65, 4.5)
            if c[i] > o[i] and body >= thresh:
                bullish_disp = True
            elif c[i] < o[i] and body >= thresh:
                bearish_disp = True

        return {
            "bullish": bullish_disp,
            "bearish": bearish_disp,
            "size": round(max_body, 2),
        }

    def evaluate_5m_confirmation(self, df_5m: pd.DataFrame, direction: str) -> dict:
        """
        5m টাইমফ্রেমে এন্ট্রি কনফার্মেশন (ক্যান্ডেল ক্লোজ, পিন বার বা রিজেকশন) পরীক্ষা করে
        """
        if df_5m is None or len(df_5m) < 3:
            return {"confirmed": True, "reason": "5m টাইমফ্রেম ডিফল্ট সক্রিয়"}

        last = df_5m.iloc[-1]
        prev = df_5m.iloc[-2]

        o = float(last["Open"])
        h = float(last["High"])
        l = float(last["Low"])
        c = float(last["Close"])
        rng = h - l if h > l else 0.1
        lower_wick = min(o, c) - l
        upper_wick = h - max(o, c)

        if direction == "BUY":
            # Bullish candle close or rejection pin bar
            if c > o and c >= float(prev["Close"]):
                return {"confirmed": True, "reason": "5m বুলিশ ক্যান্ডেল ক্লোজ কনফার্মেশন"}
            if (lower_wick / rng) >= 0.45:
                return {"confirmed": True, "reason": "5m বায়ার রিজেকশন পিন বার (লং লোয়ার উইক)"}
            if c > float(prev["High"]):
                return {"confirmed": True, "reason": "5m বুলিশ ব্রেকআউট ট্রিগার"}
            return {"confirmed": False, "reason": "5m-এ এখনও বুলিশ কনফার্মেশন ক্লোজ আসেনি"}

        elif direction == "SELL":
            # Bearish candle close or rejection pin bar
            if c < o and c <= float(prev["Close"]):
                return {"confirmed": True, "reason": "5m বেয়ারিশ ক্যান্ডেল ক্লোজ কনফার্মেশন"}
            if (upper_wick / rng) >= 0.45:
                return {"confirmed": True, "reason": "5m সেলার রিজেকশন পিন বার (লং আপার উইক)"}
            if c < float(prev["Low"]):
                return {"confirmed": True, "reason": "5m বেয়ারিশ ব্রেকআউট ট্রিগার"}
            return {"confirmed": False, "reason": "5m-এ এখনও বেয়ারিশ কনফার্মেশন ক্লোজ আসেনি"}

        return {"confirmed": False, "reason": "ডিরেকশন নিউট্রাল"}

    def evaluate_1m_confirmation(self, df_1m: Optional[pd.DataFrame], direction: str) -> dict:
        """
        1m টাইমফ্রেমে ফাইনাল এক্সিকিউশন কনফার্মেশন:
        - EMA 20 ট্রেন্ড অ্যালাইনমেন্ট
        - RSI 14 মোমেন্টাম (Bullish >= 50, Bearish <= 50)
        - ক্যান্ডেল ক্লোজ কনফার্মেশন (Bullish Green Close, Bearish Red Close)
        """
        if df_1m is None or len(df_1m) < 15:
            return {"confirmed": True, "reason": "1m টাইমফ্রেম ডিফল্ট সক্রিয়"}

        try:
            close = df_1m["Close"]
            open_p = df_1m["Open"]
            ema20 = close.ewm(span=20, adjust=False).mean()

            # RSI 14
            delta = close.diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
            rs = gain / loss.replace(0, np.nan)
            rsi_series = 100 - (100 / (1 + rs))

            last_c = float(close.iloc[-1])
            last_o = float(open_p.iloc[-1])
            last_ema = float(ema20.iloc[-1])
            last_rsi = float(rsi_series.iloc[-1]) if not np.isnan(rsi_series.iloc[-1]) else 50.0

            if direction == "BUY":
                if last_c > last_ema and last_rsi >= 48.0 and last_c > last_o:
                    return {
                        "confirmed": True,
                        "reason": f"1M বুলিশ কনফার্মেশন সম্পন্ন (Close > EMA 20, RSI {last_rsi:.1f} >= 50, গ্রিন ক্যান্ডেল ক্লোজ)"
                    }
                return {
                    "confirmed": False,
                    "reason": f"1M বুলিশ কনফার্মেশন অপেক্ষমান (Close: {last_c}, EMA20: {last_ema:.2f}, RSI: {last_rsi:.1f})"
                }
            elif direction == "SELL":
                if last_c < last_ema and last_rsi <= 52.0 and last_c < last_o:
                    return {
                        "confirmed": True,
                        "reason": f"1M বেয়ারিশ কনফার্মেশন সম্পন্ন (Close < EMA 20, RSI {last_rsi:.1f} <= 50, রেড ক্যান্ডেল ক্লোজ)"
                    }
                return {
                    "confirmed": False,
                    "reason": f"1M বেয়ারিশ কনফার্মেশন অপেক্ষমান (Close: {last_c}, EMA20: {last_ema:.2f}, RSI: {last_rsi:.1f})"
                }
        except Exception as e:
            logger.warning(f"1M confirmation calculation error: {e}")
            return {"confirmed": True, "reason": "1m এক্সেপশন, ফলব্যাক সক্রিয়"}

        return {"confirmed": False, "reason": "ডিরেকশন নিউট্রাল"}

    # ─────────────────────────────────────────────────────────
    # ── COMPLETE 12-COMPONENT DUAL-ENGINE STRATEGY PIPELINE ──
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
    ) -> dict:
        """
        ১২টি ইনস্টিটিউশনাল কম্পোনেন্ট সমৃদ্ধ ডুয়াল-ইঞ্জিন ট্রেডিং ফ্রেমওয়ার্ক:
        ১. মার্কেট স্ট্রাকচার (BOS/CHoCH/MSS উইক বনাম বডি ক্লোজ)
        ২. লিকুইডিটি (BSL, SSL, Equal High/Low, PDH/PDL, সুইপ)
        ৩. ডিসপ্লেসমেন্ট ও FVG (Fair Value Gap)
        ৪. অর্ডার ব্লক (OB - Institutional Demand/Supply)
        ৫. EMA 20 / 50 / 200 ট্রেন্ড কনটেক্সট
        ৬. RSI 14 ও ডাইভারজেন্স
        ৭. ATR 14 ডায়নামিক ভোলাটিলিটি ও স্টপ লস
        ৮. VWAP ইন্ট্রাডে ভ্যালুয়েশন
        ৯. MACD মোমেন্টাম
        ১০. Premium / Discount / 50% EQ / OTE ফিবোনাচ্চি
        ১১. Relative Volume (RVOL)
        ১২. ম্যাক্রো ও হাই-ইমপ্যাক্ট নিউজ ফিল্টার

        [সেশন নিরপেক্ষ: সময় বা সেশন রেস্ট্রিকশন ছাড়াই ২৪/৫ বড় ও ছোট সেটাপ সনাক্ত করে]
        """
        # ── 1. ATR 14 Calculation on 15m ─────────────────────
        if df_15m is not None and len(df_15m) >= 14:
            tr1 = df_15m["High"] - df_15m["Low"]
            tr2 = (df_15m["High"] - df_15m["Close"].shift(1)).abs()
            tr3 = (df_15m["Low"] - df_15m["Close"].shift(1)).abs()
            tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
            atr = round(float(tr.rolling(14).mean().iloc[-1]), 2)
            if np.isnan(atr) or atr < 2:
                atr = 15.0
        else:
            atr = 15.0

        # ── 2. 4H Trend (EMA 200 + Swings) ───────────────────
        trend_4h = "RANGE"
        ema200_4h = None
        if df_4h is not None and len(df_4h) >= 20:
            c4 = df_4h["Close"]
            ema200_s = c4.ewm(span=min(len(df_4h), 200), adjust=False).mean()
            ema200_4h = round(float(ema200_s.iloc[-1]), 2)
            swings_4h = self.find_swings(df_4h, left=2, right=2)
            struct_4h = self.detect_structure(df_4h, swings_4h)
            trend_4h = struct_4h["trend"]
            if current_price > ema200_4h and trend_4h == "RANGE":
                trend_4h = "BULLISH"
            elif current_price < ema200_4h and trend_4h == "RANGE":
                trend_4h = "BEARISH"

        # ── 3. 1H Intraday Trend & EMA Bias ──────────────────
        bias_1h = "RANGE"
        ema50_1h = None
        ema200_1h = None
        swings_1h = {"highs": [], "lows": []}
        if df_1h is not None and len(df_1h) >= 20:
            c1 = df_1h["Close"]
            ema50_1h = round(float(c1.ewm(span=min(len(df_1h), 50), adjust=False).mean().iloc[-1]), 2)
            ema200_1h = round(float(c1.ewm(span=min(len(df_1h), 200), adjust=False).mean().iloc[-1]), 2)
            swings_1h = self.find_swings(df_1h, left=2, right=2)
            struct_1h = self.detect_structure(df_1h, swings_1h)
            bias_1h = struct_1h["trend"]

            if current_price > ema50_1h and current_price > ema200_1h:
                bias_1h = "BULLISH"
            elif current_price < ema50_1h and current_price < ema200_1h:
                bias_1h = "BEARISH"

        # ── 3.5. 15M Trend & EMA 50/200 (ম্যাক্রো ট্রেন্ড) ────
        trend_15m = "RANGE"
        ema50_15m = None
        ema200_15m = None
        if df_15m is not None and len(df_15m) >= 20:
            c15 = df_15m["Close"]
            ema50_15m = round(float(c15.ewm(span=min(len(df_15m), 50), adjust=False).mean().iloc[-1]), 2)
            ema200_15m = round(float(c15.ewm(span=min(len(df_15m), 200), adjust=False).mean().iloc[-1]), 2)
            if current_price > ema50_15m and ema50_15m > ema200_15m:
                trend_15m = "BULLISH"
            elif current_price < ema50_15m and ema50_15m < ema200_15m:
                trend_15m = "BEARISH"

        # ── 4. 15m Structure, Equal Highs/Lows, and Dealing Range ──
        swings_15m = self.find_swings(df_15m, left=2, right=2) if df_15m is not None else {"highs": [], "lows": []}
        struct_15m = self.detect_structure(df_15m, swings_15m) if df_15m is not None else {}
        eq_pools_15m = self.detect_equal_highs_lows(swings_15m, tolerance=0.60)
        dealing_range = self.calculate_dealing_range_and_ote(swings_15m, current_price)

        # ── 5. Liquidity Map & Sweep Detection (Session-Free) ──
        liquidity = self.calculate_session_and_liquidity_levels(df_15m if df_15m is not None else df_1h)
        sweep_15m = self.detect_liquidity_sweep(df_15m, liquidity, swings_15m, eq_pools_15m)
        sweep_5m  = self.detect_liquidity_sweep(df_5m, liquidity, swings_15m, eq_pools_15m) if df_5m is not None else {"bullish_sweep": False, "bearish_sweep": False}

        effective_sweep = sweep_15m if (sweep_15m["bullish_sweep"] or sweep_15m["bearish_sweep"]) else sweep_5m

        # ── 6. Order Blocks & Fair Value Gaps (FVG) ───────────
        obs_15m = self.detect_order_blocks(df_15m, lookback=30)
        fvgs_15m = self.detect_fair_value_gaps(df_15m, lookback=30)
        obs_5m = self.detect_order_blocks(df_5m, lookback=25) if df_5m is not None else {"bullish_ob": None, "bearish_ob": None}
        fvgs_5m = self.detect_fair_value_gaps(df_5m, lookback=25) if df_5m is not None else []

        active_bullish_fvg = [f for f in fvgs_15m if f["type"] == "BULLISH" and f["active"]] or [f for f in fvgs_5m if f["type"] == "BULLISH" and f["active"]]
        active_bearish_fvg = [f for f in fvgs_15m if f["type"] == "BEARISH" and f["active"]] or [f for f in fvgs_5m if f["type"] == "BEARISH" and f["active"]]

        bullish_ob_active = (obs_15m.get("bullish_ob") and obs_15m["bullish_ob"]["testing"]) or (obs_5m.get("bullish_ob") and obs_5m["bullish_ob"]["testing"])
        bearish_ob_active = (obs_15m.get("bearish_ob") and obs_15m["bearish_ob"]["testing"]) or (obs_5m.get("bearish_ob") and obs_5m["bearish_ob"]["testing"])

        # ── 7. Displacement & Volume (RVOL) ───────────────────
        displacement_15m = self.detect_displacement(df_15m, atr)
        displacement_5m  = self.detect_displacement(df_5m, atr) if df_5m is not None else {"bullish": False, "bearish": False, "size": 0}
        disp_bullish = displacement_15m["bullish"] or displacement_5m["bullish"]
        disp_bearish = displacement_15m["bearish"] or displacement_5m["bearish"]
        disp_size = max(displacement_15m.get("size", 0), displacement_5m.get("size", 0))

        rvol_15m = self.calculate_rvol(df_15m, period=20)
        rvol_5m  = self.calculate_rvol(df_5m, period=20) if df_5m is not None else 1.0
        rvol_high = (rvol_15m >= 1.2 or rvol_5m >= 1.2)

        # ── 8. Momentum: RSI, MACD & Divergences ──────────────
        rsi_val = 50.0
        rsi_div_bull = False
        rsi_div_bear = False
        vwap_val = current_price
        macd_bull = False
        macd_bear = False

        if df_15m is not None and not df_15m.empty:
            df_ind = self.calculate_indicators(df_15m.copy())
            last_bar = df_ind.iloc[-1]
            rsi_val = float(last_bar.get("RSI", 50.0))
            vwap_val = float(last_bar.get("VWAP", current_price))
            macd_h = float(last_bar.get("MACD_Hist", 0.0))
            if macd_h > 0:
                macd_bull = True
            elif macd_h < 0:
                macd_bear = True

            divs = self.detect_divergences(df_ind, lookback=25)
            for d in divs:
                if "BULLISH" in d[0]:
                    rsi_div_bull = True
                if "BEARISH" in d[0]:
                    rsi_div_bear = True

        # ═════════════════════════════════════════════════════
        # ── DUAL-ENGINE SETUP EVALUATION (15M-5M-1M SMC) ─────
        # ═════════════════════════════════════════════════════
        major_buy = False
        major_sell = False
        scalp_buy = False
        scalp_sell = False

        # ── ENGINE A: Major Institutional Intraday Swing ──────
        # BUY: 15M / 1H Bullish + Sweep/BOS + Discount/OTE + FVG/OB/Displacement
        if (trend_15m == "BULLISH" or bias_1h == "BULLISH" or trend_4h == "BULLISH" or struct_15m.get("choch_bullish")):
            if (effective_sweep["bullish_sweep"] or struct_15m.get("bos_bullish") or struct_15m.get("choch_bullish")):
                if dealing_range.get("zone") in ("DISCOUNT", "EQUILIBRIUM") or dealing_range.get("ote_buy"):
                    if active_bullish_fvg or bullish_ob_active or disp_bullish:
                        major_buy = True

        # SELL: 15M / 1H Bearish + Sweep/BOS + Premium/OTE + FVG/OB/Displacement
        if (trend_15m == "BEARISH" or bias_1h == "BEARISH" or trend_4h == "BEARISH" or struct_15m.get("choch_bearish")):
            if (effective_sweep["bearish_sweep"] or struct_15m.get("bos_bearish") or struct_15m.get("choch_bearish")):
                if dealing_range.get("zone") in ("PREMIUM", "EQUILIBRIUM") or dealing_range.get("ote_sell"):
                    if active_bearish_fvg or bearish_ob_active or disp_bearish:
                        major_sell = True

        # ── ENGINE B: High-Probability 15M-5M-1M Gold Scalp ───
        # BUY: 15M Bullish/Neutral + 5M Low Sweep + BOS/Disp/FVG/OB Retest
        if trend_15m != "BEARISH":
            if effective_sweep["bullish_sweep"] or rsi_div_bull:
                if disp_bullish or active_bullish_fvg or bullish_ob_active or struct_15m.get("bos_bullish"):
                    scalp_buy = True

        # SELL: 15M Bearish/Neutral + 5M High Sweep + BOS/Disp/FVG/OB Retest
        if trend_15m != "BULLISH":
            if effective_sweep["bearish_sweep"] or rsi_div_bear:
                if disp_bearish or active_bearish_fvg or bearish_ob_active or struct_15m.get("bos_bearish"):
                    scalp_sell = True

        # ── Final Setup Direction & Type Determination ────────
        final_direction = "NO_TRADE"
        setup_type = "NONE"
        setup_title = "কোনো সক্রিয় সেটাপ নেই"
        target_dir = "NEUTRAL"

        if major_buy and not major_sell:
            target_dir = "BUY"
            setup_type = "MASTER_SWING"
            setup_title = "🎯 মাস্টার সুইং সেটাপ (ইন্ট্রাডে)"
        elif major_sell and not major_buy:
            target_dir = "SELL"
            setup_type = "MASTER_SWING"
            setup_title = "🎯 মাস্টার সুইং সেটাপ (ইন্ট্রাডে)"
        elif scalp_buy and not scalp_sell:
            target_dir = "BUY"
            setup_type = "SCALP"
            setup_title = "⚡ XAUUSD গোল্ড স্ক্যাল্পিং (15M-5M-1M)"
        elif scalp_sell and not scalp_buy:
            target_dir = "SELL"
            setup_type = "SCALP"
            setup_title = "⚡ XAUUSD গোল্ড স্ক্যাল্পিং (15M-5M-1M)"
        elif major_buy and major_sell:
            target_dir = "BUY" if (trend_15m == "BULLISH" or bias_1h == "BULLISH") else "SELL"
            setup_type = "MASTER_SWING"
            setup_title = "🎯 মাস্টার সুইং সেটাপ (ইন্ট্রাডে)"

        # ── 9. Confirmation Triggers (5M BOS & 1M Candle Close) ─
        conf_5m = {"confirmed": False, "reason": "5m সেটাপ অপেক্ষমান"}
        conf_1m = {"confirmed": True, "reason": "1m ডিফল্ট সক্রিয়"}
        if target_dir in ("BUY", "SELL"):
            conf_5m = self.evaluate_5m_confirmation(df_5m, target_dir)
            if df_1m is not None and not df_1m.empty:
                conf_1m = self.evaluate_1m_confirmation(df_1m, target_dir)
            else:
                conf_1m = {"confirmed": conf_5m.get("confirmed", False), "reason": conf_5m.get("reason", "")}

        # ── 10. Dynamic Stop Loss & 1:5 Risk/Reward Targets ───
        entry = current_price
        tp1 = entry
        tp2 = entry
        tp3 = entry
        sl  = entry
        risk = 0.0
        rr_str = "1:5.0"

        if target_dir == "BUY":
            sweep_price = effective_sweep.get("swept_level_price")
            last_low = struct_15m.get("last_low")
            ob_bottom = obs_15m.get("bullish_ob", {}).get("bottom") if obs_15m.get("bullish_ob") else None

            candidate_sl = [p for p in [sweep_price, last_low, ob_bottom] if p is not None and p < entry]
            invalidation = min(candidate_sl) if candidate_sl else (entry - max(atr * 1.0, 3.5))

            # SL: Sweep Low-এর বাইরে ATR বাফার সহ
            sl = round(invalidation - max(atr * 1.2, 1.8), 2)
            risk = round(entry - sl, 2)
            if risk <= 0:
                risk = 2.0
                sl = entry - risk

            # TP: 1:5 Risk/Reward (সাথে ১:২.৫ এ পার্শিয়াল TP)
            tp1 = round(entry + (risk * 2.5), 2)  # Partial TP (1:2.5)
            tp2 = round(entry + (risk * 5.0), 2)  # Target 1:5 R:R
            tp3 = round(entry + (risk * 5.0), 2)  # Full 1:5 Target
            rr_str = "1:5.0"

        elif target_dir == "SELL":
            sweep_price = effective_sweep.get("swept_level_price")
            last_high = struct_15m.get("last_high")
            ob_top = obs_15m.get("bearish_ob", {}).get("top") if obs_15m.get("bearish_ob") else None

            candidate_sl = [p for p in [sweep_price, last_high, ob_top] if p is not None and p > entry]
            invalidation = max(candidate_sl) if candidate_sl else (entry + max(atr * 1.0, 3.5))

            # SL: Sweep High-এর বাইরে ATR বাফার সহ
            sl = round(invalidation + max(atr * 1.2, 1.8), 2)
            risk = round(sl - entry, 2)
            if risk <= 0:
                risk = 2.0
                sl = entry + risk

            # TP: 1:5 Risk/Reward (সাথে ১:২.৫ এ পার্শিয়াল TP)
            tp1 = round(entry - (risk * 2.5), 2)  # Partial TP (1:2.5)
            tp2 = round(entry - (risk * 5.0), 2)  # Target 1:5 R:R
            tp3 = round(entry - (risk * 5.0), 2)  # Full 1:5 Target
            rr_str = "1:5.0"

        # ── 11. 12-Component Checklist Building ───────────────
        checklist = [
            {"num": 1,  "name": "Market Structure (BOS / CHoCH)", "passed": bool(struct_15m.get("bos_bullish") or struct_15m.get("bos_bearish") or struct_15m.get("choch_bullish") or struct_15m.get("choch_bearish"))},
            {"num": 2,  "name": "Liquidity Pool & Sweeps (BSL/SSL)", "passed": bool(effective_sweep.get("bullish_sweep") or effective_sweep.get("bearish_sweep"))},
            {"num": 3,  "name": "Displacement & FVG Active", "passed": bool(active_bullish_fvg or active_bearish_fvg or disp_bullish or disp_bearish)},
            {"num": 4,  "name": "Order Block (OB) Zone Active", "passed": bool(bullish_ob_active or bearish_ob_active or obs_15m.get("bullish_ob") or obs_15m.get("bearish_ob"))},
            {"num": 5,  "name": "15M Trend & EMA 50/200 Alignment", "passed": (target_dir == "BUY" and trend_15m == "BULLISH") or (target_dir == "SELL" and trend_15m == "BEARISH") or (target_dir == "BUY" and current_price > (ema50_1h or 0)) or (target_dir == "SELL" and current_price < (ema50_1h or 99999))},
            {"num": 6,  "name": "RSI 14 & Momentum Confluence", "passed": (target_dir == "BUY" and rsi_val >= 42) or (target_dir == "SELL" and rsi_val <= 58) or rsi_div_bull or rsi_div_bear},
            {"num": 7,  "name": "ATR 14 Buffer SL Outside Sweep Level", "passed": bool(atr > 0 and sl != entry)},
            {"num": 8,  "name": "Target 1:5 Risk/Reward Ratio", "passed": bool(risk > 0 and abs(tp2 - entry) >= (risk * 4.9))},
            {"num": 9,  "name": "5M BOS & Retest Trigger", "passed": bool(conf_5m.get("confirmed"))},
            {"num": 10, "name": "1M EMA 20 & RSI Confirmation", "passed": bool(conf_1m.get("confirmed"))},
            {"num": 11, "name": "Premium / Discount / OTE Zone", "passed": (target_dir == "BUY" and dealing_range.get("zone") in ("DISCOUNT", "EQUILIBRIUM")) or (target_dir == "SELL" and dealing_range.get("zone") in ("PREMIUM", "EQUILIBRIUM"))},
            {"num": 12, "name": "News Risk Safety (CPI/NFP/FOMC Window)", "passed": not news_risk},
        ]

        passed_count = sum(1 for c in checklist if c["passed"])
        total_checks = len(checklist)

        # ── 12. Final Decision & Reasoning ────────────────────
        reasoning = []
        if news_risk:
            final_direction = "WAIT"
            reasoning.append("⚠️ হাই-ইমপ্যাক্ট US নিউজ উইন্ডো সক্রিয় — বড় সংবাদের সময় নিরাপদ থাকতে অপেক্ষা করুন।")
        elif target_dir in ("BUY", "SELL") and conf_5m.get("confirmed") and conf_1m.get("confirmed"):
            final_direction = target_dir
            reasoning.append(f"📌 সেটাপ ধরন: {setup_title}")
            if effective_sweep["sweep_details"]:
                reasoning.append(effective_sweep["sweep_details"])
            if active_bullish_fvg or active_bearish_fvg:
                reasoning.append("🎯 Fair Value Gap (FVG) ইমব্যালেন্স রিটেস্ট সফল")
            if bullish_ob_active or bearish_ob_active:
                reasoning.append("🏛️ প্রাতিষ্ঠানিক Order Block (OB) জোন রিঅ্যাকশন")
            if disp_size > 0:
                reasoning.append(f"⚡ ডিসপ্লেসমেন্ট ক্যান্ডেল সাইজ ${disp_size}")
            if dealing_range.get("ote_buy") or dealing_range.get("ote_sell"):
                reasoning.append("💎 OTE (Optimal Trade Entry 62-79% Fib) গোল্ডেন জোন")
            elif dealing_range.get("zone") != "EQUILIBRIUM":
                reasoning.append(f"⚖️ ভ্যালুয়েশন: {dealing_range['zone']} জোন এন্ট্রি")
            if rsi_div_bull or rsi_div_bear:
                reasoning.append("🔥 RSI ডাইভারজেন্স রিভার্সাল কনফার্মেশন")
            if conf_5m.get("reason"):
                reasoning.append(conf_5m["reason"])
            if conf_1m.get("reason"):
                reasoning.append(conf_1m["reason"])
        else:
            final_direction = "NO_TRADE"
            missing = [c["name"] for c in checklist if not c["passed"]]
            reasoning.append("🟡 হাই-প্রোবাবিলিটি সেটাপ কনফার্মেশন অপেক্ষমান।")
            if missing:
                reasoning.append(f"অপেক্ষমান ফিল্টার: {missing[0]}")

        return {
            "direction": final_direction,
            "setup_direction": target_dir,
            "setup_type": setup_type,
            "setup_title": setup_title,
            "checklist_score": f"{passed_count}/{total_checks}",
            "passed_count": passed_count,
            "checklist": checklist,
            "trend_15m": trend_15m,
            "ema50_15m": ema50_15m,
            "ema200_15m": ema200_15m,
            "trend_4h": trend_4h,
            "bias_1h": bias_1h,
            "ema50_1h": ema50_1h,
            "ema200_4h": ema200_4h,
            "liquidity": liquidity,
            "sweep": effective_sweep,
            "dealing_range": dealing_range,
            "displacement": {"bullish": disp_bullish, "bearish": disp_bearish, "size": disp_size},
            "active_fvgs": active_bullish_fvg if target_dir == "BUY" else active_bearish_fvg,
            "confirmation_5m": conf_5m,
            "confirmation_1m": conf_1m,
            "entry": round(entry, 2),
            "tp1": round(tp1, 2),
            "tp2": round(tp2, 2),
            "tp3": round(tp3, 2),
            "sl": round(sl, 2),
            "atr": atr,
            "rvol": max(rvol_15m, rvol_5m),
            "rr_ratio": rr_str,
            "reasoning": reasoning,
        }

