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
        মার্কেট স্ট্রাকচার (HH/HL, LH/LL, BOS, CHoCH) বিশ্লেষণ করে
        """
        highs = swings.get("highs", [])
        lows = swings.get("lows", [])

        trend = "RANGE"
        bos_bullish = False
        bos_bearish = False
        choch_bullish = False
        choch_bearish = False

        if len(highs) >= 2 and len(lows) >= 2:
            h1, h2 = highs[-2]["price"], highs[-1]["price"]
            l1, l2 = lows[-2]["price"], lows[-1]["price"]

            if h2 > h1 and l2 >= l1:
                trend = "BULLISH"
            elif h2 <= h1 and l2 < l1:
                trend = "BEARISH"
            else:
                trend = "RANGE"

            # BOS check with current close
            cur_close = float(df["Close"].iloc[-1])
            last_sh = highs[-1]["price"]
            last_sl = lows[-1]["price"]

            if cur_close > last_sh:
                bos_bullish = True
            if cur_close < last_sl:
                bos_bearish = True

            # CHoCH check: Counter-trend break
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
            "last_high": highs[-1]["price"] if highs else None,
            "last_low": lows[-1]["price"] if lows else None,
        }

    def detect_fair_value_gaps(self, df: pd.DataFrame, lookback: int = 25) -> list:
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
                # Check if retested by subsequent candles
                retested = False
                for j in range(i + 1, len(sub)):
                    if l[j] <= gap_top:
                        retested = True
                        break
                active = cur_price >= gap_bottom - 1.0
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
                active = cur_price <= gap_top + 1.0
                fvgs.append({
                    "type": "BEARISH",
                    "top": gap_top,
                    "bottom": gap_bottom,
                    "retested": retested,
                    "active": active,
                    "bar_index": i,
                })

        return fvgs

    def detect_order_blocks(self, df: pd.DataFrame, lookback: int = 25) -> dict:
        """
        অর্ডার ব্লক (Demand ও Supply জোন) চিহ্নিত করে
        """
        if df is None or len(df) < 5:
            return {"bullish_ob": None, "bearish_ob": None}

        sub = df.tail(lookback).copy()
        o = sub["Open"].values
        h = sub["High"].values
        l = sub["Low"].values
        c = sub["Close"].values

        bullish_ob = None
        bearish_ob = None

        # Look for last opposite candle before strong displacement
        for i in range(len(sub) - 4, 1, -1):
            body_next = abs(c[i + 1] - o[i + 1])
            body_next2 = abs(c[i + 2] - o[i + 2])

            # Bullish OB: Bearish candle followed by strong bullish run
            if c[i] < o[i] and c[i + 1] > o[i + 1] and (c[i + 1] > h[i] or c[i + 2] > h[i]):
                if not bullish_ob:
                    bullish_ob = {
                        "top": round(float(h[i]), 2),
                        "bottom": round(float(l[i]), 2),
                        "candle_type": "BEARISH",
                    }

            # Bearish OB: Bullish candle followed by strong bearish run
            if c[i] > o[i] and c[i + 1] < o[i + 1] and (c[i + 1] < l[i] or c[i + 2] < l[i]):
                if not bearish_ob:
                    bearish_ob = {
                        "top": round(float(h[i]), 2),
                        "bottom": round(float(l[i]), 2),
                        "candle_type": "BULLISH",
                    }

            if bullish_ob and bearish_ob:
                break

        return {"bullish_ob": bullish_ob, "bearish_ob": bearish_ob}

    def calculate_session_and_liquidity_levels(self, df: pd.DataFrame, timezone_str: str = "Asia/Dhaka") -> dict:
        """
        Session Timing ও Liquidity Map তৈরি করে:
        - Previous Day High (PDH) ও Previous Day Low (PDL)
        - Asian Session High ও Low (বাংলাদেশ সময় ০৬:০০ - ১৩:০০)
        - বর্তমান ট্রেডিং সেশন
        """
        import pytz
        tz = pytz.timezone(timezone_str)

        res = {
            "pdh": None,
            "pdl": None,
            "asian_high": None,
            "asian_low": None,
            "current_session": "অফ-সেশন",
            "session_code": "OFF",
        }

        if df is None or df.empty:
            return res

        try:
            # Convert timezone
            df_local = df.copy()
            if df_local.index.tz is None:
                df_local.index = df_local.index.tz_localize("UTC").tz_convert(tz)
            else:
                df_local.index = df_local.index.tz_convert(tz)

            now_local = datetime.now(tz)
            hour = now_local.hour
            minute = now_local.minute
            current_time_dec = hour + (minute / 60.0)

            # Determine Session
            if 6.0 <= current_time_dec < 13.0:
                res["current_session"] = "এশিয়ান সেশন (Asian Session)"
                res["session_code"] = "ASIA"
            elif 13.0 <= current_time_dec < 18.0:
                res["current_session"] = "লন্ডন সেশন (London Session)"
                res["session_code"] = "LONDON"
            elif 18.0 <= current_time_dec < 22.5:
                res["current_session"] = "লন্ডন–নিউ ইয়র্ক ওভারল্যাপ (London-NY Overlap)"
                res["session_code"] = "LONDON_NY_OVERLAP"
            elif 22.5 <= current_time_dec or current_time_dec < 3.0:
                res["current_session"] = "নিউ ইয়র্ক সেশন (New York Session)"
                res["session_code"] = "NY"
            else:
                res["current_session"] = "লেট নাইট কুল-অফ (Off-hours)"
                res["session_code"] = "OFF"

            # Find PDH / PDL (Previous Day High/Low)
            dates = sorted(list(set(d.date() for d in df_local.index)))
            today = now_local.date()
            prev_dates = [d for d in dates if d < today]

            if prev_dates:
                last_day = prev_dates[-1]
                day_df = df_local[df_local.index.date == last_day]
                if not day_df.empty:
                    res["pdh"] = round(float(day_df["High"].max()), 2)
                    res["pdl"] = round(float(day_df["Low"].min()), 2)

            # Find Asian Session High/Low (06:00 to 13:00 local time)
            # Check today's Asian session, or previous active day's Asian session
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

    def detect_liquidity_sweep(self, df_15m: pd.DataFrame, liquidity: dict, swings: dict = None) -> dict:
        """
        লিকুইডিটি সুইপ (Liquidity Sweep) নিশ্চিত করে:
        দাম গুরুত্বপূর্ণ লেভেলের ওপরে/নিচে গিয়ে উইক (Wick) তৈরি করে আবার ভিতরে ক্লোজ হয়েছে কি না
        """
        res = {
            "bullish_sweep": False,
            "bearish_sweep": False,
            "swept_level_name": "",
            "swept_level_price": None,
            "sweep_details": "",
        }

        if df_15m is None or len(df_15m) < 4:
            return res

        recent_bars = df_15m.tail(4)
        c = recent_bars["Close"].values
        h = recent_bars["High"].values
        l = recent_bars["Low"].values

        cur_close = c[-1]
        pdl = liquidity.get("pdl")
        pdh = liquidity.get("pdh")
        asian_low = liquidity.get("asian_low")
        asian_high = liquidity.get("asian_high")

        # Bullish Sweep (Sell-side Liquidity SSL Swept)
        # Low went below level, but recent close is back above
        ssl_levels = []
        if asian_low:
            ssl_levels.append(("Asian Low (SSL)", asian_low))
        if pdl:
            ssl_levels.append(("Previous Day Low (PDL)", pdl))
        if swings and swings.get("lows"):
            ssl_levels.append(("Major Swing Low", swings["lows"][-1]["price"]))

        for name, lvl in ssl_levels:
            # Check if any recent low dipped below, but current close is above
            min_low = min(l)
            if min_low < lvl and cur_close > lvl:
                res["bullish_sweep"] = True
                res["swept_level_name"] = name
                res["swept_level_price"] = lvl
                res["sweep_details"] = f"🟢 লিকুইডিটি সুইপ: {name} (${lvl}) ব্রেক করে উইক ফেলে আবার উপরে ফিরে এসেছে"
                return res

        # Bearish Sweep (Buy-side Liquidity BSL Swept)
        bsl_levels = []
        if asian_high:
            bsl_levels.append(("Asian High (BSL)", asian_high))
        if pdh:
            bsl_levels.append(("Previous Day High (PDH)", pdh))
        if swings and swings.get("highs"):
            bsl_levels.append(("Major Swing High", swings["highs"][-1]["price"]))

        for name, lvl in bsl_levels:
            max_high = max(h)
            if max_high > lvl and cur_close < lvl:
                res["bearish_sweep"] = True
                res["swept_level_name"] = name
                res["swept_level_price"] = lvl
                res["sweep_details"] = f"🔴 লিকুইডিটি সুইপ: {name} (${lvl}) ব্রেক করে ফেকআউট উইক ফেলে আবার নিচে ফিরে এসেছে"
                return res

        return res

    def detect_displacement(self, df_15m: pd.DataFrame, atr: float) -> dict:
        """
        ইনস্টিটিউশনাল ডিসপ্লেসমেন্ট (Displacement) ক্যান্ডেল ডিটেক্ট করে
        """
        if df_15m is None or len(df_15m) < 4:
            return {"bullish": False, "bearish": False, "size": 0}

        sub = df_15m.tail(3)
        o = sub["Open"].values
        c = sub["Close"].values

        bullish_disp = False
        bearish_disp = False
        max_body = 0.0

        for i in range(len(sub)):
            body = abs(c[i] - o[i])
            if body > max_body:
                max_body = body
            # Displacement condition: body >= 0.7 * ATR or body >= 6.0 USD
            thresh = max(atr * 0.7, 6.0)
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
        5m টাইমফ্রেমে এন্ট্রি কনফার্মেশন ও রিজেকশন পরীক্ষা করে
        """
        if df_5m is None or len(df_5m) < 3:
            return {"confirmed": False, "reason": "5m ডেটা অপ্রতুল"}

        last = df_5m.iloc[-1]
        prev = df_5m.iloc[-2]

        o = float(last["Open"])
        h = float(last["High"])
        l = float(last["Low"])
        c = float(last["Close"])
        rng = h - l if h > l else 0.1
        body = abs(c - o)
        lower_wick = min(o, c) - l
        upper_wick = h - max(o, c)

        if direction == "BUY":
            # Bullish candle close or rejection pin bar
            if c > o and c > float(prev["Close"]):
                return {"confirmed": True, "reason": "5m বুলিশ কনফার্মেশন ক্যান্ডেল ক্লোজ"}
            if lower_wick / rng >= 0.5:
                return {"confirmed": True, "reason": "5m বুলিশ রিজেকশন পিন বার (বায়ার প্রেসার)"}
            return {"confirmed": False, "reason": "5m-এ বুলিশ ক্যান্ডেল কনফার্মেশন এখনও আসেনি"}

        elif direction == "SELL":
            # Bearish candle close or rejection pin bar
            if c < o and c < float(prev["Close"]):
                return {"confirmed": True, "reason": "5m বেয়ারিশ কনফার্মেশন ক্যান্ডেল ক্লোজ"}
            if upper_wick / rng >= 0.5:
                return {"confirmed": True, "reason": "5m বেয়ারিশ রিজেকশন পিন বার (সেলার প্রেসার)"}
            return {"confirmed": False, "reason": "5m-এ বেয়ারিশ ক্যান্ডেল কনফার্মেশন এখনও আসেনি"}

        return {"confirmed": False, "reason": "ডিরেকশন নিউট্রাল"}

    # ─────────────────────────────────────────────────────────
    # ── COMPLETE 9-STEP MASTER STRATEGY PIPELINE ─────────────
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
    ) -> dict:
        """
        ব্যবহারকারীর সম্পূর্ণ 'XAUUSD Intraday Master Strategy' এক্সিকিউট করে:
        4H Trend -> 1H Intraday Bias -> 15m Setup (Sweep + BOS + FVG) -> 5m Entry Trigger -> 9-step Checklist
        """
        checklist = [
            {"num": 1, "task": "Economic Calendar ও High-impact News Time দেখা", "passed": not news_risk},
            {"num": 2, "task": "4H Trend ও গুরুত্বপূর্ণ Swing চিহ্নিত করা", "passed": False},
            {"num": 3, "task": "1H Intraday Bias নির্ধারণ", "passed": False},
            {"num": 4, "task": "PDH/PDL ও Session High/Low মার্ক করা", "passed": False},
            {"num": 5, "task": "15m-এ Liquidity Sweep ও Structure Setup খোঁজা", "passed": False},
            {"num": 6, "task": "5m-এ Entry Confirmation-এর অপেক্ষা", "passed": False},
            {"num": 7, "task": "SL, TP, Lot Size ও R:R যাচাই (কমপক্ষে 1:2)", "passed": False},
            {"num": 8, "task": "News Risk ও Spread সহনশীলতা যাচাই", "passed": not news_risk},
            {"num": 9, "task": "Entry-এর কারণ ও ফলাফল Journal-এ প্রস্তুত করা", "passed": True},
        ]

        # ── 1. ATR Calculation on 15m ─────────────────────────
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

        # ── 2. 4H Trend Analysis (Market Direction) ───────────
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
            checklist[1]["passed"] = True

        # ── 3. 1H Intraday Bias Analysis ───────────────────────
        bias_1h = "RANGE"
        ema50_1h = None
        ema200_1h = None
        if df_1h is not None and len(df_1h) >= 20:
            c1 = df_1h["Close"]
            ema50_1h = round(float(c1.ewm(span=min(len(df_1h), 50), adjust=False).mean().iloc[-1]), 2)
            ema200_1h = round(float(c1.ewm(span=min(len(df_1h), 200), adjust=False).mean().iloc[-1]), 2)
            swings_1h = self.find_swings(df_1h, left=2, right=2)
            struct_1h = self.detect_structure(df_1h, swings_1h)
            bias_1h = struct_1h["trend"]

            # Support by EMAs
            if current_price > ema50_1h and current_price > ema200_1h:
                bias_1h = "BULLISH"
            elif current_price < ema50_1h and current_price < ema200_1h:
                bias_1h = "BEARISH"

            if bias_1h != "RANGE":
                checklist[2]["passed"] = True

        # ── 4. Liquidity Map (PDH/PDL, Asian High/Low, Session) ─
        liquidity = self.calculate_session_and_liquidity_levels(df_15m if df_15m is not None else df_1h)
        if liquidity.get("pdh") or liquidity.get("asian_high"):
            checklist[3]["passed"] = True

        # ── 5. 15m Setup Identification (Sweep + BOS + FVG) ───
        swings_15m = self.find_swings(df_15m, left=2, right=2) if df_15m is not None else {"highs": [], "lows": []}
        struct_15m = self.detect_structure(df_15m, swings_15m) if df_15m is not None else {}
        sweep = self.detect_liquidity_sweep(df_15m, liquidity, swings_15m)
        displacement = self.detect_displacement(df_15m, atr)
        fvgs = self.detect_fair_value_gaps(df_15m)
        obs = self.detect_order_blocks(df_15m)

        active_bullish_fvg = [f for f in fvgs if f["type"] == "BULLISH" and f["active"]]
        active_bearish_fvg = [f for f in fvgs if f["type"] == "BEARISH" and f["active"]]

        bullish_setup_ready = False
        bearish_setup_ready = False

        # Bullish Setup Conditions:
        # A. Bullish Sweep OR at least Bullish Structure break (CHoCH / BOS)
        # B. Bullish Displacement OR Bullish FVG
        # C. Conforms with higher timeframe bias (not strictly opposing 4H strong trend)
        if (sweep["bullish_sweep"] or struct_15m.get("choch_bullish") or struct_15m.get("bos_bullish")):
            if displacement["bullish"] or active_bullish_fvg:
                bullish_setup_ready = True

        if (sweep["bearish_sweep"] or struct_15m.get("choch_bearish") or struct_15m.get("bos_bearish")):
            if displacement["bearish"] or active_bearish_fvg:
                bearish_setup_ready = True

        if bullish_setup_ready or bearish_setup_ready:
            checklist[4]["passed"] = True

        # ── 6. 5m Confirmation Trigger ─────────────────────────
        setup_direction = "NEUTRAL"
        if bullish_setup_ready and not bearish_setup_ready:
            setup_direction = "BUY"
        elif bearish_setup_ready and not bullish_setup_ready:
            setup_direction = "SELL"
        elif bullish_setup_ready and bearish_setup_ready:
            # Tie breaker: Higher timeframe bias
            setup_direction = "BUY" if bias_1h == "BULLISH" or trend_4h == "BULLISH" else "SELL"

        conf_5m = {"confirmed": False, "reason": "No setup"}
        if setup_direction in ("BUY", "SELL"):
            conf_5m = self.evaluate_5m_confirmation(df_5m, setup_direction)
            if conf_5m["confirmed"]:
                checklist[5]["passed"] = True

        # ── 7. Exact SL, TP & R:R Calculations ─────────────────
        entry = current_price
        tp1 = entry
        tp2 = entry
        tp3 = entry
        sl = entry
        rr_str = "1:2.0"

        if setup_direction == "BUY":
            # SL placed below the sweep low or nearest swing low with buffer
            sweep_price = sweep.get("swept_level_price")
            last_low = struct_15m.get("last_low")
            invalidation = min([p for p in [sweep_price, last_low] if p is not None] or [entry - atr * 1.5])
            sl = round(invalidation - max(atr * 0.4, 2.5), 2)
            risk = entry - sl
            if risk <= 0:
                risk = max(atr * 1.0, 5.0)
                sl = round(entry - risk, 2)

            # Targets based on BSL / Session High / R:R
            target_high = liquidity.get("asian_high") or liquidity.get("pdh")
            if target_high and target_high > entry + risk * 1.2:
                tp1 = round(entry + risk * 1.5, 2)
                tp2 = round(target_high, 2)
                tp3 = round(target_high + risk * 1.5, 2)
            else:
                tp1 = round(entry + risk * 1.5, 2)
                tp2 = round(entry + risk * 2.5, 2)
                tp3 = round(entry + risk * 4.0, 2)

            rr_val = round((tp2 - entry) / risk, 1)
            rr_str = f"1:{rr_val}"
            if rr_val >= 1.8:
                checklist[6]["passed"] = True

        elif setup_direction == "SELL":
            sweep_price = sweep.get("swept_level_price")
            last_high = struct_15m.get("last_high")
            invalidation = max([p for p in [sweep_price, last_high] if p is not None] or [entry + atr * 1.5])
            sl = round(invalidation + max(atr * 0.4, 2.5), 2)
            risk = sl - entry
            if risk <= 0:
                risk = max(atr * 1.0, 5.0)
                sl = round(entry + risk, 2)

            target_low = liquidity.get("asian_low") or liquidity.get("pdl")
            if target_low and target_low < entry - risk * 1.2:
                tp1 = round(entry - risk * 1.5, 2)
                tp2 = round(target_low, 2)
                tp3 = round(target_low - risk * 1.5, 2)
            else:
                tp1 = round(entry - risk * 1.5, 2)
                tp2 = round(entry - risk * 2.5, 2)
                tp3 = round(entry - risk * 4.0, 2)

            rr_val = round((entry - tp2) / risk, 1)
            rr_str = f"1:{rr_val}"
            if rr_val >= 1.8:
                checklist[6]["passed"] = True

        # ── 8. Calculate Final Checklist Score ─────────────────
        passed_count = sum(1 for c in checklist if c["passed"])
        total_checks = len(checklist)

        # Decision Logic: Strict "No Setup = No Trade"
        final_direction = "NO_TRADE"
        reasoning = []

        if news_risk:
            final_direction = "WAIT"
            reasoning.append("⚠️ হাই-ইমপ্যাক্ট US নিউজ উইন্ডো সক্রিয় — বড় সংবাদের সময় এন্ট্রি ঝুঁকি এড়াতে অপেক্ষা করুন।")
        elif passed_count >= 7 and setup_direction in ("BUY", "SELL") and conf_5m["confirmed"]:
            final_direction = setup_direction
            if sweep["sweep_details"]:
                reasoning.append(sweep["sweep_details"])
            if displacement.get("bullish") or displacement.get("bearish"):
                reasoning.append(f"⚡ ইনস্টিটিউশনাল ডিসপ্লেসমেন্ট ক্যান্ডেল সাইজ ${displacement['size']}")
            if active_bullish_fvg or active_bearish_fvg:
                reasoning.append("🎯 Fair Value Gap (FVG) রিটেস্ট সম্পন্ন")
            reasoning.append(conf_5m["reason"])
            reasoning.append(f"📈 4H ডিরেকশন: {trend_4h} | 1H ইন্ট্রাডে বায়াস: {bias_1h}")
        else:
            final_direction = "NO_TRADE"
            # State what is missing
            missing = [c["task"] for c in checklist if not c["passed"]]
            reasoning.append("🟡 পারফেক্ট ইনস্টিটিউশনাল সেটআপ এখনও তৈরি হয়নি (No Trade)।")
            if missing:
                reasoning.append(f"অপেক্ষমান ধাপ: {missing[0]}")

        return {
            "direction": final_direction,
            "setup_direction": setup_direction,
            "checklist_score": f"{passed_count}/{total_checks}",
            "passed_count": passed_count,
            "checklist": checklist,
            "trend_4h": trend_4h,
            "bias_1h": bias_1h,
            "ema50_1h": ema50_1h,
            "ema200_4h": ema200_4h,
            "liquidity": liquidity,
            "sweep": sweep,
            "displacement": displacement,
            "fvgs": fvgs,
            "active_fvgs": active_bullish_fvg if setup_direction == "BUY" else active_bearish_fvg,
            "confirmation_5m": conf_5m,
            "entry": round(entry, 2),
            "tp1": round(tp1, 2),
            "tp2": round(tp2, 2),
            "tp3": round(tp3, 2),
            "sl": round(sl, 2),
            "atr": atr,
            "rr_ratio": rr_str,
            "reasoning": reasoning,
        }
