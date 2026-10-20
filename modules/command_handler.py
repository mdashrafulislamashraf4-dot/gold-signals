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
            "📋 চেকলিস্ট ও নিয়ম":         self._cmd_checklist,

            # ── স্ল্যাশ কমান্ড হ্যান্ডলার ──────────────────────
            "/signal":    self._cmd_signal,
            "/price":     self._cmd_price,
            "/news":      self._cmd_news,
            "/analysis":  self._cmd_analysis,
            "/calendar":  self._cmd_calendar,
            "/report":    self._cmd_report,
            "/weekly":    self._cmd_weekly,
            "/scan":      self._cmd_scan,
            "/status":    self._cmd_status,
            "/help":      self._cmd_help,
            "/checklist": self._cmd_checklist,
            "/start":     self._cmd_start,
        }

        # Clean command if starts with /
        if text.startswith("/"):
            lookup_key = text.split()[0].lower().split("@")[0]
        else:
            lookup_key = text

        if lookup_key == "/lot":
            threading.Thread(target=self._cmd_lot, args=(chat_id, text), daemon=True).start()
            return

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
        try:
            active_signals = self.se.get_active_signals()
            price = self.md.get_current_price() or 0

            # যদি ইতিমধ্যে কোনো সিগনাল চালু থাকে, তবে তার লাইভ অগ্রগতি দেখাবে
            if active_signals:
                cur_sig = active_signals[0]
                trade_num = cur_sig.get("daily_trade_num") or cur_sig.get("id", 1)
                direction = cur_sig.get("direction", "")
                dir_icon = "🟢 BUY" if direction == "BUY" else "🔴 SELL"
                tp1 = cur_sig.get("tp1")
                tp2 = cur_sig.get("tp2")
                sl = cur_sig.get("sl")
                entry = cur_sig.get("entry_price", cur_sig.get("entry", 0))
                tp_hit = cur_sig.get("tp_hit", 0)

                status_text = "🎯 TP1 অর্জিত, TP2 এর অপেক্ষায় (SL ব্রেকইভেনে)" if tp_hit == 1 else "চলমান (Active)"

                pnl = round(price - entry, 2) if direction == "BUY" else round(entry - price, 2)
                pnl_str = f"+${pnl}" if pnl >= 0 else f"-${abs(pnl)}"

                msg = f"""🎯 <b>আজকের চলমান ট্রেড #{trade_num} (XAUUSD)</b>
━━━━━━━━━━━━━━━━━
⚡ <b>অ্যাকশন:</b> {dir_icon}
💰 <b>এন্ট্রি:</b> <code>${entry}</code>
📍 <b>লাইভ প্রাইস:</b> <code>${price}</code>
💵 <b>ফ্লোটিং PnL:</b> <code>{pnl_str} USD</code>
🎯 <b>TP1:</b> <code>${tp1}</code> | 🔥 <b>TP2:</b> <code>${tp2}</code>
🛑 <b>স্টপ লস (SL):</b> <code>${sl}</code>
📊 <b>অবস্থা:</b> <b>{status_text}</b>
━━━━━━━━━━━━━━━━━
💡 <i>স্টপ লস (SL) বা টার্গেট অর্জিত না হওয়া পর্যন্ত নতুন কোনো {direction} সিগনাল আসবে না। মার্কেট হঠাৎ ঘুরে গেলে স্বয়ংক্রিয় রিভার্সাল সিগনাল আসবে।</i>"""
                self.bot.send_message(msg, chat_id=chat_id)
                return

            self.bot.send_message("⏳ <b>মার্কেট এনালাইসিস চলছে...</b>\nTradingView ডেটা, ১২+ ইন্ডিকেটর এবং বিশ্ব সংবাদের সেন্টিমেন্ট যাচাই করা হচ্ছে। অনুগ্রহ করে একটু অপেক্ষা করুন।", chat_id=chat_id)
            signal = self.sch.run_analysis(send_regardless=True)
            if not signal or signal.get("direction") == "NEUTRAL" or signal.get("confidence", 0) < 65:
                self.bot.send_message(
                    f"⚪ <b>বর্তমানে কোনো সুস্পষ্ট সিগনাল নেই</b>\n"
                    f"━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                    f"💰 বর্তমান প্রাইস: <code>${price}</code>\n"
                    f"⚖️ মার্কেট এই মুহূর্তে নিরপেক্ষ/সাইডওয়েজ জোনে আছে।\n"
                    f"💡 <i>সিস্টেম ২৪/৭ নজর রাখছে। ভালো কনফার্মেশন পাওয়ার সাথে সাথে স্বয়ংক্রিয় BUY/SELL সিগনাল পাঠানো হবে।</i>",
                    chat_id=chat_id,
                )
        except Exception as e:
            logger.error(f"Cmd signal error: {e}")
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
        """🔍 টেকনিক্যাল এনালাইসিস — মাল্টি-টাইমফ্রেম ইনস্টিটিউশনাল মাস্টার স্ট্র্যাটেজি"""
        self.bot.send_message("🔍 <b>4H → 1H → 15m → 5m ইনস্টিটিউশনাল এনালাইসিস চলছে...</b>", chat_id=chat_id)
        try:
            price  = self.md.get_current_price() or 0
            df_4h  = self.md.get_ohlcv(timeframe="4h", bars=60)
            df_1h  = self.md.get_ohlcv(timeframe="1h", bars=100)
            df_15m = self.md.get_ohlcv(timeframe="15m", bars=150)
            df_5m  = self.md.get_ohlcv(timeframe="5m", bars=60)
            df_1m  = self.md.get_ohlcv(timeframe="1m", bars=60)

            tech = self.ta.analyze_master_strategy(
                df_4h=df_4h,
                df_1h=df_1h,
                df_15m=df_15m,
                df_5m=df_5m,
                current_price=price,
                df_1m=df_1m,
            )

            if tech.get("direction") in ("BUY", "SELL"):
                msg = self.bot.format_signal_message(tech, price)
            else:
                msg = self.bot.format_no_trade_message(tech, price)

            self.bot.send_message(msg, chat_id=chat_id)

        except Exception as e:
            logger.error(f"Analysis command error: {e}", exc_info=True)
            self.bot.send_message(f"❌ এনালাইসিস করতে সমস্যা হয়েছে: {e}", chat_id=chat_id)

    def _cmd_checklist(self, chat_id: str):
        """📋 ১২-দফা প্রাতিষ্ঠানিক চেকলিস্ট ও নিয়ম"""
        msg = """📋 <b>XAUUSD প্রাতিষ্ঠানিক ডুয়াল-ইঞ্জিন — ১২-দফা চেকলিস্ট</b>
━━━━━━━━━━━━━━━━━━━━━━━━━
বড় সুইং বা ছোট স্ক্যাল্প প্রতিটি ট্রেডের পূর্বে এই ১২টি ধাপ যাচাই করা হয়:

1️⃣ <b>Market Structure:</b> BOS / CHoCH (ক্যান্ডেল বডি ক্লোজ বনাম উইক)
2️⃣ <b>Liquidity:</b> BSL / SSL, Equal Highs/Lows ও Major Sweeps
3️⃣ <b>Displacement & FVG:</b> শক্তিশালী মুভ ও আনমিটিগেটেড ইমব্যালেন্স
4️⃣ <b>Order Block (OB):</b> প্রাতিষ্ঠানিক ডিমান্ড ও সাপ্লাই জোন রিঅ্যাকশন
5️⃣ <b>EMA 20/50/200:</b> স্বল্প ও দীর্ঘমেয়াদি ট্রেন্ড অ্যালাইনমেন্ট
6️⃣ <b>RSI 14 & Divergence:</b> মোমেন্টাম ও ফলস ব্রেকআউট রিভার্সাল
7️⃣ <b>ATR 14 Volatility:</b> ডায়নামিক ও লজিক্যাল SL ও TP বাফার
8️⃣ <b>VWAP:</b> ইন্ট্রাডে গড় ভ্যালুয়েশন ও প্রাতিষ্ঠানিক অবস্থান
9️⃣ <b>MACD:</b> মোমেন্টাম বৃদ্ধি বা হ্রাস যাচাই
🔟 <b>Premium / Discount / OTE:</b> ডিসকাউন্টে বাই ও প্রিমিয়ামে সেল
1️⃣1️⃣ <b>5M Confirmation:</b> ক্যান্ডেল ক্লোজ ও রিজেকশন পিন বার
1️⃣2️⃣ <b>Macro & News Safety:</b> CPI, NFP, FOMC নিউজ ঝুঁকি সুরক্ষা

━━━━━━━━━━━━━━━━━━━━━━━━━
⚡ <b>ডুয়াল ইঞ্জিন সুবিধা:</b>
• 🎯 <b>মাস্টার সুইং:</b> ১H/৪H ট্রেন্ড ভিত্তিক বড় ইন্ট্রাডে মুভ (R:R ১:২.০ - ১:৪.০)
• ⚡ <b>কুইক স্ক্যাল্প:</b> লিকুইডিটি সুইপ ও ৫M ডিসপ্লেসমেন্টে দ্রুত এন্ট্রি (R:R ১:১.২ - ১:২.৫)
• 🕒 <b>সার্বক্ষণিক (24/5):</b> কোনো সেশন লক নেই — সেটআপ প্রস্তুত হলেই তাৎক্ষণিক টেলিগ্রাম অ্যালার্ট!"""
        self.bot.send_message(msg, chat_id=chat_id)

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
        """⚡ দ্রুত মার্কেট স্ক্যান — লিকুইডিটি ও সেশন স্ক্যান"""
        self.bot.send_message("⚡ <b>তাৎক্ষণিক প্রাতিষ্ঠানিক লিকুইডিটি ও মার্কেট স্ক্যানিং চলছে...</b>", chat_id=chat_id)
        try:
            price  = self.md.get_current_price() or 0
            df_15m = self.md.get_ohlcv("15m", bars=150)
            liquidity = self.ta.calculate_session_and_liquidity_levels(df_15m)
            active_signals = self.se.get_active_signals()
            active_note = ""
            if active_signals:
                cur = active_signals[0]
                t_num = cur.get("daily_trade_num") or cur.get("id", 1)
                active_note = f"\n📌 <b>চলমান ট্রেড:</b> #{t_num} {cur.get('direction')} @ <code>${cur.get('entry_price')}</code>\n"

            msg = (
                f"⚡ <b>তাৎক্ষণিক মার্কেট স্ক্যান সম্পন্ন</b>\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"🥇 <b>বর্তমান গোল্ড প্রাইস:</b> <code>${price}</code>\n"
                f"⏱️ <b>বর্তমান সেশন:</b> {liquidity.get('current_session', 'N/A')}\n"
                f"🗺️ <b>Asian Range:</b> <code>${liquidity.get('asian_low', 'N/A')}</code> – <code>${liquidity.get('asian_high', 'N/A')}</code>\n"
                f"📍 <b>Previous Day:</b> PDH <code>${liquidity.get('pdh', 'N/A')}</code> | PDL <code>${liquidity.get('pdl', 'N/A')}</code>\n"
                f"{active_note}━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"💡 <i>'🎯 লাইভ সিগনাল' বাটনে চাপলে পূর্ণাঙ্গ চেকলিস্ট সহ বর্তমান এন্ট্রি অবস্থা জানতে পারবেন।</i>"
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

    def _cmd_lot(self, chat_id: str, text: str = ""):
        """💰 নির্ভুল গোল্ড লট সাইজ ক্যালকুলেটর"""
        try:
            parts = text.split()
            balance = 1000.0
            if len(parts) > 1:
                try:
                    balance = float(parts[1].replace("$", "").replace(",", ""))
                except Exception:
                    pass

            # SL distance from active signal or default ATR (e.g. $10)
            active_signals = self.se.get_active_signals()
            sl_dist = 10.0
            if active_signals:
                cur = active_signals[0]
                entry = cur.get("entry_price", 0)
                sl = cur.get("sl", 0)
                if entry and sl:
                    sl_dist = max(1.0, abs(entry - sl))

            risk_pct = 0.5  # 0.5% — সিগনালের সাথে সামঞ্জস্যপূর্ণ (Bug fix: was incorrectly 2%)
            risk_usd = balance * (risk_pct / 100.0)
            # 1 Standard Lot = 100 oz of Gold. Each $1 move = $100 per 1.00 lot
            raw_lot = risk_usd / (sl_dist * 100)
            rec_lot = max(0.01, round(raw_lot, 2))

            msg = f"""💰 <b>গোল্ড (XAUUSD) লট সাইজ ক্যালকুলেটর</b>
━━━━━━━━━━━━━━━━━━━━━━━━━
💼 <b>অ্যাকাউন্ট ব্যালেন্স:</b> <code>${balance:,.2f}</code>
⚠️ <b>নির্ধারিত ঝুঁকি (Risk):</b> <b>{risk_pct}% (${risk_usd:.2f})</b>
🛑 <b>স্টপ লস দূরত্ব:</b> <code>${sl_dist:.2f}</code> ডলার

🎯 <b>আপনার জন্য নিরাপদ লট সাইজ:</b>
👉 <b><code>{rec_lot} Lot</code></b>

💡 <b>ব্যবহারের নিয়ম:</b>
যেকোনো ব্যালেন্সের জন্য সরাসরি লিখুন:
<code>/lot [আপনার ব্যালেন্স]</code>
(যেমন: <code>/lot 500</code> বা <code>/lot 2000</code>)
━━━━━━━━━━━━━━━━━━━━━━━━━
🛡️ <i>সঠিক লট সাইজ ও মানি ম্যানেজমেন্টই আপনার মূলধনকে ১০০% নিরাপদ রাখবে!</i>"""
            self.bot.send_message(msg, chat_id=chat_id)
        except Exception as e:
            self.bot.send_message(f"❌ লট সাইজ ক্যালকুলেশন এরর: {e}", chat_id=chat_id)

    def _cmd_unknown(self, chat_id: str):
        self.bot.send_message(
            "❓ কমান্ডটি বুঝতে পারিনি। নিচের ছবির মতো বাটনগুলো চাপুন অথবা /help কমান্ড ব্যবহার করুন।",
            chat_id=chat_id,
        )
