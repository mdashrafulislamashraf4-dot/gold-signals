"""
============================================================
  modules/telegram_bot.py
  Telegram Bot — সব ধরনের মেসেজ ফরম্যাট ও পাঠানো
  (বাংলা ইন্টারফেস + ছবির মতো কাস্টম বাটন কিবোর্ড)
============================================================
"""

import logging
from datetime import datetime
from typing import Optional, Union

import requests

from config import SIGNAL_CHECK_INTERVAL

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────
# ছবির মতো কাস্টম ২-কলাম বাটন কিবোর্ড (Reply Keyboard)
# ─────────────────────────────────────────────────────────
MAIN_KEYBOARD = {
    "keyboard": [
        [{"text": "🎯 লাইভ সিগনাল"}, {"text": "💰 গোল্ড লাইভ প্রাইস"}],
        [{"text": "🔍 টেকনিক্যাল এনালাইসিস"}, {"text": "📰 ব্রেকিং নিউজ ও প্রভাব"}],
        [{"text": "📅 আজকের ইকোনমিক ইভেন্ট"}, {"text": "📊 আজকের রিপোর্ট"}],
        [{"text": "🗓️ সাপ্তাহিক রিপোর্ট"}, {"text": "⚡ দ্রুত মার্কেট স্ক্যান"}],
        [{"text": "📋 চেকলিস্ট ও নিয়ম"}, {"text": "⚙️ সিস্টেম স্ট্যাটাস"}],
        [{"text": "💡 ট্রেডিং গাইড ও সাহায্য"}],
    ],
    "resize_keyboard": True,
    "persistent": True,
    "is_persistent": True,
}


