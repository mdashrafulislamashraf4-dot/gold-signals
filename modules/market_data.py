"""
============================================================
  modules/market_data.py
  XAUUSD মার্কেট ডেটা ফেচ করার মডিউল
  Sources: yfinance (Free), Investing.com RSS
============================================================
"""

import logging
import time
from datetime import datetime, timedelta
from typing import Optional

import pandas as pd
import requests
import yfinance as yf

logger = logging.getLogger(__name__)


class MarketDataFetcher:
    """গোল্ড মার্কেটের সব ধরনের ডেটা ফেচ করে"""

    GOLD_SYMBOLS = ["GC=F", "XAUUSD=X", "GLD"]
    CORRELATED   = {
        "DXY":  "DX-Y.NYB",   # US Dollar Index
        "SPX":  "^GSPC",      # S&P 500
        "US10Y": "^TNX",      # 10-Year Treasury
        "VIX":  "^VIX",       # Volatility Index
        "OIL":  "CL=F",       # Crude Oil
        "SILVER": "SI=F",     # Silver
    }

    def __init__(self):
        self._price_cache: dict = {}
        self._cache_time: dict  = {}
        self.cache_ttl = 60  # seconds

    # ─────────────────────────────────────────────────────────
    # Current Price
    # ─────────────────────────────────────────────────────────
    def get_current_price(self) -> Optional[float]:
        """
        বর্তমান গোল্ড প্রাইস ফেচ করে — সরাসরি TradingView OANDA:XAUUSD থেকে
        """
        # 1) Try TradingView CFD Scanner API directly for OANDA:XAUUSD (100% exact match)
        try:
            url = "https://scanner.tradingview.com/cfd/scan"
            payload = {
                "symbols": {"tickers": ["OANDA:XAUUSD"]},
                "columns": ["close"]
            }
            resp = requests.post(url, json=payload, headers={"User-Agent": "Mozilla/5.0"}, timeout=6)
            if resp.ok:
                data = resp.json()
                rows = data.get("data", [])
                if rows and len(rows[0].get("d", [])) > 0:
                    price = rows[0]["d"][0]
                    if price and price > 0:
                        logger.info(f"Gold spot price from TradingView (OANDA:XAUUSD): {price}")
                        return round(float(price), 2)
        except Exception as e:
            logger.warning(f"TradingView scanner fetch failed: {e}")

        # 2) Try Gold-API spot price (Free live spot)
        try:
            url = "https://api.gold-api.com/price/XAU"
            resp = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=6)
            if resp.ok:
                data = resp.json()
                price = data.get("price")
                if price and price > 0:
                    logger.info(f"Gold spot price from Gold-API: {price}")
                    return round(float(price), 2)
        except Exception as e:
            logger.warning(f"Gold-API fetch failed: {e}")

        # 3) Fallback to yfinance GC=F
        for sym in self.GOLD_SYMBOLS:
            try:
                ticker = yf.Ticker(sym)
                price  = ticker.fast_info.last_price
                if price and price > 0:
                    logger.info(f"Gold price from {sym}: {price}")
                    return round(float(price), 2)
            except Exception as e:
                logger.warning(f"yfinance {sym} failed: {e}")

        return None

    # ─────────────────────────────────────────────────────────
    # OHLCV Historical Data
    # ─────────────────────────────────────────────────────────
    def get_ohlcv(self, timeframe: str = "1h", bars: int = 200) -> Optional[pd.DataFrame]:
        """
        OHLCV ক্যান্ডেল ডেটা ফেচ করে এবং Spot Gold (OANDA:XAUUSD) প্রাইসের সাথে সিঙ্ক করে
        """
        tf_map = {
            "1m": "1m", "5m": "5m", "15m": "15m",
            "30m": "30m", "1h": "60m", "4h": "60m",
            "1d": "1d", "1w": "1wk",
        }
        yf_tf = tf_map.get(timeframe, "60m")

        if yf_tf in ("1m",):
            period = "7d"
        elif yf_tf in ("5m", "15m", "30m", "60m"):
            period = "60d"
        else:
            period = "2y"

        spot_price = self.get_current_price()

        for sym in self.GOLD_SYMBOLS:
            try:
                df = yf.download(
                    sym,
                    period=period,
                    interval=yf_tf,
                    auto_adjust=True,
                    progress=False,
                )
                if df is not None and not df.empty:
                    df.columns = [c[0] if isinstance(c, tuple) else c for c in df.columns]
                    df = df.rename(columns=str.capitalize)
                    df = df[["Open", "High", "Low", "Close", "Volume"]].dropna()
                    df = df.tail(bars)

                    # Align with Spot Price if using futures data
                    if spot_price and not df.empty:
                        last_close = df["Close"].iloc[-1]
                        diff = last_close - spot_price
                        # If difference is more than 3 dollars, calibrate to spot
                        if abs(diff) > 3.0:
                            df["Open"]  = (df["Open"] - diff).round(2)
                            df["High"]  = (df["High"] - diff).round(2)
                            df["Low"]   = (df["Low"] - diff).round(2)
                            df["Close"] = (df["Close"] - diff).round(2)

                    logger.info(f"OHLCV fetched & calibrated: {sym} {timeframe} — {len(df)} bars")
                    return df
            except Exception as e:
                logger.warning(f"OHLCV fetch failed for {sym}/{timeframe}: {e}")

        return None

    # ─────────────────────────────────────────────────────────
    # Correlated Assets
    # ─────────────────────────────────────────────────────────
    def get_correlated_assets(self) -> dict:
        """
        Gold-correlated assets ডেটা ফেচ করে (DXY, SPX, etc.)
        Returns dict with last price and daily change %
        """
        result = {}
        for name, sym in self.CORRELATED.items():
            try:
                t     = yf.Ticker(sym)
                info  = t.fast_info
                price = getattr(info, "last_price", None)
                prev  = getattr(info, "previous_close", None)
                if price and prev:
                    chg = round(((price - prev) / prev) * 100, 2)
                    result[name] = {"price": round(float(price), 4), "change_pct": chg}
            except Exception as e:
                logger.warning(f"Correlated asset {name} failed: {e}")

        return result

    # ─────────────────────────────────────────────────────────
    # Market Status
    # ─────────────────────────────────────────────────────────
    def is_market_open(self) -> bool:
        """Gold futures market খোলা কি না চেক করে"""
        now = datetime.utcnow()
        weekday = now.weekday()  # 0=Mon, 6=Sun

        # Gold trades Sunday 6PM – Friday 5PM ET (approx)
        if weekday == 5:  # Saturday
            return False

        # Friday after 5PM ET (21:00 UTC) is closed
        if weekday == 4 and now.hour >= 21:
            return False

        # Sunday before 6PM ET (22:00 UTC) is closed
        if weekday == 6 and now.hour < 22:
            return False

        return True

    # ─────────────────────────────────────────────────────────
    # Key Levels (Support / Resistance)
    # ─────────────────────────────────────────────────────────
    def get_key_levels(self, df: pd.DataFrame, n: int = 5) -> dict:
        """সাপোর্ট এবং রেজিস্ট্যান্স লেভেল বের করে"""
        if df is None or df.empty:
            return {"support": [], "resistance": []}

        highs  = df["High"].values
        lows   = df["Low"].values
        closes = df["Close"].values

        # Pivot Points (Classic)
        last_high  = highs[-1]
        last_low   = lows[-1]
        last_close = closes[-1]

        pivot = (last_high + last_low + last_close) / 3
        r1    = 2 * pivot - last_low
        r2    = pivot + (last_high - last_low)
        r3    = last_high + 2 * (pivot - last_low)
        s1    = 2 * pivot - last_high
        s2    = pivot - (last_high - last_low)
        s3    = last_low - 2 * (last_high - pivot)

        # Recent swing highs/lows
        window = 10
        swing_highs = []
        swing_lows  = []
        for i in range(window, len(highs) - window):
            if highs[i] == max(highs[i - window : i + window + 1]):
                swing_highs.append(round(highs[i], 2))
            if lows[i] == min(lows[i - window : i + window + 1]):
                swing_lows.append(round(lows[i], 2))

        return {
            "pivot":      round(pivot, 2),
            "resistance": sorted(set([round(r1,2), round(r2,2), round(r3,2)] + swing_highs[-3:]), reverse=True),
            "support":    sorted(set([round(s1,2), round(s2,2), round(s3,2)] + swing_lows[-3:]), reverse=True),
        }
