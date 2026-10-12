"""
============================================================
  modules/scheduler.py
  Automated tasks — সিগনাল চেক, রিপোর্ট, নিউজ মনিটর
============================================================
"""

import logging
import threading
import time
from datetime import datetime

import pytz
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from config import (
    TIMEZONE, SIGNAL_CHECK_INTERVAL, DAILY_REPORT_TIME,
    MIN_CONFIDENCE, NEWS_API_KEY, TIMEFRAMES,
)

logger = logging.getLogger(__name__)


class TaskScheduler:
    """সব অটোমেটিক টাস্ক শিডিউল করে"""

    def __init__(self, market_data, technical, news_analyzer,
                 ai_analyzer, signal_engine, telegram_bot):
        self.md  = market_data
        self.ta  = technical
        self.na  = news_analyzer
        self.ai  = ai_analyzer
        self.se  = signal_engine
        self.bot = telegram_bot

        self.scheduler        = BackgroundScheduler(timezone=TIMEZONE)
        self._last_signal_dir = "NEUTRAL"
        self._last_news_sent  = set()
        self._running         = False

        # ── Real-Time Continuous Watcher (Zero Waiting Barrier) ──
        self._price_history      = []   # [(timestamp, price)]
        self._last_full_scan     = 0    # last full analysis timestamp
        self._last_flash_alert   = 0    # last flash volatility alert
        self._notified_breakeven = set() # signal IDs notified for breakeven
        self._realtime_thread    = None

    # ─────────────────────────────────────────────────────────
    # Core Analysis Task
    # ─────────────────────────────────────────────────────────
    def run_analysis(self, send_regardless: bool = False):
        """
        সম্পূর্ণ মার্কেট এনালাইসিস চালায় এবং সিগনাল পাঠায়
        """
        logger.info("━━━━ Running full market analysis ━━━━")
        try:
            # 1) Current price
            price = self.md.get_current_price()
            if not price:
                logger.warning("Could not fetch gold price")
                return

            logger.info(f"Current Gold price: {price}")

            # 2) Market open check
            if not self.md.is_market_open() and not send_regardless:
                logger.info("Market is closed — skipping")
                return

            # 3) OHLCV data for multiple timeframes
            primary_tf = TIMEFRAMES[0] if TIMEFRAMES else "1h"
            df = self.md.get_ohlcv(timeframe=primary_tf, bars=200)
            if df is None or df.empty:
                logger.warning("No OHLCV data available")
                return

            # 4) Technical Analysis
            tech_result = self.ta.get_technical_score(df)
            logger.info(f"Technical score: {tech_result['score']} ({tech_result['direction']})")

            # 5) News & Sentiment
            articles    = self.na.fetch_all_news(api_key=NEWS_API_KEY)
            news_result = self.na.analyze_sentiment(articles)
            logger.info(f"News sentiment: {news_result['score']} ({news_result['direction']})")

            # 6) Correlated assets
            correlated = self.md.get_correlated_assets()

            # 7) AI Analysis
            ai_result = self.ai.analyze_market(
                current_price=price,
                technical_data=tech_result,
                news_sentiment=news_result,
                correlated_assets=correlated,
                timeframe=primary_tf.upper(),
            )
            logger.info(f"AI: {ai_result['direction']} ({ai_result['confidence']}%)")

            # 8) Generate Signal
            signal = self.se.generate_signal(
                technical_result=tech_result,
                news_result=news_result,
                ai_result=ai_result,
                current_price=price,
                timeframe=primary_tf.upper(),
            )

            logger.info(f"Final signal: {signal['direction']} | Confidence: {signal['confidence']}%")

            # 9) Send signal if confidence is sufficient
            if (signal["direction"] != "NEUTRAL" and
                signal["confidence"] >= MIN_CONFIDENCE and
                (signal["direction"] != self._last_signal_dir or send_regardless)):

                self.bot.send_signal(signal, price)
                self._last_signal_dir = signal["direction"]
                logger.info(f"Signal sent: {signal['direction']}")
            else:
                logger.info(f"Signal not sent (confidence: {signal['confidence']}%, direction: {signal['direction']})")

            return signal

        except Exception as e:
            logger.error(f"Analysis error: {e}", exc_info=True)
            return None

    # ─────────────────────────────────────────────────────────
    # Monitor Active Signals (TP/SL Tracking)
    # ─────────────────────────────────────────────────────────
    def monitor_signals(self):
        """চলমান সিগনালের TP/SL মনিটর করে"""
        try:
            price = self.md.get_current_price()
            if not price:
                return

            alerts = self.se.check_active_signals(price)
            for alert in alerts:
                alert_type = alert["type"]
                signal     = alert["signal"]
                cur_price  = alert["price"]

                self.bot.send_tp_sl_alert(alert_type, signal, cur_price)
                logger.info(f"{alert_type} hit for signal #{signal.get('id')} at {cur_price}")

        except Exception as e:
            logger.error(f"Signal monitoring error: {e}")

    # ─────────────────────────────────────────────────────────
    # News Monitor
    # ─────────────────────────────────────────────────────────
    def monitor_news(self):
        """গুরুত্বপূর্ণ নিউজ মনিটর করে এবং অ্যালার্ট পাঠায়"""
        try:
            articles    = self.na.fetch_all_news(api_key=NEWS_API_KEY)
            news_result = self.na.analyze_sentiment(articles)

            high_impact = news_result.get("high_impact_news", [])
            price       = self.md.get_current_price() or 0

            for news in high_impact[:3]:
                news_id = news.get("title", "")[:50]
                if news_id in self._last_news_sent:
                    continue

                # AI impact analysis
                ai_analysis = ""
                if self.ai.available and news.get("title"):
                    ai_analysis = self.ai.analyze_news_impact(news["title"], price)

                news["impact"] = "HIGH"
                self.bot.send_news_alert(news, ai_analysis)
                self._last_news_sent.add(news_id)

                # Keep memory manageable
                if len(self._last_news_sent) > 100:
                    self._last_news_sent = set(list(self._last_news_sent)[-50:])

                logger.info(f"News alert sent: {news.get('title', '')[:60]}")
                time.sleep(2)

        except Exception as e:
            logger.error(f"News monitor error: {e}")

    # ─────────────────────────────────────────────────────────
    # Daily Report (রাত ১২টায়)
    # ─────────────────────────────────────────────────────────
    def send_daily_report(self):
        """রাত ১২টায় দৈনিক রিপোর্ট পাঠায়"""
        try:
            logger.info("Generating daily report...")
            stats = self.se.get_daily_stats()
            self.bot.send_daily_report(stats)
            logger.info("Daily report sent")
        except Exception as e:
            logger.error(f"Daily report error: {e}")

    # ─────────────────────────────────────────────────────────
    # Weekly Report (শুক্রবার মার্কেট বন্ধের পরে)
    # ─────────────────────────────────────────────────────────
    def send_weekly_report(self):
        """শুক্রবার সাপ্তাহিক রিপোর্ট পাঠায়"""
        try:
            logger.info("Generating weekly report...")
            stats      = self.se.get_weekly_stats()
            ai_summary = ""
            if self.ai.available:
                ai_summary = self.ai.generate_weekly_summary(
                    stats.get("signals", []), stats.get("win_rate", 0)
                )
            self.bot.send_weekly_report(stats, ai_summary)
            logger.info("Weekly report sent")
        except Exception as e:
            logger.error(f"Weekly report error: {e}")

    # ─────────────────────────────────────────────────────────
    # Real-Time Continuous Watcher Loop (Zero-Delay Monitoring)
    # ─────────────────────────────────────────────────────────
    def _realtime_loop(self):
        """
        অবিরাম রিয়েল-টাইম মনিটরিং (কোনো টাইমের বাধা নেই):
        ১. প্রতি ৫ সেকেন্ডে লাইভ স্পট দাম ট্র্যাক করে
        ২. রিয়েলটাইমে TP/SL এবং Breakeven (ঝুঁকিমুক্ত) চেক করে
        ৩. হঠাৎ কোনো তীব্র মুভমেন্ট/স্পাইক হলে সাথে সাথে অ্যালার্ট দেয়
        ৪. বড় মুভমেন্ট হলে সাথে সাথে রি-এনালাইসিস করে সিগনাল পাঠায়
        """
        logger.info("⚡ Real-Time Continuous Market Watcher active (Scanning every 5 sec)")
        import sqlite3
        from config import DB_PATH

        while self._running:
            try:
                now_ts = time.time()
                cur_price = self.md.get_current_price()

                if cur_price and cur_price > 0:
                    # 1. Update rolling price history (last 120 seconds)
                    self._price_history.append((now_ts, cur_price))
                    self._price_history = [
                        (t, p) for (t, p) in self._price_history if now_ts - t <= 120
                    ]

                    # 2. Check Active Signals for TP / SL / Breakeven
                    self._check_realtime_active_signals(cur_price)

                    # 3. Flash Volatility / Momentum Spike Detection (>= $3.00 movement)
                    if len(self._price_history) >= 2:
                        oldest_p = self._price_history[0][1]
                        price_diff = round(cur_price - oldest_p, 2)
                        elapsed = int(now_ts - self._price_history[0][0])
                        if abs(price_diff) >= 3.0 and (now_ts - self._last_flash_alert > 300):
                            alert_msg = self.bot.format_volatility_alert(cur_price, price_diff, elapsed)
                            self.bot.send_message(alert_msg)
                            self._last_flash_alert = now_ts
                            # Trigger immediate full analysis due to high volatility
                            threading.Thread(target=self.run_analysis, kwargs={"send_regardless": False}, daemon=True).start()

                    # 4. Continuous background scan (runs every 90 seconds or when triggered)
                    if now_ts - self._last_full_scan >= 90:
                        self._last_full_scan = now_ts
                        threading.Thread(target=self.run_analysis, daemon=True).start()

            except Exception as e:
                logger.error(f"Realtime loop error: {e}")

            time.sleep(5)

    def _check_realtime_active_signals(self, cur_price: float):
        """সক্রিয় ট্রেডের TP/SL এবং Breakeven রিয়েলটাইমে পরীক্ষা করে"""
        import sqlite3
        from config import DB_PATH

        try:
            # 1. Check TP / SL hits
            alerts = self.se.check_active_signals(cur_price)
            for alert in alerts:
                self.bot.send_tp_sl_alert(alert["type"], alert["signal"], alert["price"])
                logger.info(f"⚡ Instant hit: {alert['type']} at {alert['price']}")

            # 2. Check for Breakeven (+15 pips / +$1.50 profit)
            with sqlite3.connect(DB_PATH) as conn:
                conn.row_factory = sqlite3.Row
                rows = conn.execute("SELECT * FROM signals WHERE status='ACTIVE'").fetchall()

            for r in rows:
                s = dict(r)
                sid = s["id"]
                if sid in self._notified_breakeven:
                    continue

                direction = s["direction"]
                entry = s.get("entry_price", 0)
                if not entry:
                    continue

                profit_usd = (cur_price - entry) if direction == "BUY" else (entry - cur_price)
                # If trade is in profit by $1.50+ (15 pips)
                if profit_usd >= 1.50:
                    msg = self.bot.format_breakeven_alert(s, cur_price, profit_usd)
                    self.bot.send_message(msg)
                    self._notified_breakeven.add(sid)
                    logger.info(f"🛡️ Breakeven alert sent for signal #{sid} (+{profit_usd:.2f})")

        except Exception as e:
            logger.error(f"Realtime active signal check error: {e}")

    # ─────────────────────────────────────────────────────────
    # Start All Scheduled Jobs
    # ─────────────────────────────────────────────────────────
    def start(self):
        """সব শিডিউল জব ও রিয়েল-টাইম থ্রেড শুরু করে"""
        if self._running:
            logger.warning("Scheduler already running")
            return

        self._running = True

        # Launch real-time 5-second continuous watcher thread
        self._realtime_thread = threading.Thread(target=self._realtime_loop, daemon=True)
        self._realtime_thread.start()

        # 1) Main signal analysis fallback — every N minutes
        self.scheduler.add_job(
            self.run_analysis,
            IntervalTrigger(minutes=SIGNAL_CHECK_INTERVAL),
            id="signal_analysis",
            name="Signal Analysis",
            replace_existing=True,
        )

        # 2) TP/SL monitoring — every 3 minutes
        self.scheduler.add_job(
            self.monitor_signals,
            IntervalTrigger(minutes=3),
            id="signal_monitor",
            name="Signal Monitor",
            replace_existing=True,
        )

        # 3) News monitoring — every 30 minutes
        self.scheduler.add_job(
            self.monitor_news,
            IntervalTrigger(minutes=30),
            id="news_monitor",
            name="News Monitor",
            replace_existing=True,
        )

        # 4) Daily report — রাত ১২:০০ (Bangladesh time)
        report_hour, report_min = DAILY_REPORT_TIME.split(":")
        self.scheduler.add_job(
            self.send_daily_report,
            CronTrigger(hour=int(report_hour), minute=int(report_min), timezone=TIMEZONE),
            id="daily_report",
            name="Daily Report",
            replace_existing=True,
        )

        # 5) Weekly report — Friday 5:30 PM (market close)
        self.scheduler.add_job(
            self.send_weekly_report,
            CronTrigger(day_of_week="fri", hour=17, minute=30, timezone=TIMEZONE),
            id="weekly_report",
            name="Weekly Report",
            replace_existing=True,
        )

        self.scheduler.start()
        self._running = True
        logger.info("✅ Scheduler started with all jobs")
        logger.info(f"  📊 Signal check: every {SIGNAL_CHECK_INTERVAL} min")
        logger.info(f"  🔍 Signal monitor: every 3 min")
        logger.info(f"  📰 News monitor: every 30 min")
        logger.info(f"  📋 Daily report: {DAILY_REPORT_TIME} ({TIMEZONE})")
        logger.info(f"  📅 Weekly report: Friday 17:30 ({TIMEZONE})")

    def stop(self):
        """শিডিউলার বন্ধ করে"""
        if self._running:
            self.scheduler.shutdown()
            self._running = False
            logger.info("Scheduler stopped")

    def get_jobs_status(self) -> list:
        """সব শিডিউল জবের স্ট্যাটাস দেখায়"""
        jobs = []
        for job in self.scheduler.get_jobs():
            jobs.append({
                "id":       job.id,
                "name":     job.name,
                "next_run": str(job.next_run_time),
            })
        return jobs
