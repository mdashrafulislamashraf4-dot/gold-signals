"""
============================================================
  modules/command_handler.py
  Telegram Bot Command Handler — /signal, /price, /news, etc.
============================================================
"""

import logging
import threading

import requests

from config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_IDS

logger = logging.getLogger(__name__)


class CommandHandler:
    """Telegram bot commands হ্যান্ডেল করে"""

    BASE_URL = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"

    def __init__(self, market_data, technical, news_analyzer,
                 ai_analyzer, signal_engine, telegram_bot, scheduler):
        self.md  = market_data
        self.ta  = technical
        self.na  = news_analyzer
        self.ai  = ai_analyzer
        self.se  = signal_engine
        self.bot = telegram_bot
        self.sch = scheduler

        self._offset        = 0
        self._running       = False
        self._poll_thread   = None

    # ─────────────────────────────────────────────────────────
    # Polling Loop
    # ─────────────────────────────────────────────────────────
    def start_polling(self):
        """Telegram updates poll করা শুরু করে"""
        self._running     = True
        self._poll_thread = threading.Thread(target=self._poll_loop, daemon=True)
        self._poll_thread.start()
        logger.info("Telegram command polling started")

    def stop_polling(self):
        self._running = False

    def _poll_loop(self):
        """Telegram getUpdates loop"""
        while self._running:
            try:
                updates = self._get_updates()
                for update in updates:
                    self._process_update(update)
            except Exception as e:
                logger.error(f"Poll error: {e}")
            import time
            time.sleep(2)

    def _get_updates(self) -> list:
        try:
            resp = requests.get(
                f"{self.BASE_URL}/getUpdates",
                params={"offset": self._offset, "timeout": 30},
                timeout=35,
            )
            if resp.ok:
                data    = resp.json()
                updates = data.get("result", [])
                if updates:
                    self._offset = updates[-1]["update_id"] + 1
                return updates
        except Exception as e:
            logger.error(f"getUpdates error: {e}")
        return []

    # ─────────────────────────────────────────────────────────
    # Process Update
    # ─────────────────────────────────────────────────────────
    def _process_update(self, update: dict):
        """একটি টেলিগ্রাম আপডেট প্রসেস করে"""
        message = update.get("message", {})
        if not message:
            return

        chat_id = str(message.get("chat", {}).get("id", ""))
        text    = message.get("text", "").strip()

        if not text or not text.startswith("/"):
            return

        # Security check — only allow configured chat IDs
        if TELEGRAM_CHAT_IDS and chat_id not in TELEGRAM_CHAT_IDS:
            self.bot.send_message(
                "⛔ Unauthorized. This bot is private.", chat_id=chat_id
            )
            return

        cmd = text.split()[0].lower().replace(f"@", "").split("@")[0]
        logger.info(f"Command received: {cmd} from {chat_id}")

        handlers = {
            "/signal":   self._cmd_signal,
            "/price":    self._cmd_price,
            "/news":     self._cmd_news,
            "/analysis": self._cmd_analysis,
            "/calendar": self._cmd_calendar,
            "/report":   self._cmd_report,
            "/weekly":   self._cmd_weekly,
            "/status":   self._cmd_status,
            "/help":     self._cmd_help,
            "/start":    self._cmd_help,
        }

        handler = handlers.get(cmd, self._cmd_unknown)
        threading.Thread(
            target=handler, args=(chat_id,), daemon=True
        ).start()

    # ─────────────────────────────────────────────────────────
    # Command Handlers
    # ─────────────────────────────────────────────────────────
    def _cmd_signal(self, chat_id: str):
        """/signal — লেটেস্ট ট্রেডিং সিগনাল"""
        self.bot.send_message("⏳ Analyzing market... Please wait.", chat_id=chat_id)
        try:
            signal = self.sch.run_analysis(send_regardless=True)
            if signal and signal.get("direction") != "NEUTRAL":
                msg = self.bot.format_signal_message(signal)
                self.bot.send_message(msg, chat_id=chat_id)
            else:
                self.bot.send_message(
                    "⚪ <b>No clear signal at this time.</b>\n\n"
                    "Market is in a NEUTRAL zone. Wait for a better opportunity.",
                    chat_id=chat_id,
                )
        except Exception as e:
            self.bot.send_message(f"❌ Error generating signal: {e}", chat_id=chat_id)

    def _cmd_price(self, chat_id: str):
        """/price — বর্তমান গোল্ড প্রাইস"""
        try:
            price      = self.md.get_current_price()
            correlated = self.md.get_correlated_assets()
            if price:
                msg = self.bot.format_price_update(price, correlated)
            else:
                msg = "❌ Could not fetch gold price. Try again."
            self.bot.send_message(msg, chat_id=chat_id)
        except Exception as e:
            self.bot.send_message(f"❌ Error: {e}", chat_id=chat_id)

    def _cmd_news(self, chat_id: str):
        """/news — লেটেস্ট গোল্ড নিউজ"""
        self.bot.send_message("📰 Fetching latest gold news...", chat_id=chat_id)
        try:
            articles = self.na.fetch_all_news()
            if not articles:
                self.bot.send_message("No news found.", chat_id=chat_id)
                return

            msg = "📰 <b>LATEST GOLD MARKET NEWS</b>\n━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            for a in articles[:5]:
                title  = a.get("title", "")[:150]
                source = a.get("source", "")
                link   = a.get("link", "")
                msg += f"📌 <b>{title}</b>\n📎 {source}\n"
                if link:
                    msg += f'🔗 <a href="{link}">Read more</a>\n'
                msg += "\n"
            self.bot.send_message(msg, chat_id=chat_id)
        except Exception as e:
            self.bot.send_message(f"❌ Error fetching news: {e}", chat_id=chat_id)

    def _cmd_analysis(self, chat_id: str):
        """/analysis — সম্পূর্ণ টেকনিক্যাল এনালাইসিস"""
        self.bot.send_message("🔍 Running deep analysis...", chat_id=chat_id)
        try:
            price      = self.md.get_current_price()
            df         = self.md.get_ohlcv(timeframe="1h", bars=200)
            tech       = self.ta.get_technical_score(df)
            key_levels = self.md.get_key_levels(df)

            details    = tech.get("details", {})
            patterns   = tech.get("patterns", [])
            fib        = tech.get("fibonacci", {})

            pat_text = ""
            for p in patterns[:3]:
                pat_text += f"  🕯️ {p[2]}\n"

            fib_text = ""
            for level, val in list(fib.items())[:5]:
                fib_text += f"  {level}%: {val}\n"

            sup = ", ".join(str(s) for s in key_levels.get("support", [])[:3])
            res = ", ".join(str(r) for r in key_levels.get("resistance", [])[:3])

            msg = f"""🔍 <b>FULL TECHNICAL ANALYSIS</b>
━━━━━━━━━━━━━━━━━━━━━━━━━
💰 <b>XAUUSD Price: {price}</b>

📊 <b>Indicators:</b>
  RSI(14): {details.get('RSI', 'N/A')}
  MACD: {details.get('MACD', 'N/A')}
  EMA20: {details.get('EMA_20', 'N/A')}
  EMA50: {details.get('EMA_50', 'N/A')}
  EMA200: {details.get('EMA_200', 'N/A')}
  ATR: {details.get('ATR', 'N/A')}
  ADX: {details.get('ADX', 'N/A')}
  Stochastic: {details.get('Stochastic_K', 'N/A')}

🎯 <b>Score: {tech.get('score', 50)}/100</b>
Direction: {tech.get('direction', 'NEUTRAL')}

🏗️ <b>Key Levels:</b>
  Resistance: {res}
  Support: {sup}
  Pivot: {key_levels.get('pivot', 'N/A')}

📐 <b>Fibonacci:</b>
{fib_text if fib_text else "  Calculating..."}
"""
            if pat_text:
                msg += f"\n🕯️ <b>Patterns:</b>\n{pat_text}"

            msg += "━━━━━━━━━━━━━━━━━━━━━━━━━\n🤖 <i>AI Gold Signal System</i>"
            self.bot.send_message(msg, chat_id=chat_id)

        except Exception as e:
            self.bot.send_message(f"❌ Analysis error: {e}", chat_id=chat_id)

    def _cmd_calendar(self, chat_id: str):
        """/calendar — আজকের ইকোনমিক ইভেন্ট"""
        self.bot.send_message("📅 Fetching economic calendar...", chat_id=chat_id)
        try:
            events = self.na.get_economic_calendar()
            msg    = self.bot.format_economic_calendar(events)
            self.bot.send_message(msg, chat_id=chat_id)
        except Exception as e:
            self.bot.send_message(f"❌ Error: {e}", chat_id=chat_id)

    def _cmd_report(self, chat_id: str):
        """/report — আজকের পারফরম্যান্স রিপোর্ট"""
        try:
            stats = self.se.get_daily_stats()
            msg   = self.bot.format_daily_report(stats)
            self.bot.send_message(msg, chat_id=chat_id)
        except Exception as e:
            self.bot.send_message(f"❌ Report error: {e}", chat_id=chat_id)

    def _cmd_weekly(self, chat_id: str):
        """/weekly — সাপ্তাহিক পারফরম্যান্স রিপোর্ট"""
        try:
            stats      = self.se.get_weekly_stats()
            ai_summary = ""
            if self.ai.available:
                ai_summary = self.ai.generate_weekly_summary(
                    stats.get("signals", []), stats.get("win_rate", 0)
                )
            msg = self.bot.format_weekly_report(stats, ai_summary)
            self.bot.send_message(msg, chat_id=chat_id)
        except Exception as e:
            self.bot.send_message(f"❌ Weekly report error: {e}", chat_id=chat_id)

    def _cmd_status(self, chat_id: str):
        """/status — সিস্টেম স্ট্যাটাস"""
        try:
            price      = self.md.get_current_price()
            is_open    = self.md.is_market_open()
            jobs       = self.sch.get_jobs_status()
            stats      = self.se.get_daily_stats()

            jobs_text = ""
            for j in jobs[:5]:
                jobs_text += f"  ✅ {j['name']}: {j['next_run'][:16]}\n"

            msg = f"""⚙️ <b>SYSTEM STATUS</b>
━━━━━━━━━━━━━━━━━━━━━━━━━
✅ Bot: <b>ACTIVE</b>
💰 Gold Price: <code>{price}</code>
📊 Market: {"🟢 OPEN" if is_open else "🔴 CLOSED"}
🤖 AI: {"✅ Active" if self.ai.available else "❌ Not configured"}

📋 <b>Today's Performance:</b>
  Signals: {stats.get('total', 0)}
  Win Rate: {stats.get('win_rate', 0)}%

⏰ <b>Scheduled Jobs:</b>
{jobs_text if jobs_text else "  Loading..."}
━━━━━━━━━━━━━━━━━━━━━━━━━
🤖 <i>AI Gold Signal System</i>"""
            self.bot.send_message(msg, chat_id=chat_id)
        except Exception as e:
            self.bot.send_message(f"❌ Status error: {e}", chat_id=chat_id)

    def _cmd_help(self, chat_id: str):
        """/help — সব কমান্ডের তালিকা"""
        msg = """🤖 <b>AI GOLD SIGNAL BOT</b>
━━━━━━━━━━━━━━━━━━━━━━━━━
<b>Available Commands:</b>

📊 /signal — Get latest BUY/SELL signal
💰 /price — Current gold price + market
📰 /news — Latest gold market news
🔍 /analysis — Full technical analysis
📅 /calendar — Economic events today
📋 /report — Today's performance report
📆 /weekly — Weekly performance report
⚙️ /status — System status & health
❓ /help — Show this help message

━━━━━━━━━━━━━━━━━━━━━━━━━
<b>Auto Alerts (No command needed):</b>
  🔔 New signal every 15 min
  ✅ TP/SL hit notifications
  🚨 High impact news alerts
  📊 Daily report at 12:00 AM
  📅 Weekly report on Friday

━━━━━━━━━━━━━━━━━━━━━━━━━
⚠️ <i>Always use risk management!</i>
💼 <i>Max 2% risk per trade</i>"""
        self.bot.send_message(msg, chat_id=chat_id)

    def _cmd_unknown(self, chat_id: str):
        self.bot.send_message(
            "❓ Unknown command. Use /help to see all available commands.",
            chat_id=chat_id,
        )