class TelegramBot:
    """Telegram Bot API wrapper with Bengali templates and custom reply buttons"""

    BASE_URL = "https://api.telegram.org/bot{token}/{method}"

    def __init__(self, token: str, chat_ids: list):
        self.token    = token
        self.chat_ids = chat_ids if isinstance(chat_ids, list) else [chat_ids]

    # ─────────────────────────────────────────────────────────
    # Core Send Methods
    # ─────────────────────────────────────────────────────────
    def send_message(self, text: str, chat_id: str = None, parse_mode: str = "HTML",
                     disable_preview: bool = True, reply_markup: dict = None) -> bool:
        """টেলিগ্রামে মেসেজ পাঠায় এবং সাথে কাস্টম বাটন কিবোর্ড যুক্ত করে"""
        targets = [chat_id] if chat_id else self.chat_ids
        success = True
        markup = reply_markup if reply_markup is not None else MAIN_KEYBOARD

        for cid in targets:
            try:
                url = self.BASE_URL.format(token=self.token, method="sendMessage")
                payload = {
                    "chat_id":                  cid,
                    "text":                     text,
                    "parse_mode":               parse_mode,
                    "disable_web_page_preview": disable_preview,
                    "reply_markup":             markup,
                }
                resp = requests.post(url, json=payload, timeout=30)
                if not resp.ok:
                    logger.error(f"Telegram send failed for {cid}: {resp.text}")
                    success = False
                else:
                    logger.info(f"Message sent to {cid}")
            except Exception as e:
                logger.error(f"Telegram error for {cid}: {e}")
                success = False

        return success

    def send_photo(self, image_path: str, caption: str = "", chat_id: str = None) -> bool:
        """ছবি পাঠায়"""
        targets = [chat_id] if chat_id else self.chat_ids
        for cid in targets:
            try:
                url = self.BASE_URL.format(token=self.token, method="sendPhoto")
                with open(image_path, "rb") as f:
                    resp = requests.post(
                        url,
                        data={
                            "chat_id": cid,
                            "caption": caption,
                            "parse_mode": "HTML",
                            "reply_markup": requests.utils.json.dumps(MAIN_KEYBOARD),
                        },
                        files={"photo": f},
                        timeout=30,
                    )
                if not resp.ok:
                    logger.error(f"Photo send failed: {resp.text}")
            except Exception as e:
                logger.error(f"Photo send error: {e}")
        return True

    # ─────────────────────────────────────────────────────────
    # Signal Alert Format (বাংলায় + ট্রেডিং প্যারামিটার)
    # ─────────────────────────────────────────────────────────
    def format_signal_message(self, signal: dict, current_price: float = None) -> str:
        """ট্রেডিং সিগনাল সহজ ও পরিষ্কারভাবে বাংলায় ফরম্যাট করে (মাস্টার স্ট্র্যাটেজি ও SMC প্যারামিটার সহ)"""
        direction = signal.get("direction", "NEUTRAL")
        confidence = signal.get("confidence", 0)
        trade_num = signal.get("daily_trade_num") or signal.get("id", 1)

        if direction == "BUY":
            dir_text = "🟢 BUY (বাই)"
        elif direction == "SELL":
            dir_text = "🔴 SELL (সেল)"
        else:
            dir_text = "⚪ NEUTRAL"

        entry = signal.get("entry", 0)
        tp1   = signal.get("tp1", 0)
        tp2   = signal.get("tp2", 0)
        tp3   = signal.get("tp3", 0)
        sl    = signal.get("sl", 0)
        tf    = signal.get("timeframe", "4H-1H-15m-5m")
        rr    = signal.get("rr_ratio", "1:2.0")
        lot   = signal.get("suggested_lot", 0.01)
        checklist_score = signal.get("checklist_score", "")

        setup_type = signal.get("setup_type")
        active_ref = signal.get("active_ref", {})

        if setup_type == "ADDITIONAL":
            header = f"🔥 <b>আজকের ট্রেড #{trade_num} — নতুন সেটাপ (XAUUSD)</b>"
            ref_num = active_ref.get("daily_trade_num") or active_ref.get("id", "")
            ref_dir = active_ref.get("direction", "")
            extra_line = f"📌 <i>পূর্ববর্তী ট্রেড #{ref_num} {ref_dir} চলমান রেখেই নতুন সুযোগ</i>\n"
        elif setup_type == "REVERSAL":
            header = f"🔄 <b>আজকের ট্রেড #{trade_num} — মার্কেট রিভার্সাল (XAUUSD)</b>"
            ref_num = active_ref.get("daily_trade_num") or active_ref.get("id", "")
            ref_dir = active_ref.get("direction", "")
            extra_line = f"⚠️ <i>পূর্ববর্তী ট্রেড #{ref_num} {ref_dir} ক্লোজ করে নতুন ট্রেন্ড এন্ট্রি</i>\n"
        else:
            header = f"🎯 <b>আজকের ট্রেড #{trade_num} — মাস্টার স্ট্র্যাটেজি (XAUUSD)</b>"
            extra_line = ""

        # Confluence bullet points
        reasons = signal.get("reasoning", [])
        reason_text = ""
        if reasons:
            reason_text = "\n💡 <b>সেটআপ লজিক:</b>\n" + "\n".join([f"  • {r}" for r in reasons[:3]]) + "\n"

        chk_badge = f" | 📋 চেকলিস্ট: <b>{checklist_score} পাস</b>" if checklist_score else ""

        msg = f"""{header}
━━━━━━━━━━━━━━━━━
⚡ <b>অ্যাকশন:</b> <b>{dir_text}</b>
💰 <b>এন্ট্রি (Entry):</b> <code>${entry}</code>
🎯 <b>TP1 (টার্গেট ১):</b> <code>${tp1}</code>
🔥 <b>TP2 (টার্গেট ২):</b> <code>${tp2}</code>
🚀 <b>TP3 (টার্গেট ৩):</b> <code>${tp3}</code>
🛑 <b>স্টপ লস (SL):</b> <code>${sl}</code>
⚖️ <b>রিস্ক-টু-রিওয়ার্ড (R:R):</b> <code>{rr}</code>
⏱️ <b>টাইমফ্রেম:</b> {tf} | 🤖 <b>কনফিডেন্স:</b> {confidence}%{chk_badge}
{extra_line}{reason_text}━━━━━━━━━━━━━━━━━
🛡️ <b>রিস্ক ম্যানেজমেন্ট:</b>
  • প্রতি ট্রেডে রিস্ক: <b>০.৫%</b> (প্রস্তাবিত লট: <code>{lot}</code> / $1000)
📌 <i>স্টপ লস কখনোই সরিয়ে ক্ষতি বাড়াবেন না</i>"""

        return msg

    def format_no_trade_message(self, data: dict, current_price: float) -> str:
        """ভালো সেটআপ না থাকলে নো-ট্রেড স্ট্যাটাস ও লিকুইডিটি ম্যাপ বাংলায় ফরম্যাট করে"""
        liquidity = data.get("liquidity", {})
        session = liquidity.get("current_session", "সাধারণ সেশন")
        score = data.get("checklist_score", "0/9")
        reasons = data.get("reasoning", ["পারফেক্ট ইনস্টিটিউশনাল কনফার্মেশন অপেক্ষমান"])

        reason_str = "\n".join([f"  • {r}" for r in reasons[:3]])

        pdh = liquidity.get("pdh", "N/A")
        pdl = liquidity.get("pdl", "N/A")
        ah = liquidity.get("asian_high", "N/A")
        al = liquidity.get("asian_low", "N/A")

        return f"""🟡 <b>মার্কেট স্ট্যাটাস: No Trade (অপেক্ষা করুন)</b>
━━━━━━━━━━━━━━━━━
💰 <b>বর্তমান XAUUSD প্রাইস:</b> <code>${current_price}</code>
⏱️ <b>বর্তমান সেশন:</b> {session}
📈 <b>4H ট্রেন্ড:</b> <b>{data.get('trend_4h', 'N/A')}</b> | 🎯 <b>1H বায়াস:</b> <b>{data.get('bias_1h', 'N/A')}</b>

🗺️ <b>লিকুইডিটি ম্যাপ (SMC):</b>
  • Asian Session: High <code>${ah}</code> | Low <code>${al}</code>
  • Previous Day: High <code>${pdh}</code> | Low <code>${pdl}</code>

📋 <b>মাস্টার স্ট্র্যাটেজি চেকলিস্ট:</b> <b>{score} উত্তীর্ণ</b>
⚡ <b>বর্তমান অবস্থা:</b>
{reason_str}

━━━━━━━━━━━━━━━━━
💡 <i>'No Setup = No Trade' — প্রতিদিন ট্রেড নেওয়া লক্ষ্য নয়, ভালো সেটআপ এলে তবেই এন্ট্রি।</i>"""

    # ─────────────────────────────────────────────────────────
    # TP/SL Hit Alert (বাংলায়)
    # ─────────────────────────────────────────────────────────
    def format_tp_sl_alert(self, alert_type: str, signal: dict, current_price: float) -> str:
        """TP বা SL হিট হলে সংক্ষেপে পরিষ্কার বাংলায় নোটিফিকেশন পাঠায় (আজকের ট্রেড নম্বর উল্লেখ সহ)"""
        trade_num = signal.get("daily_trade_num") or signal.get("id", 1)
        direction = signal.get("direction", "")
        dir_text  = "🟢 BUY" if direction == "BUY" else "🔴 SELL"
        entry     = signal.get("entry_price", signal.get("entry", 0))
        diff      = abs(round(current_price - entry, 2))
        pips      = round(diff * 10, 1)

        if alert_type == "TP1":
            title = f"✅ <b>আজকের ট্রেড #{trade_num}-এর TP1 হিট করেছে!</b> 🎯"
            body = (
                f"⚡ <b>ট্রেড:</b> {dir_text} @ <code>${entry}</code>\n"
                f"📍 <b>বর্তমান প্রাইস:</b> <code>${current_price}</code>\n"
                f"💵 <b>অর্জিত মুনাফা:</b> <code>+${diff} USD (+{pips} pips)</code>\n"
                f"💡 <b>পরামর্শ:</b> SL এন্ট্রি প্রাইসে (Breakeven) আনুন"
            )
        elif alert_type == "TP2":
            title = f"🎉 <b>আজকের ট্রেড #{trade_num}-এর TP2 হিট করেছে!</b> 🔥"
            body = (
                f"⚡ <b>ট্রেড:</b> {dir_text} @ <code>${entry}</code>\n"
                f"📍 <b>বর্তমান প্রাইস:</b> <code>${current_price}</code>\n"
                f"💵 <b>অর্জিত মুনাফা:</b> <code>+${diff} USD (+{pips} pips)</code>\n"
                f"💡 <b>পরামর্শ:</b> কিছু প্রফিট বুক করুন বা ট্রেইলিং SL ব্যবহার করুন"
            )
        elif alert_type == "TP3":
            title = f"🚀 <b>আজকের ট্রেড #{trade_num}-এর TP3 হিট করেছে! (JACKPOT)</b> 💎"
            body = (
                f"⚡ <b>ট্রেড:</b> {dir_text} @ <code>${entry}</code>\n"
                f"📍 <b>বর্তমান প্রাইস:</b> <code>${current_price}</code>\n"
                f"💵 <b>মোট মুনাফা:</b> <code>+${diff} USD (+{pips} pips)</code>\n"
                f"💡 <b>পরামর্শ:</b> সর্বোচ্চ টার্গেট অর্জিত, ট্রেড ক্লোজ করে সম্পূর্ণ প্রফিট নিন"
            )
        elif alert_type == "SL":
            title = f"🛑 <b>আজকের ট্রেড #{trade_num}-এর স্টপ লস (SL) হিট করেছে!</b> ❌"
            body = (
                f"⚡ <b>ট্রেড:</b> {dir_text} @ <code>${entry}</code>\n"
                f"📍 <b>বর্তমান প্রাইস:</b> <code>${current_price}</code>\n"
                f"📉 <b>লসের পরিমাণ:</b> <code>-${diff} USD (-{pips} pips)</code>\n"
                f"💡 <b>পরামর্শ:</b> স্টপ লস মেনে চলুন, রিভেঞ্জ ট্রেডিং পরিহার করুন"
            )
        elif alert_type == "BREAKEVEN":
            title = f"🛡️ <b>আজকের ট্রেড #{trade_num} ব্রেকইভেনে ক্লোজ হয়েছে!</b> ⚖️"
            body = (
                f"⚡ <b>ট্রেড:</b> {dir_text} @ <code>${entry}</code>\n"
                f"📍 <b>এক্সিট প্রাইস:</b> <code>${current_price}</code>\n"
                f"⚖️ <b>ফলাফল:</b> <code>$0.00 USD (ক্যাপিটাল ১০০% সুরক্ষিত)</code>\n"
                f"💡 <b>তথ্য:</b> TP1 অর্জনের পর SL এন্ট্রিতে থাকায় কোনো লস হয়নি"
            )
        else:
            title = f"ℹ️ <b>আজকের ট্রেড #{trade_num} আপডেট</b>"
            body = f"📍 <b>বর্তমান মার্কেট প্রাইস:</b> <code>${current_price}</code>"

        return f"""{title}
━━━━━━━━━━━━━━━━━
{body}
━━━━━━━━━━━━━━━━━
🤖 <i>এআই গোল্ড সিগনাল সিস্টেম</i>"""

    # ─────────────────────────────────────────────────────────
    # News Alert (সম্পূর্ণ বাংলায়)
    # ─────────────────────────────────────────────────────────
    def format_news_alert(self, news: dict, impact_analysis: str = "") -> str:
        """গুরুত্বপূর্ণ নিউজ অ্যালার্ট বাংলায় ফরম্যাট করে"""
        impact  = news.get("impact", "MEDIUM")
        title   = news.get("title", "")
        source  = news.get("source", "")
        link    = news.get("link", "")

        if impact == "HIGH":
            emoji = "🚨🚨"
            impact_text = "উচ্চ ঝুঁকি ও তীব্র প্রভাব (HIGH IMPACT)"
        elif impact == "MEDIUM":
            emoji = "⚠️"
            impact_text = "মাঝারি প্রভাব (MEDIUM IMPACT)"
        else:
            emoji = "📰"
            impact_text = "সাধারণ আপডেট (LOW IMPACT)"

        msg = f"""{emoji} <b>গোল্ড মার্কেট ব্রেকিং নিউজ সতর্কতা</b> {emoji}
━━━━━━━━━━━━━━━━━━━━━━━━━
📌 <b>শিরোনাম:</b> <i>{title[:200]}</i>

📎 <b>সংবাদের সূত্র:</b> <i>{source}</i>
⚡ <b>প্রভাবের মাত্রা:</b> <b>{impact_text}</b>
"""
        if impact_analysis:
            msg += f"\n🤖 <b>এআই প্রভাব বিশ্লেষণ ও পরামর্শ:</b>\n{impact_analysis}\n"

        if link:
            msg += f'\n🔗 <a href="{link}">সম্পূর্ণ সংবাদ পড়ুন</a>'

        msg += f"""
━━━━━━━━━━━━━━━━━━━━━━━━━
🤖 <i>এআই গোল্ড সিস্টেম | হঠাৎ তীব্র পরিবর্তনের জন্য পজিশন নজরে রাখুন!</i>"""

        return msg

    # ─────────────────────────────────────────────────────────
    # Sudden Volatility / Rapid Movement Alert (বাংলায়)
    # ─────────────────────────────────────────────────────────
    def format_volatility_alert(self, current_price: float, diff: float, duration_mins: int = 5) -> str:
        """হঠাৎ তীব্র মার্কেট মুভমেন্টের তাৎক্ষণিক বাংলা সতর্কতা"""
        direction = "তীব্র ঊর্ধ্বগতি (Bullish Surge 🟢)" if diff > 0 else "তীব্র পতন (Bearish Dump 🔴)"
        arrow = "📈" if diff > 0 else "📉"

        return f"""⚡⚡ <b>জরুরি মার্কেট অ্যালার্ট: গোল্ডে হঠাৎ তীব্র ওঠানামা!</b> ⚡⚡
━━━━━━━━━━━━━━━━━━━━━━━━━
{arrow} <b>মুভমেন্ট:</b> <b>{direction}</b>
📍 <b>বর্তমান গোল্ড প্রাইস:</b> <code>${current_price}</code>
⏱️ <b>গত {duration_mins} মিনিটে পরিবর্তন:</b> <code>{'+' if diff > 0 else ''}{diff:.2f} USD</code>

🚨 <b>পরিস্থিতি:</b>
কোনো বড় আন্তর্জাতিক ভূরাজনৈতিক ঘটনা, যুদ্ধ পরিস্থিতি বা অর্থনৈতিক ঘোষণার কারণে গোল্ড মার্কেটে হঠাৎ তীব্র স্পাইক/অস্থিরতা তৈরি হয়েছে!

💡 <b>ট্রেডারদের প্রতি জরুরি পরামর্শ:</b>
• চলমান ট্রেডে স্টপ লস নিশ্চিত করুন।
• কোনো ফোমো (FOMO) বা তাড়াহুড়া করে বিপরীত ট্রেড ওপেন করবেন না।
• মার্কেট কিছুটা শান্ত হওয়া পর্যন্ত নতুন এন্ট্রি নেওয়া থেকে বিরত থাকুন।
━━━━━━━━━━━━━━━━━━━━━━━━━
🤖 <i>এআই গোল্ড রিয়েলটাইম ওয়াচডগ</i>"""

    # ─────────────────────────────────────────────────────────
    # Daily Report (বাংলায়)
    # ─────────────────────────────────────────────────────────
    def format_daily_report(self, stats: dict, date: str = None) -> str:
        """দৈনিক পারফরম্যান্স রিপোর্ট বাংলায় ফরম্যাট করে"""
        date    = date or stats.get("date", "আজকের দিন")
        total   = stats.get("total", 0)
        tp_hits = stats.get("tp_hits", 0)
        sl_hits = stats.get("sl_hits", 0)
        pending = stats.get("pending", 0)
        win_rate = stats.get("win_rate", 0)

        if win_rate >= 70:
            performance_emoji = "🏆 অসাধারণ লাভজনক (Excellent)"
        elif win_rate >= 55:
            performance_emoji = "✅ ভালো লাভজনক (Good)"
        elif win_rate >= 40:
            performance_emoji = "⚠️ মোটামুটি (Average)"
        else:
            performance_emoji = "❌ সতর্ক থাকুন (Needs Review)"

        bar_len = int(win_rate / 10)
        rate_bar = "█" * bar_len + "░" * (10 - bar_len)

        msg = f"""📊 <b>দৈনিক ট্রেডিং পারফরম্যান্স রিপোর্ট</b>
🗓️ <b>তারিখ:</b> {date}
━━━━━━━━━━━━━━━━━━━━━━━━━

📈 <b>সিগনালের সারসংক্ষেপ:</b>
  📌 মোট সিগনাল প্রদান: <b>{total} টি</b>
  ✅ সফলভাবে লাভ অর্জিত (TP Hit): <b>{tp_hits} টি</b>
  ❌ স্টপ লস হিট (SL Hit): <b>{sl_hits} টি</b>
  ⏳ ফলাফল প্রক্রিয়াধীন (Active): <b>{pending} টি</b>

🎯 <b>সফলতার হার (Win Rate): {win_rate}%</b>
[{rate_bar}]
মূল্যায়ন: <b>{performance_emoji}</b>

"""
        signals = stats.get("signals", [])[:10]
        if signals:
            msg += "📋 <b>আজকের ট্রেডগুলোর তালিকা:</b>\n"
            for s in signals:
                trade_num = s.get("daily_trade_num") or s.get("id", 1)
                result_icon = "✅" if s.get("tp_hit", 0) > 0 else ("❌" if s.get("sl_hit", 0) > 0 else "⏳")
                dir_icon    = "🟢 BUY" if s.get("direction") == "BUY" else "🔴 SELL"
                res_text    = "মুনাফা অর্জিত" if s.get("tp_hit", 0) > 0 else ("স্টপ লস" if s.get("sl_hit", 0) > 0 else "চলমান")
                msg += f"  {result_icon} <b>ট্রেড #{trade_num}:</b> {dir_icon} @ <code>${s.get('entry_price')}</code> — <i>{res_text}</i>\n"

        msg += f"""
━━━━━━━━━━━━━━━━━━━━━━━━━
🤖 <i>এআই গোল্ড সিগনাল সিস্টেম | দৈনিক রিপোর্ট</i>
💡 <i>নিয়মিত মানি ম্যানেজমেন্ট অনুসরণই দীর্ঘমেয়াদে ধারাবাহিক লাভের চাবিকাঠি!</i>"""

        return msg

    # ─────────────────────────────────────────────────────────
    # Weekly Report (বাংলায়)
    # ─────────────────────────────────────────────────────────
    def format_weekly_report(self, stats: dict, ai_summary: str = "") -> str:
        """সাপ্তাহিক পারফরম্যান্স রিপোর্ট বাংলায় ফরম্যাট করে"""
        total    = stats.get("total", 0)
        tp_hits  = stats.get("tp_hits", 0)
        sl_hits  = stats.get("sl_hits", 0)
        win_rate = stats.get("win_rate", 0)
        buys     = stats.get("buys", 0)
        sells    = stats.get("sells", 0)
        from_date = stats.get("from_date", "চলতি সপ্তাহ")

        if win_rate >= 70:
            grade = "A+ 🏆 (অসাধারণ ফলাফল)"
        elif win_rate >= 60:
            grade = "A 🥇 (চমৎকার লাভজনক)"
        elif win_rate >= 50:
            grade = "B 🥈 (সন্তোষজনক)"
        elif win_rate >= 40:
            grade = "C 🥉 (গড়পড়তা)"
        else:
            grade = "D ⚠️ (উন্নতি প্রয়োজন)"

        msg = f"""🗓️ <b>সাপ্তাহিক গোল্ড ট্রেডিং রিপোর্ট</b>
📅 <b>সপ্তাহ:</b> {from_date}
━━━━━━━━━━━━━━━━━━━━━━━━━

📊 <b>সাপ্তাহিক পরিসংখ্যান:</b>
  📌 সর্বমোট সিগনাল: <b>{total} টি</b>
  📈 BUY সিগনাল: <b>{buys} টি</b>
  📉 SELL সিগনাল: <b>{sells} টি</b>
  ✅ সফল মুনাফা (TP Hit): <b>{tp_hits} টি</b>
  ❌ স্টপ লস (SL Hit): <b>{sl_hits} টি</b>

🎯 <b>সামগ্রিক উইন রেট: {win_rate}%</b>
📝 <b>পারফরম্যান্স গ্রেড: {grade}</b>

"""
        if ai_summary:
            msg += f"🤖 <b>এআই সাপ্তাহিক পর্যালোচনা ও আগামী সপ্তাহের দৃষ্টিভঙ্গি:</b>\n<i>{ai_summary}</i>\n\n"

        msg += f"""━━━━━━━━━━━━━━━━━━━━━━━━━
🤖 <i>এআই গোল্ড সিগনাল সিস্টেম | সাপ্তাহিক রিপোর্ট</i>
📅 <i>পরবর্তী সপ্তাহের জন্য মানসিকভাবে প্রস্তুতি নিন এবং ডিসিপ্লিন বজায় রাখুন!</i>"""

        return msg

    # ─────────────────────────────────────────────────────────
    # Price Update (বাংলায়)
    # ─────────────────────────────────────────────────────────
    def format_price_update(self, price: float, correlated: dict) -> str:
        """বর্তমান গোল্ড প্রাইস ও মার্কেট আপডেট বাংলায় ফরম্যাট করে"""
        corr_text = ""
        for name, val in correlated.items():
            chg = val.get("change_pct", 0)
            arrow = "▲" if chg >= 0 else "▼"
            emoji = "🟢" if chg >= 0 else "🔴"
            corr_text += f"  {emoji} {name}: <code>{val.get('price', 'N/A')}</code> ({arrow}{abs(chg)}%)\n"

        return f"""💰 <b>গোল্ড (XAUUSD) লাইভ মার্কেট আপডেট</b>
━━━━━━━━━━━━━━━━━━━━━━━━━
🥇 <b>বর্তমান স্পট প্রাইস:</b> <code>${price}</code> USD/oz
📊 <b>সোর্স:</b> সরাসরি TradingView (OANDA:XAUUSD)

🌐 <b>সম্পর্কিত আন্তর্জাতিক মার্কেট:</b>
{corr_text if corr_text else "  ডেটা লোড হচ্ছে..."}
━━━━━━━━━━━━━━━━━━━━━━━━━
🤖 <i>এআই গোল্ড সিগনাল সিস্টেম</i>"""

    # ─────────────────────────────────────────────────────────
    # Full Technical Analysis (বাংলায়)
    # ─────────────────────────────────────────────────────────
    def format_technical_analysis(self, price: float, tech: dict, key_levels: dict) -> str:
        """সম্পূর্ণ টেকনিক্যাল এনালাইসিস বাংলায় ফরম্যাট করে"""
        details    = tech.get("details", {})
        patterns   = tech.get("patterns", [])
        fib        = tech.get("fibonacci", {})

        pat_text = ""
        for p in patterns[:3]:
            pat_text += f"  🕯️ {p[2]}\n"

        fib_text = ""
        for level, val in list(fib.items())[:5]:
            fib_text += f"  • ফিবোনাচ্চি {level}%: <code>{val}</code>\n"

        sup = ", ".join(str(s) for s in key_levels.get("support", [])[:3])
        res = ", ".join(str(r) for r in key_levels.get("resistance", [])[:3])

        dir_bn = "বুলিশ (উর্ধ্বমুখী 🟢)" if tech.get('direction') == 'BUY' else ("বেয়ারিশ (নিম্নমুখী 🔴)" if tech.get('direction') == 'SELL' else "নিরপেক্ষ (সাইডওয়েজ ⚪)")

        # Divergence text
        divs = tech.get("divergences", [])
        div_text = ""
        for d in divs[:2]:
            div_text += f"  ⚡ {d[2]}\n"

        # Squeeze status
        sq_status = str(details.get("Squeeze", "RELEASED"))
        sq_icon = "🔴 কম্প্রেশন (ব্রেকআউট লোডিং)" if "ACTIVE" in sq_status else "🟢 সাধারণ ভোলাটিলিটি"

        # SuperTrend icon
        st_dir = details.get("SuperTrend", "N/A")
        st_icon = "🟢 BULLISH" if st_dir == "BULLISH" else ("🔴 BEARISH" if st_dir == "BEARISH" else "N/A")

        msg = f"""🔍 <b>৩০+ ইন্ডিকেটর পূর্ণাঙ্গ টেকনিক্যাল এনালাইসিস</b>
━━━━━━━━━━━━━━━━━━━━━━━━━
💰 <b>XAUUSD প্রাইস:</b> <code>${price}</code>
📈 <b>সামগ্রিক ট্রেন্ড:</b> <b>{dir_bn}</b>
🎯 <b>টেকনিক্যাল স্কোর:</b> <b>{tech.get('score', 50)}/100</b>

📈 <b>ট্রেন্ড ইন্ডিকেটরসমূহ (Trend):</b>
  • SuperTrend (10,3): <b>{st_icon}</b> (<code>${details.get('SuperTrend_Val', 'N/A')}</code>)
  • Parabolic SAR: <code>${details.get('PSAR', 'N/A')}</code>
  • Hull Moving Avg (HMA 16): <code>${details.get('HMA_16', 'N/A')}</code>
  • EMA 20: <code>${details.get('EMA_20', 'N/A')}</code> | EMA 50: <code>${details.get('EMA_50', 'N/A')}</code>
  • EMA 200 (ম্যাক্রো ট্রেন্ড): <code>${details.get('EMA_200', 'N/A')}</code>
  • ইচিমোকু Tenkan: <code>${details.get('Ichimoku_Tenkan', 'N/A')}</code> | Kijun: <code>${details.get('Ichimoku_Kijun', 'N/A')}</code>

⚡ <b>মোমেন্টাম ও অসিলেটরসমূহ (Oscillators):</b>
  • RSI (14): <code>{details.get('RSI', 'N/A')}</code>
  • MACD: <code>{details.get('MACD', 'N/A')}</code> (সিগনাল: <code>{details.get('MACD_Signal', 'N/A')}</code>)
  • স্টোকাস্টিক (K / D): <code>{details.get('Stochastic_K', 'N/A')} / {details.get('Stochastic_D', 'N/A')}</code>
  • স্টোকাস্টিক RSI (Fast): <code>{details.get('StochRSI_K', 'N/A')}</code>
  • CCI (কমোডিটি ইনডেক্স): <code>{details.get('CCI', 'N/A')}</code>
  • Awesome Oscillator (AO): <code>{details.get('Awesome_Osc', 'N/A')}</code>
  • Williams %R: <code>{details.get('Williams_R', 'N/A')}</code>
  • ADX (ট্রেন্ড শক্তি): <code>{details.get('ADX', 'N/A')}</code>

🌊 <b>ভোলাটিলিটি ও ব্যান্ডস (Volatility & Squeeze):</b>
  • বলিঙ্গার ব্যান্ডস: আপার <code>${details.get('BB_Upper', 'N/A')}</code> | লোয়ার <code>${details.get('BB_Lower', 'N/A')}</code>
  • TTM Bollinger Squeeze: <b>{sq_icon}</b>
  • ATR (গড় অস্থিরতা): <code>${details.get('ATR', 'N/A')}</code>

💼 <b>স্মার্ট মানি ও ভলিউম প্রবাহ (Smart Money Flow):</b>
  • প্রাতিষ্ঠানিক VWAP: <code>${details.get('VWAP', 'N/A')}</code>
  • Money Flow Index (MFI): <code>{details.get('MFI', 'N/A')}</code>
  • Chaikin Money Flow (CMF): <code>{details.get('CMF', 'N/A')}</code>

🏗️ <b>সাপোর্ট, রেজিস্ট্যান্স ও পিভট লেভেল:</b>
  🔻 সাপোর্ট জোন: <code>{sup if sup else 'N/A'}</code>
  🔺 রেজিস্ট্যান্স জোন: <code>{res if res else 'N/A'}</code>
  ⚖️ ডেইলি পিভট (Classic): <code>${details.get('Pivot_Point', key_levels.get('pivot', 'N/A'))}</code>
  ⚡ Camarilla ব্রেকআউট: H4 <code>${details.get('Cam_H4', 'N/A')}</code> | L4 <code>${details.get('Cam_L4', 'N/A')}</code>

📐 <b>ফিবোনাচ্চি গোল্ডেন রেশিও:</b>
{fib_text if fib_text else "  হিসাব করা হচ্ছে..."}
"""
        if div_text:
            msg += f"\n⚡ <b>লুকায়িত ডাইভারজেন্স (Divergence):</b>\n{div_text}"

        if pat_text:
            msg += f"\n🕯️ <b>ডিটেক্ট হওয়া ক্যান্ডেলস্টিক প্যাটার্ন:</b>\n{pat_text}"

        msg += "\n━━━━━━━━━━━━━━━━━━━━━━━━━\n🤖 <i>এআই গোল্ড সিগনাল সিস্টেম | ৩০+ ইন্ডিকেটর কনফার্মেশন ইঞ্জিন</i>"
        return msg

    # ─────────────────────────────────────────────────────────
    # Economic Calendar Alert (বাংলায়)
    # ─────────────────────────────────────────────────────────
    def format_economic_calendar(self, events: list) -> str:
        """ইকোনমিক ক্যালেন্ডার বাংলায় ফরম্যাট করে"""
        if not events:
            return "📅 <b>আজ গোল্ডের উপর প্রভাব ফেলার মতো বড় কোনো ইভেন্ট পাওয়া যায়নি।</b>"

        msg = """📅 <b>আজকের গুরুত্বপূর্ণ ইকোনমিক ইভেন্টসমূহ</b>
━━━━━━━━━━━━━━━━━━━━━━━━━
<i>এই ইভেন্টগুলোর সময় গোল্ড মার্কেটে তীব্র ওঠানামা হতে পারে:</i>

"""
        for ev in events[:8]:
            impact = ev.get("impact", "MEDIUM")
            emoji  = "🔴" if impact == "HIGH" else ("🟡" if impact == "MEDIUM" else "🟢")
            impact_bn = "উচ্চ ঝুঁকি" if impact == "HIGH" else "মাঝারি ঝুঁকি"
            msg += f"{emoji} <b>{ev.get('event', '')[:80]}</b>\n"
            msg += f"   ⚡ মাত্রা: <b>{impact_bn}</b>\n"
            if ev.get("time"):
                msg += f"   ⏰ সময়: <code>{str(ev.get('time', ''))[:40]}</code>\n"
            msg += "\n"

        msg += "━━━━━━━━━━━━━━━━━━━━━━━━━\n🔴 উচ্চ ঝুঁকি (CPI, NFP, Fed) | 🟡 মাঝারি | 🟢 সাধারণ"
        return msg

    # ─────────────────────────────────────────────────────────
    # Help & Trading Guide (বাংলায়)
    # ─────────────────────────────────────────────────────────
    def format_help_message(self) -> str:
        """হেল্প ও ব্যবহারের গাইড বাংলায় ফরম্যাট করে"""
        return """🤖 <b>এআই গোল্ড (XAUUSD) সিগনাল বট — সহায়িকা</b>
━━━━━━━━━━━━━━━━━━━━━━━━━
নিচের ছবিতে দেওয়া বাটনগুলো ব্যবহার করে সরাসরি ১-ক্লিকে সবকিছু জানতে পারবেন:

🎯 <b>লাইভ সিগনাল:</b> বর্তমান সেরা BUY/SELL ট্রেডিং সিগনাল
💰 <b>গোল্ড লাইভ প্রাইস:</b> TradingView-এর হুবহু লাইভ দাম
🔍 <b>টেকনিক্যাল এনালাইসিস:</b> ১২+ ইন্ডিকেটর ও চার্ট প্যাটার্ন
📰 <b>ব্রেকিং নিউজ ও প্রভাব:</b> গোল্ডে প্রভাব ফেলে এমন বিশ্ব সংবাদ
📅 <b>আজকের ইকোনমিক ইভেন্ট:</b> গুরুত্বপূর্ণ অর্থনৈতিক ক্যালেন্ডার
📊 <b>আজকের রিপোর্ট:</b> সারাদিনের লাভ-লস ও পারফরম্যান্স
🗓️ <b>সাপ্তাহিক রিপোর্ট:</b> পুরো সপ্তাহের বিস্তারিত লাভ-ক্ষতি
⚡ <b>দ্রুত মার্কেট স্ক্যান:</b> এই মুহূর্তে তাৎক্ষণিক এআই স্ক্যান
⚙️ <b>সিস্টেম স্ট্যাটাস:</b> সিস্টেম ও সার্ভারের বর্তমান অবস্থা
💡 <b>ট্রেডিং গাইড ও সাহায্য:</b> এই নির্দেশিকা
💰 <b>লট সাইজ ক্যালকুলেটর:</b> <code>/lot [ব্যালেন্স]</code> (যেমন: <code>/lot 1000</code>) লিখে পাঠালে নিরাপদ লট সাইজ পাওয়া যাবে।

━━━━━━━━━━━━━━━━━━━━━━━━━
<b>স্বয়ংক্রিয় নোটিফিকেশন (বাটনে চাপার প্রয়োজন নেই):</b>
  🔔 নতুন সিগনাল পেলেই তাৎক্ষণিক অ্যালার্ট
  ✅ টার্গেট (TP) বা স্টপ লস (SL) হিট অ্যালার্ট
  🚨 বড় কোনো যুদ্ধ বা বিশ্ব সংবাদের তাত্ক্ষণিক বাংলা অ্যালার্ট
  ⚡ হঠাৎ মার্কেট বড় মুভ করলে তাৎক্ষণিক স্পাইক অ্যালার্ট
  📊 প্রতিদিন রাত ১১:৫৯ মিনিটে দৈনিক হিসাব রিপোর্ট
  📅 প্রতি শুক্রবার মার্কেট বন্ধের পর সাপ্তাহিক হিসাব রিপোর্ট

━━━━━━━━━━━━━━━━━━━━━━━━━
⚠️ <b>সোনালী নিয়ম:</b> প্রতিটি ট্রেডে অ্যাকাউন্টের সর্বোচ্চ ১-২% এর বেশি ঝুঁকি নেবেন না!"""

    # ─────────────────────────────────────────────────────────
    # Startup Message (বাংলায়)
    # ─────────────────────────────────────────────────────────
    def send_startup_message(self) -> bool:
        msg = """🚀 <b>এআই গোল্ড (XAUUSD) সিগনাল সিস্টেম সফলভাবে চালু হয়েছে!</b>
━━━━━━━━━━━━━━━━━━━━━━━━━
✅ <b>বট স্ট্যাটাস:</b> সম্পূর্ণ সক্রিয় (ACTIVE)
📊 <b>নজরদারি:</b> XAUUSD (Spot Gold)
🤖 <b>এআই ইঞ্জিন:</b> Google Gemini AI
📰 <b>নিউজ ওয়াচডগ:</b> ২৪/৭ রিয়েলটাইম স্ক্যানিং সক্রিয়
⚡ <b>তীব্র ওঠানামা সেন্সর:</b> সক্রিয় (প্রতি ৪৫ সেকেন্ড পর পর নজরদারি)
⏰ <b>সিগনাল এনালাইসিস:</b> প্রতি {SIGNAL_CHECK_INTERVAL} মিনিট অন্তর মাল্টি-টাইমফ্রেম

💡 <b>নিচের ছবিতে দেওয়া বাটনগুলো ব্যবহার করে যেকোনো তথ্য এক ক্লিকে পেয়ে যান!</b>
━━━━━━━━━━━━━━━━━━━━━━━━━
📌 <i>মার্কেটে সুযোগ আসলেই সাথে সাথে স্বয়ংক্রিয় সিগনাল চলে আসবে!</i>"""
        return self.send_message(msg)

    # ─────────────────────────────────────────────────────────
    # Public Send Wrappers
    # ─────────────────────────────────────────────────────────
    def send_signal(self, signal: dict, current_price: float = None) -> bool:
        if signal.get("direction") in ("NEUTRAL", "NO_TRADE", "WAIT"):
            return False
        msg = self.format_signal_message(signal, current_price)
        return self.send_message(msg)

    def send_no_trade_status(self, master_data: dict, price: float, chat_id: str = None) -> bool:
        msg = self.format_no_trade_message(master_data, price)
        return self.send_message(msg, chat_id=chat_id)

    def send_tp_sl_alert(self, alert_type: str, signal: dict, price: float) -> bool:
        msg = self.format_tp_sl_alert(alert_type, signal, price)
        return self.send_message(msg)

    def send_news_alert(self, news: dict, ai_analysis: str = "") -> bool:
        msg = self.format_news_alert(news, ai_analysis)
        return self.send_message(msg)

    def send_volatility_alert(self, current_price: float, diff: float, duration_mins: int = 5) -> bool:
        msg = self.format_volatility_alert(current_price, diff, duration_mins)
        return self.send_message(msg)

    def send_daily_report(self, stats: dict) -> bool:
        msg = self.format_daily_report(stats)
        return self.send_message(msg)

    def send_weekly_report(self, stats: dict, ai_summary: str = "") -> bool:
        msg = self.format_weekly_report(stats, ai_summary)
        return self.send_message(msg)
