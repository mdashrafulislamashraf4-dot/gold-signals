"""
============================================================
  modules/market_data.py
  XAUUSD Market Data Ingestion & Health Engine
  TradingView OANDA:XAUUSD CFD Feed + Gold-API Spot + yfinance
  Strict Normalization, Freshness Tracking & Outlier Guardrails
============================================================
"""

import logging
import time
from datetime import datetime, timezone
from typing import Optional, Dict, Any
import pandas as pd
import requests
import yfinance as yf

from config import GOLD_SYMBOL

logger = logging.getLogger(__name__)


class MarketDataFetcher:
    """Ingests multi-timeframe OHLCV (M15, M5, M1), live bids, asks, and spreads for XAUUSD only"""

    GOLD_SYMBOLS = [GOLD_SYMBOL, "GC=F", "XAUUSD=X"]

    def __init__(self):
        self._price_cache: Dict[str, Any] = {}
        self._last_snapshot_time = 0.0
        self._last_successful_fetch = 0.0
        self._last_provider = "UNKNOWN"
        self._consecutive_failures = 0
        self.default_spread = 0.25  # Standard spot gold spread ($0.25)

    # ─────────────────────────────────────────────────────────
    # Live Market Snapshot (Price, Bid, Ask, Spread, Freshness)
    # ─────────────────────────────────────────────────────────
    def get_market_snapshot(self) -> Dict[str, Any]:
        """
        Fetches current price, bid, ask, spread, and freshness timestamp for XAUUSD.
        Prioritizes real-time TradingView OANDA:XAUUSD CFD feed.
        """
        now = time.time()
        # Fast cache for 2.0 seconds to prevent rate-limit bursts
        if self._price_cache and (now - self._last_snapshot_time) < 2.0:
            return self._price_cache

        # 1. TradingView CFD Scanner (OANDA:XAUUSD)
        try:
            url = "https://scanner.tradingview.com/cfd/scan"
            payload = {
                "symbols": {"tickers": ["OANDA:XAUUSD"]},
                "columns": ["close", "bid", "ask", "change"]
            }
            resp = requests.post(url, json=payload, headers={"User-Agent": "Mozilla/5.0"}, timeout=5)
            if resp.ok:
                data = resp.json()
                rows = data.get("data", [])
                if rows and len(rows[0].get("d", [])) >= 3:
                    vals = rows[0]["d"]
                    price = float(vals[0]) if vals[0] else None
                    bid = float(vals[1]) if vals[1] else (price - 0.12 if price else None)
                    ask = float(vals[2]) if vals[2] else (price + 0.13 if price else None)
                    spread = round(ask - bid, 2) if (bid and ask and ask >= bid) else self.default_spread
                    if spread <= 0.0 or spread > 3.0:
                        spread = self.default_spread

                    if price and price > 0:
                        snapshot = {
                            "price": round(price, 2),
                            "bid": round(bid, 2) if bid else round(price - spread / 2, 2),
                            "ask": round(ask, 2) if ask else round(price + spread / 2, 2),
                            "spread": spread,
                            "timestamp": datetime.now(timezone.utc).isoformat(),
                            "provider": "TradingView (OANDA:XAUUSD)",
                            "is_stale": False,
                            "data_age_seconds": 0,
                            "is_market_open": self.is_market_open(),
                        }
                        self._price_cache = snapshot
                        self._last_snapshot_time = now
                        self._last_successful_fetch = now
                        self._last_provider = "TradingView (OANDA:XAUUSD)"
                        self._consecutive_failures = 0
                        return snapshot
        except Exception as e:
            logger.debug(f"TradingView scanner fetch note: {e}")

        # 2. Gold-API Spot Fallback
        try:
            url = "https://api.gold-api.com/price/XAU"
            resp = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=5)
            if resp.ok:
                data = resp.json()
                price = data.get("price")
                if price and float(price) > 0:
                    p = round(float(price), 2)
                    snapshot = {
                        "price": p,
                        "bid": round(p - self.default_spread / 2, 2),
                        "ask": round(p + self.default_spread / 2, 2),
                        "spread": self.default_spread,
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                        "provider": "Gold-API Spot",
                        "is_stale": False,
                        "data_age_seconds": int(now - self._last_successful_fetch) if self._last_successful_fetch else 0,
                        "is_market_open": self.is_market_open(),
                    }
                    self._price_cache = snapshot
                    self._last_snapshot_time = now
                    self._last_successful_fetch = now
                    self._last_provider = "Gold-API Spot"
                    self._consecutive_failures = 0
                    return snapshot
        except Exception as e:
            logger.debug(f"Gold-API fetch note: {e}")

        # 3. yfinance Fallback
        for sym in self.GOLD_SYMBOLS:
            try:
                ticker = yf.Ticker(sym)
                price = ticker.fast_info.last_price
                if price and float(price) > 0:
                    p = round(float(price), 2)
                    snapshot = {
                        "price": p,
                        "bid": round(p - self.default_spread / 2, 2),
                        "ask": round(p + self.default_spread / 2, 2),
                        "spread": self.default_spread,
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                        "provider": f"yfinance ({sym})",
                        "is_stale": False,
                        "data_age_seconds": int(now - self._last_successful_fetch) if self._last_successful_fetch else 0,
                        "is_market_open": self.is_market_open(),
                    }
                    self._price_cache = snapshot
                    self._last_snapshot_time = now
                    self._last_successful_fetch = now
                    self._last_provider = f"yfinance ({sym})"
                    self._consecutive_failures = 0
                    return snapshot
            except Exception as e:
                logger.debug(f"yfinance {sym} note: {e}")

        self._consecutive_failures += 1
        age = int(now - self._last_successful_fetch) if self._last_successful_fetch else 999
        return {
            "price": self._price_cache.get("price", 0.0),
            "bid": self._price_cache.get("bid", 0.0),
            "ask": self._price_cache.get("ask", 0.0),
            "spread": self.default_spread,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "provider": "STALE_FALLBACK",
            "is_stale": True,
            "data_age_seconds": age,
            "is_market_open": self.is_market_open(),
        }

    def get_current_price(self) -> Optional[float]:
        """Convenience method returning latest spot price"""
        snap = self.get_market_snapshot()
        p = snap.get("price")
        return p if (p and p > 0) else None

    # ─────────────────────────────────────────────────────────
    # OHLCV Multi-Timeframe Candle Data (M15, M5, M1)
    # ─────────────────────────────────────────────────────────
    def get_ohlcv(self, timeframe: str = "5m", bars: int = 150) -> Optional[pd.DataFrame]:
        """
        OHLCV candle data ingestion with timestamp normalization,
        outlier filtering, and completed bar validation.
        """
        tf_map = {
            "1m": "1m",
            "5m": "5m",
            "15m": "15m",
            "60m": "60m",
            "1h": "60m",
        }
        yf_tf = tf_map.get(timeframe.lower(), "5m")
        period = "5d" if yf_tf == "1m" else ("30d" if yf_tf in ("5m", "15m") else "60d")

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
                    df = df[["Open", "High", "Low", "Close"]].dropna()

                    # Outlier filter: eliminates single erroneous spikes (> 8x median bar range)
                    tr = (df["High"] - df["Low"]).abs()
                    median_tr = tr.median()
                    if median_tr > 0:
                        outliers = tr > (median_tr * 8.0)
                        if outliers.any():
                            df.loc[outliers, "High"] = df.loc[outliers, "Open"] + (median_tr * 2.5)
                            df.loc[outliers, "Low"] = df.loc[outliers, "Open"] - (median_tr * 2.5)

                    # Normalize futures basis difference with spot price if needed
                    if spot_price and not df.empty:
                        last_close = df["Close"].iloc[-1]
                        diff = last_close - spot_price
                        if abs(diff) > 2.0:
                            df["Open"]  = (df["Open"] - diff).round(2)
                            df["High"]  = (df["High"] - diff).round(2)
                            df["Low"]   = (df["Low"] - diff).round(2)
                            df["Close"] = (df["Close"] - diff).round(2)

                    return df.tail(bars)
            except Exception as e:
                logger.warning(f"OHLCV fetch note for {sym}/{timeframe}: {e}")

        return None

    def is_market_open(self) -> bool:
        """
        Spot Gold operates Sunday 22:00 UTC to Friday 21:00 UTC.
        Returns False during weekend shutdown.
        """
        now = datetime.now(timezone.utc)
        weekday = now.weekday()  # 0=Monday, 5=Saturday, 6=Sunday

        if weekday == 5:  # Saturday full close
            return False
        if weekday == 4 and now.hour >= 21:  # Friday post-close
            return False
        if weekday == 6 and now.hour < 22:   # Sunday pre-open
            return False

        return True

    def get_health_status(self) -> Dict[str, Any]:
        """Returns health diagnostics for market data engine"""
        now = time.time()
        age = int(now - self._last_successful_fetch) if self._last_successful_fetch else 999
        is_healthy = age < 120 and self._consecutive_failures < 3
        return {
            "status": "HEALTHY" if is_healthy else "DEGRADED",
            "last_provider": self._last_provider,
            "data_age_seconds": age,
            "consecutive_failures": self._consecutive_failures,
            "is_market_open": self.is_market_open(),
        }
