"""
============================================================
  modules/scheduler.py
  Continuous 24/7 Market Monitoring & Execution Scheduler
  Commander A Specification:
    - 24/7 setup scanning whenever valid data is available
    - No fixed session restrictions (London/NY)
    - Frequent TP/SL active trade tracking
    - Zero promotional/daily Telegram spam (signals & results only)
============================================================
"""

import logging
from datetime import datetime
import pytz
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger

from config import (
    TIMEZONE,
    SIGNAL_CHECK_INTERVAL,
    MONITOR_CHECK_INTERVAL_SEC,
    NEWS_CHECK_INTERVAL_SECONDS,
    NEWS_API_KEY,
)

logger = logging.getLogger(__name__)


class TaskScheduler:
    """Orchestrates 24/7 continuous market monitoring and rapid TP/SL tracking"""

    def __init__(
        self,
        market_data,
        signal_engine,
        news_analyzer=None,
        ai_analyzer=None,
    ):
        self.md = market_data
        self.se = signal_engine
        self.na = news_analyzer
        self.ai = ai_analyzer

        self.scheduler = BackgroundScheduler(timezone=TIMEZONE)
        self._running = False
        self._last_news_warning = False
        self._last_news_event = None

    # ─────────────────────────────────────────────────────────
    # 1. Core Setup Analysis & Signal Dispatch
    # ─────────────────────────────────────────────────────────
    def run_analysis(self):
        """
        Runs full multi-timeframe strategy evaluation across the 3 setup engines.
        Operates 24/7 whenever valid market data is available.
        """
        try:
            # 1. Market data snapshot
            snapshot = self.md.get_market_snapshot()
            if snapshot.get("is_stale", False) or not snapshot.get("price"):
                logger.warning("Market data is stale or unavailable. Skipping analysis cycle without fabricating signals.")
                return

            if not self.md.is_market_open():
                logger.debug("Market is closed for the weekend. Skipping.")
                return

            price  = float(snapshot["price"])
            spread = float(snapshot.get("spread", 0.25))

            # 2. Fetch completed OHLCV candles
            df_15m = self.md.get_ohlcv("15m", bars=80)
            df_5m  = self.md.get_ohlcv("5m", bars=60)
            df_1m  = self.md.get_ohlcv("1m", bars=60)

            if df_15m is None or df_5m is None or len(df_15m) < 20 or len(df_5m) < 20:
                logger.debug("Insufficient candle history available. Skipping cycle.")
                return

            # 3. Evaluate setups and dispatch signal if approved
            signal = self.se.generate_and_dispatch(
                df_15m=df_15m,
                df_5m=df_5m,
                df_1m=df_1m,
                current_price=price,
                current_spread=spread,
                news_risk=self._last_news_warning,
                news_event_name=self._last_news_event,
            )

            if signal:
                logger.info(f"Signal #{signal['trade_id']:03d} generated: {signal['direction']} @ {signal['entry']}")

        except Exception as e:
            logger.error(f"Error in analysis cycle: {e}", exc_info=True)

    # ─────────────────────────────────────────────────────────
    # 2. Rapid TP/SL & Trade Outcome Monitoring
    # ─────────────────────────────────────────────────────────
    def monitor_trades(self):
        """
        Continuously tracks active trades for TP1, TP2, and SL events.
        Runs frequently (every 15s) to guarantee prompt exit detection.
        """
        try:
            snapshot = self.md.get_market_snapshot()
            price = snapshot.get("price")
            spread = snapshot.get("spread", 0.25)
            if not price or snapshot.get("is_stale"):
                return

            # Read 1M bar to check intra-candle High/Low extremes
            df_1m = self.md.get_ohlcv("1m", bars=3)

            self.se.monitor_active_trades(
                current_price=float(price),
                current_spread=float(spread),
                df_1m=df_1m,
            )
        except Exception as e:
            logger.error(f"Error in trade monitoring cycle: {e}")

    # ─────────────────────────────────────────────────────────
    # 3. News Risk Watchdog (Logs Only - No Telegram Spam)
    # ─────────────────────────────────────────────────────────
    def monitor_news(self):
        """
        Checks for high-impact macro news events and sets news warning flag.
        Never disables trading solely based on the clock.
        """
        if not self.na:
            return

        try:
            articles = self.na.fetch_all_news(api_key=NEWS_API_KEY)
            sentiment = self.na.analyze_sentiment(articles)
            self._last_news_warning = sentiment.get("news_risk", False)
            self._last_news_event = sentiment.get("event_name")
            if self._last_news_warning:
                logger.warning(f"High-impact news warning active: {self._last_news_event}")
        except Exception as e:
            logger.debug(f"News monitor check note: {e}")

    # ─────────────────────────────────────────────────────────
    # Lifecycle Control
    # ─────────────────────────────────────────────────────────
    def start(self):
        """Starts all background schedulers"""
        if self._running:
            return

        # 1. Main strategy analysis (every 5 minutes or configured interval)
        self.scheduler.add_job(
            self.run_analysis,
            IntervalTrigger(minutes=SIGNAL_CHECK_INTERVAL),
            id="strategy_analysis",
            name="XAUUSD Strategy Analysis",
            replace_existing=True,
        )

        # 2. Active trade monitoring (every 15 seconds)
        self.scheduler.add_job(
            self.monitor_trades,
            IntervalTrigger(seconds=MONITOR_CHECK_INTERVAL_SEC),
            id="trade_monitor",
            name="Rapid TP/SL Monitor",
            replace_existing=True,
        )

        # 3. News monitor (every 60 seconds)
        self.scheduler.add_job(
            self.monitor_news,
            IntervalTrigger(seconds=NEWS_CHECK_INTERVAL_SECONDS),
            id="news_monitor",
            name="News Risk Monitor",
            replace_existing=True,
        )

        self.scheduler.start()
        self._running = True
        logger.info(f"TaskScheduler started: 24/7 continuous monitoring active.")
        logger.info(f"  • Strategy analysis interval: {SIGNAL_CHECK_INTERVAL}m")
        logger.info(f"  • Trade outcome tracker: {MONITOR_CHECK_INTERVAL_SEC}s")

    def stop(self):
        """Gracefully halts schedulers"""
        if self._running:
            self.scheduler.shutdown()
            self._running = False
            logger.info("TaskScheduler stopped.")
