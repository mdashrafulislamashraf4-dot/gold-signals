"""
============================================================
  modules/command_handler.py
  Telegram Bot Command & Custom Button Handler
  (স্ল্যাশ কমান্ড এবং ছবির মতো বাংলা বাটন দুটোই হ্যান্ডেল করে)
============================================================
"""

import logging
import threading

import requests

from config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_IDS

logger = logging.getLogger(__name__)


class CommandHandler:
    """Telegram bot commands and persistent custom buttons handler"""

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

        self._offset      = 0
        self._running     = False
        self._poll_thread = None

    # ─────────────────────────────────────────────────────────
    # Polling Loop
    # ─────────────────────────────────────────────────────────
    def start_polling(self):
        """Telegram updates poll করা শুরু করে"""
        self._running     = True
        self._poll_thread = threading.Thread(target=self._poll_loop, daemon=True)
        self._poll_thread.start()
        logger.info("Telegram command & button polling started")

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
            time.sleep(1.5)

    def _get_updates(self) -> list:
        try:
            resp = requests.get(
                f"{self.BASE_URL}/getUpdates",
                params={"offset": self._offset, "timeout": 25},
                timeout=30,
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
        """টেলিগ্রাম আপডেট প্রসেস করে (কমান্ড এবং বাটন ক্লিক দুটোই সমর্থন করে)"""
        message = update.get("message", {})
        if not message:
            return

        chat_id = str(message.get("chat", {}).get("id", ""))
        text    = message.get("text", "").strip()

        if not text:
            return

        # Security check — only allow configured chat IDs
        if TELEGRAM_CHAT_IDS and chat_id not in TELEGRAM_CHAT_IDS:
            self.bot.send_message(
                "⛔ অননুমোদিত অ্যাক্সেস। এই বটটি ব্যক্তিগত।", chat_id=chat_id
            )
            return

        # Identify handler: check full text first (for buttons), then slash command
        handlers = {
            # ── ছবির মতো বাংলা বাটন হ্যান্ডলার ─────────────────
            "🎯 লাইভ সিগনাল":           self._cmd_signal,
            "💰 গোল্ড লাইভ প্রাইস":       self._cmd_price,
            "🔍 টেকনিক্যাল এনালাইসিস":     self._cmd_analysis,
            "📰 ব্রেকিং নিউজ ও প্রভাব":    self._cmd_news,
            "📅 আজকের ইকোনমিক ইভেন্ট":    self._cmd_calendar,
            "📊 আজকের রিপোর্ট":           self._cmd_report,
            "🗓️ সাপ্তাহিক রিপোর্ট":        self._cmd_weekly,
            "⚡ দ্রুত মার্কেট স্ক্যান":       self._cmd_scan,
            "⚙️ সিস্টেম স্ট্যাটাস":       self._cmd_status,
            "💡 ট্রেডিং গাইড ও সাহায্য":     self._cmd_help,

            # ── স্ল্যাশ কমান্ড হ্যান্ডলার ──────────────────────
            "/signal":   self._cmd_signal,
            "/price":    self._cmd_price,
            "/news":     self._cmd_news,
            "/analysis": self._cmd_analysis,
            "/calendar": self._cmd_calendar,
            "/report":   self._cmd_report,
            "/weekly":   self._cmd_weekly,
            "/scan":     self._cmd_scan,
            "/status":   self._cmd_status,
            "/help":     self._cmd_help,
            "/start":    self._cmd_start,
        }

        # Clean command if starts with /
        if text.startswith("/"):
            lookup_key = text.split()[0].lower().split("@")[0]
        else:
            lookup_key = text

        handler = handlers.get(lookup_key)
        if handler:
            logger.info(f"Triggered action: {lookup_key} from {chat_id}")
            threading.Thread(target=handler, args=(chat_id,), daemon=True).start()
        elif text.startswith("/"):
            threading.Thread(target=self._cmd_unknown, args=(chat_id,), daemon=True).start()

    # ─────────────────────────────────────────────────────────
    # Command & Button Handlers (সব উত্তর বাংলায়)
    # ─────────────────────────────────────────────────────────
    def _cmd_signal(self, chat_id: str):
        """🎯 লাইভ সিগনাল"""
        self.bot.send_message("⏳ <b>মার্কেট এনালাইসিস চলছে...</b>\nTradingView ডেটা, ১২+ ইন্ডিকেটর এবং বিশ্ব সংবাদের সেন্টিমেন্ট যাচাই করা হচ্ছে। অনুগ্রহ করে একটু অপেক্ষা করুন।", chat_id=chat_id)
        try:
            signal = self.sch.run_analysis(send_regardless=True)
            if signal and signal.get("direction") != "NEUTRAL":
                msg = self.bot.format_signal_message(signal)
                self.bot.send_message(msg, chat_id=chat_id)
            else:
                price = self.md.get_current_price() or 0
                self.bot.send_message(
                    f"⚪ <b>বর্তমানে কোনো সুস্পষ্ট সিগনাল নেই</b>\n"
                    f"━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                    f"💰 বর্তমান প্রাইস: <code>${price}</code>\n"
                    f"⚖️ মার্কেট এই মুহূর্তে নিরপেক্ষ/সাইডওয়েজ জোনে আছে।\n"
                    f"💡 <i>সিস্টেম ২৪/৭ নজর রাখছে। ভালো কনফার্মেশন পাওয়ার সাথে সাথে স্বয়ংক্রিয় BUY/SELL সিগনাল পাঠানো হবে।</i>",
                    chat_id=chat_id,
                )
        except Exception as e:
            self.bot.send_message(f"❌ সিগনাল তৈরিতে সমস্যা হয়েছে: {e}", chat_id=chat_id)

    def _cmd_price(self, chat_id: str):
        """💰 গোল্ড লাইভ প্রাইস"""
        try:
            price      = self.md.get_current_price()
            correlated = self.md.get_correlated_assets()
            if price:
                msg = self.bot.format_price_update(price, correlated)
            else:
                msg = "❌ গোল্ডের লাইভ প্রাইস ফেচ করা যায়নি। অনুগ্রহ করে আবার চেষ্টা করুন।"
            self.bot.send_message(msg, chat_id=chat_id)
        except Exception as e:
            self.bot.send_message(f"❌ এরর: {e}", chat_id=chat_id)

    def _cmd_news(self, chat_id: str):
        """📰 ব্রেকিং নিউজ ও প্রভাব"""
        self.bot.send_message("📰 <b>সাম্প্রতিক গোল্ড মার্কেট ও ভূরাজনৈতিক সংবাদ সংগ্রহ করা হচ্ছে...</b>", chat_id=chat_id)
        try:
            articles = self.na.fetch_all_news()
            if not articles:
                self.bot.send_message("এই মুহূর্তে কোনো বড় আন্তর্জাতিক সংবাদ পাওয়া যায়নি।", chat_id=chat_id)
                return

            msg = "📰 <b>গোল্ড মার্কেট আন্তর্জাতিক তাজা সংবাদ</b>\n━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            for a in articles[:5]:
                title  = a.get("title", "")[:150]
                source = a.get("source", "")
                link   = a.get("link", "")
                msg += f"📌 <b>{title}</b>\n📎 সূত্র: <i>{source}</i>\n"
                if link:
                    msg += f'🔗 <a href="{link}">সম্পূর্ণ সংবাদ পড়ুন</a>\n'
                msg += "\n"

            msg += "💡 <i>বড় কোনো যুদ্ধ বা মার্কিন ঘোষণার সাথে সাথে এআই তাৎক্ষণিক প্রভাব বিশ্লেষণ করে অ্যালার্ট পাঠাবে।</i>"
            self.bot.send_message(msg, chat_id=chat_id)
        except Exception as e:
            self.bot.send_message(f"❌ সংবাদ সংগ্রহে এরর: {e}", chat_id=chat_id)

    def _cmd_analysis(self, chat_id: str):
        """🔍 টেকনিক্যাল এনালাইসিস"""
        self.bot.send_message("🔍 <b>১২+ টেকনিক্যাল ইন্ডিকেটর এবং ক্যান্ডেলস্টিক এনালাইসিস চলছে...</b>", chat_id=chat_id)
        try:
            price      = self.md.get_current_price()
            df         = self.md.get_ohlcv(timeframe="1h", bars=200)
            tech       = self.ta.get_technical_score(df)
            key_levels = self.md.get_key_levels(df)

            msg = self.bot.format_technical_analysis(price, tech, key_levels)
            self.bot.send_message(msg, chat_id=chat_id)

        except Exception as e:
            self.bot.send_message(f"❌ এনালাইসিস করতে সমস্যা হয়েছে: {e}", chat_id=chat_id)

    def _cmd_calendar(self, chat_id: str):
        """📅 আজকের ইকোনমিক ইভেন্ট"""
        self.bot.send_message("📅 <b>আজকের ইকোনমিক ক্যালেন্ডার সংগ্রহ করা হচ্ছে...</b>", chat_id=chat_id)
        try:
            events = self.na.get_economic_calendar()
            msg    = self.bot.format_economic_calendar(events)
            self.bot.send_message(msg, chat_id=chat_id)
        except Exception as e:
            self.bot.send_message(f"❌ এরর: {e}", chat_id=chat_id)

    def _cmd_report(self, chat_id: str):
        """📊 আজকের রিপোর্ট"""
        try:
            stats = self.se.get_daily_stats()
            msg   = self.bot.format_daily_report(stats)
            self.bot.send_message(msg, chat_id=chat_id)
        except Exception as e:
            self.bot.send_message(f"❌ রিপোর্ট তৈরিতে এরর: {e}", chat_id=chat_id)

    def _cmd_weekly(self, chat_id: str):
        """🗓️ সাপ্তাহিক রিপোর্ট"""
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
            self.bot.send_message(f"❌ সাপ্তাহিক রিপোর্টে এরর: {e}", chat_id=chat_id)

    def _cmd_scan(self, chat_id: str):
        """⚡ দ্রুত মার্কেট স্ক্যান"""
        self.bot.send_message("⚡ <b>তাৎক্ষণিক এআই মার্কেট স্ক্যানিং চলছে...</b>\nলাইভ প্রাইস, চার্ট ভলাটিলিটি ও সেন্টিমেন্ট স্ক্যান করা হচ্ছে।", chat_id=chat_id)
        try:
            signal = self.sch.run_analysis(send_regardless=True)
            price  = self.md.get_current_price() or 0
            if signal and signal.get("direction") != "NEUTRAL":
                msg = self.bot.format_signal_message(signal)
            else:
                msg = (
                    f"⚡ <b>তাৎক্ষণিক মার্কেট স্ক্যান সম্পন্ন</b>\n"
                    f"━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                    f"🥇 বর্তমান গোল্ড প্রাইস: <code>${price}</code>\n"
                    f"⚖️ অবস্থা: <b>নিরপেক্ষ (সাইডওয়েজ রেন্জ)</b>\n"
                    f"📊 টেকনিক্যাল স্কোর: <code>{signal.get('tech_score', 50) if signal else 50}/100</code>\n"
                    f"📰 নিউজ সেন্টিমেন্ট স্কোর: <code>{signal.get('news_score', 50) if signal else 50}/100</code>\n\n"
                    f"💡 <i>মার্কেটে সুযোগ আসলেই সাথে সাথে এআই অটোমেটিক নোটিফিকেশন পাঠিয়ে দেবে।</i>"
                )
            self.bot.send_message(msg, chat_id=chat_id)
        except Exception as e:
            self.bot.send_message(f"❌ স্ক্যান এরর: {e}", chat_id=chat_id)

    def _cmd_status(self, chat_id: str):
        """⚙️ সিস্টেম স্ট্যাটাস"""
        try:
            price   = self.md.get_current_price()
            is_open = self.md.is_market_open()
            jobs    = self.sch.get_jobs_status()
            stats   = self.se.get_daily_stats()

            jobs_text = ""
            for j in jobs[:5]:
                jobs_text += f"  ✅ {j['name']}: {j['next_run'][:16]}\n"

            msg = f"""⚙️ <b>সিস্টেম ও সার্ভার স্ট্যাটাস</b>
━━━━━━━━━━━━━━━━━━━━━━━━━
🤖 এআই সিস্টেম: <b>সম্পূর্ণ সক্রিয় (ONLINE)</b>
🥇 গোল্ড প্রাইস: <code>${price}</code> (TradingView OANDA:XAUUSD)
📊 মার্কেট স্ট্যাটাস: {"🟢 উন্মুক্ত (OPEN)" if is_open else "🔴 বন্ধ (CLOSED)"}
🧠 এআই ইঞ্জিন: {"✅ Gemini 3.8 Flash সক্রিয়" if self.ai.available else "❌ কনফিগার করা হয়নি"}
⚡ স্পাইক সেন্সর: ✅ সক্রিয় (প্রতি ৪৫ সেকেন্ড অন্তর চেক)

📋 <b>আজকের পারফরম্যান্স:</b>
  মোট সিগনাল: {stats.get('total', 0)} টি
  উইন রেট: {stats.get('win_rate', 0)}%

⏰ <b>স্বয়ংক্রিয় ব্যাকগ্রাউন্ড জবস:</b>
{jobs_text if jobs_text else "  লোড হচ্ছে..."}
━━━━━━━━━━━━━━━━━━━━━━━━━
🤖 <i>এআই গোল্ড সিগনাল সিস্টেম ২৪/৭ নজরদারিতে রয়েছে</i>"""
            self.bot.send_message(msg, chat_id=chat_id)
        except Exception as e:
            self.bot.send_message(f"❌ স্ট্যাটাস এরর: {e}", chat_id=chat_id)

    def _cmd_help(self, chat_id: str):
        """💡 ট্রেডিং গাইড ও সাহায্য"""
        msg = self.bot.format_help_message()
        self.bot.send_message(msg, chat_id=chat_id)

    def _cmd_start(self, chat_id: str):
        """স্টার্ট কমান্ড"""
        self.bot.send_startup_message()

    def _cmd_unknown(self, chat_id: str):
        self.bot.send_message(
            "❓ কমান্ডটি বুঝতে পারিনি। নিচের ছবির মতো বাটনগুলো চাপুন অথবা /help কমান্ড ব্যবহার করুন।",
            chat_id=chat_id,
        )
