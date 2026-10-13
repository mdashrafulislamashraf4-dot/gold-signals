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
        [{"text": "⚙️ সিস্টেম স্ট্যাটাস"}, {"text": "💡 ট্রেডিং গাইড ও সাহায্য"}],
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
        """ট্রেডিং সিগনাল ফরম্যাট করে (BUY / SELL বাদে বাকি সব বিশ্লেষণ বাংলায়)"""
        direction = signal.get("direction", "NEUTRAL")
        confidence = signal.get("confidence", 0)

        if direction == "BUY":
            action_text = "🟢 BUY 📈 (কেনার উপযুক্ত সময়)"
            arrow = "⬆️"
        elif direction == "SELL":
            action_text = "🔴 SELL 📉 (বিক্রির উপযুক্ত সময়)"
            arrow = "⬇️"
        else:
            action_text = "⚪ NEUTRAL ↔️ (অপেক্ষা করুন)"
            arrow = "↔️"

        entry = signal.get("entry", 0)
        tp1   = signal.get("tp1", 0)
        tp2   = signal.get("tp2", 0)
        tp3   = signal.get("tp3", 0)
        sl    = signal.get("sl", 0)
        rr    = signal.get("rr_ratio", "1:2")
        tf    = signal.get("timeframe", "H1")
        risk  = signal.get("risk_level", "মাঝারি")
        valid = signal.get("validity", "৪-৮ ঘণ্টা")

        # Confidence bar
        conf_bar = "█" * (confidence // 10) + "░" * (10 - confidence // 10)

        # Reasoning (বাংলায়)
        reasoning = signal.get("reasoning", [])
        reason_text = ""
        for i, r in enumerate(reasoning[:4], 1):
            reason_text += f"  {i}. {r}\n"

        # Warnings (বাংলায়)
        warnings = signal.get("warnings", [])
        warn_text = ""
        for w in warnings[:2]:
            warn_text += f"  ⚠️ {w}\n"

        # Patterns (বাংলায়)
        patterns = signal.get("patterns", [])
        pattern_text = ""
        for p in patterns[:2]:
            pattern_text += f"  🕯️ {p[2]}\n"

        msg = f"""🏆 <b>XAUUSD (গোল্ড) এআই সিগনাল</b> 🏆
━━━━━━━━━━━━━━━━━━━━━━━━━

{arrow} <b>অ্যাকশন: {action_text}</b>
💰 <b>Entry:</b> <code>{entry}</code>
🎯 <b>TP1 (প্রথম টার্গেট):</b> <code>{tp1}</code> (+{abs(round(tp1-entry,1))} ডলার)
🎯 <b>TP2 (দ্বিতীয় টার্গেট):</b> <code>{tp2}</code> (+{abs(round(tp2-entry,1))} ডলার)
🎯 <b>TP3 (সর্বোচ্চ টার্গেট):</b> <code>{tp3}</code> (+{abs(round(tp3-entry,1))} ডলার)
🛑 <b>SL (স্টপ লস):</b> <code>{sl}</code> (-{abs(round(sl-entry,1))} ডলার)
📊 <b>রিস্ক:রিওয়ার্ড অনুপাত (R:R):</b> {rr}
⏱️ <b>টাইমফ্রেম:</b> {tf}
⚡ <b>সিগনালের মেয়াদ:</b> {valid}

📈 <b>এআই কনফিডেন্স: {confidence}%</b>
[{conf_bar}]

🔍 <b>বিশ্লেষণ স্কোর:</b>
  📊 টেকনিক্যাল স্কোর: {signal.get('tech_score', 0)}/100
  📰 নিউজ সেন্টিমেন্ট: {signal.get('news_score', 0)}/100
  🤖 এআই কনফার্মেশন: {signal.get('ai_score', 0):.0f}/100

⚠️ <b>ঝুঁকির মাত্রা:</b> {risk}
💼 <b>প্রতি ট্রেডে অনুমোদিত ঝুঁকি:</b> {signal.get('risk_per_trade', 2)}%

📝 <b>সিগনালের কারণ ও যুক্তি:</b>
{reason_text if reason_text else "  • টেকনিক্যাল ইন্ডিকেটর এবং ফান্ডামেন্টাল নিউজ উভয়ের শক্তিশালী সাপোর্ট রয়েছে।"}
"""

        if pattern_text:
            msg += f"\n🕯️ <b>ক্যান্ডেলস্টিক প্যাটার্ন:</b>\n{pattern_text}"

        if warn_text:
            msg += f"\n⚠️ <b>বিশেষ সতর্কতা:</b>\n{warn_text}"

        msg += f"""
━━━━━━━━━━━━━━━━━━━━━━━━━
🤖 <i>এআই গোল্ড সিগনাল সিস্টেম | {signal.get('timestamp', '')[:16]}</i>
📌 <i>সর্বদা সঠিক মানি ম্যানেজমেন্ট ও স্টপ লস ব্যবহার করুন!</i>"""

        return msg

    # ─────────────────────────────────────────────────────────
    # TP/SL Hit Alert (বাংলায়)
    # ─────────────────────────────────────────────────────────
    def format_tp_sl_alert(self, alert_type: str, signal: dict, current_price: float) -> str:
        """TP বা SL হিট হলে বাংলায় নোটিফিকেশন পাঠায়"""
        direction = signal.get("direction", "")
        entry = signal.get("entry_price", signal.get("entry", 0))

        if alert_type == "TP1":
            emoji  = "✅🎯"
            title  = "টার্গেট ১ সফলভাবে অর্জিত! (TP1 HIT)"
            profit = abs(round(current_price - entry, 2))
            advice = "💡 <b>পরামর্শ:</b> আপনার স্টপ লস (SL) এন্ট্রি প্রাইসে নিয়ে আসুন (Breakeven), যাতে এই ট্রেডে আর কোনো লসের ঝুঁকি না থাকে!"
        elif alert_type == "TP2":
            emoji  = "🎉🔥"
            title  = "টার্গেট ২ সফলভাবে অর্জিত! (TP2 HIT)"
            profit = abs(round(current_price - entry, 2))
            advice = "💡 <b>পরামর্শ:</b> চমৎকার মুনাফা হয়েছে! কিছু প্রফিট বুক করুন এবং বাকি ট্রেড ট্রেইলিং স্টপ লস দিয়ে ধরে রাখতে পারেন।"
        elif alert_type == "SL":
            emoji  = "🛑❌"
            title  = "স্টপ লস স্পর্শ করেছে (SL HIT)"
            profit = -abs(round(current_price - entry, 2))
            advice = "💡 <b>পরামর্শ:</b> নিয়ম মেনে স্টপ লস মেনে চলুন। রিভেঞ্জ ট্রেডিং করবেন না। পরবর্তী পারফেক্ট সিগনালের জন্য অপেক্ষা করুন।"
        elif alert_type == "BREAKEVEN":
            emoji  = "🛡️⚖️"
            title  = "ট্রেড ব্রেকইভেনে ক্লোজ হয়েছে (Breakeven Exit)"
            profit = 0.0
            advice = "💡 <b>তথ্য:</b> টার্গেট ১ সফলভাবে অর্জনের পর স্টপ লস এন্ট্রি প্রাইসে ছিল, তাই এই ট্রেডে কোনো ক্ষতি বা লস হয়নি। সম্পূর্ণ ক্যাপিটাল ১০০% সুরক্ষিত!"
        else:
            emoji  = "ℹ️"
            title  = "মার্কেট আপডেট"
            profit = 0
            advice = ""

        direction_icon = "🟢 BUY" if direction == "BUY" else "🔴 SELL"

        return f"""{emoji} <b>{title}</b>
━━━━━━━━━━━━━━━━━━━━━━━━━
⚡ সিগনাল ছিল: <b>{direction_icon}</b>
💰 এন্ট্রি ছিল: <code>{entry}</code>
📍 বর্তমান মার্কেট প্রাইস: <code>{current_price}</code>
{'💵 অর্জিত মুনাফা' if profit > 0 else ('⚖️ মোট ফলাফল' if profit == 0 else '📉 লসের পরিমাণ')}: <code>{abs(profit)} USD</code>

{advice}
━━━━━━━━━━━━━━━━━━━━━━━━━
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
        signals = stats.get("signals", [])[:6]
        if signals:
            msg += "📋 <b>আজকের ট্রেডগুলোর তালিকা:</b>\n"
            for s in signals:
                result_icon = "✅" if s.get("tp_hit", 0) > 0 else ("❌" if s.get("sl_hit", 0) > 0 else "⏳")
                dir_icon    = "🟢 BUY" if s.get("direction") == "BUY" else "🔴 SELL"
                res_text    = "মুনাফা অর্জিত" if s.get("tp_hit", 0) > 0 else ("স্টপ লস" if s.get("sl_hit", 0) > 0 else "চলমান")
                msg += f"  {result_icon} {dir_icon} @ <code>{s.get('entry_price')}</code> — <i>{res_text}</i>\n"

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

        msg = f"""🔍 <b>সম্পূর্ণ টেকনিক্যাল এনালাইসিস রিপোর্ট</b>
━━━━━━━━━━━━━━━━━━━━━━━━━
💰 <b>XAUUSD প্রাইস:</b> <code>${price}</code>
📈 <b>সামগ্রিক ট্রেন্ড:</b> <b>{dir_bn}</b>
🎯 <b>টেকনিক্যাল স্কোর:</b> <b>{tech.get('score', 50)}/100</b>

📊 <b>প্রধান ইন্ডিকেটরসমূহ:</b>
  • RSI (14): <code>{details.get('RSI', 'N/A')}</code>
  • MACD: <code>{details.get('MACD', 'N/A')}</code>
  • EMA 20: <code>{details.get('EMA_20', 'N/A')}</code>
  • EMA 50: <code>{details.get('EMA_50', 'N/A')}</code>
  • EMA 200 (দীর্ঘমেয়াদী): <code>{details.get('EMA_200', 'N/A')}</code>
  • ATR (দৈনিক অস্থিরতা): <code>{details.get('ATR', 'N/A')}</code>
  • স্টোকাস্টিক K: <code>{details.get('Stochastic_K', 'N/A')}</code>

🏗️ <b>গুরুত্বপূর্ণ সাপোর্ট ও রেজিস্ট্যান্স লেভেল:</b>
  🔻 সাপোর্ট জোন: <code>{sup if sup else 'N/A'}</code>
  🔺 রেজিস্ট্যান্স জোন: <code>{res if res else 'N/A'}</code>
  ⚖️ পিভট পয়েন্ট (Pivot): <code>{key_levels.get('pivot', 'N/A')}</code>

📐 <b>ফিবোনাচ্চি রিট্রেসমেন্ট লেভেল:</b>
{fib_text if fib_text else "  হিসাব করা হচ্ছে..."}
"""
        if pat_text:
            msg += f"\n🕯️ <b>ডিটেক্ট হওয়া ক্যান্ডেলস্টিক প্যাটার্ন:</b>\n{pat_text}"

        msg += "\n━━━━━━━━━━━━━━━━━━━━━━━━━\n🤖 <i>এআই গোল্ড সিগনাল সিস্টেম</i>"
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
⏰ <b>সিগনাল এনালাইসিস:</b> প্রতি ১৫ মিনিট অন্তর মাল্টি-টাইমফ্রেম

💡 <b>নিচের ছবিতে দেওয়া বাটনগুলো ব্যবহার করে যেকোনো তথ্য এক ক্লিকে পেয়ে যান!</b>
━━━━━━━━━━━━━━━━━━━━━━━━━
📌 <i>মার্কেটে সুযোগ আসলেই সাথে সাথে স্বয়ংক্রিয় সিগনাল চলে আসবে!</i>"""
        return self.send_message(msg)

    # ─────────────────────────────────────────────────────────
    # Public Send Wrappers
    # ─────────────────────────────────────────────────────────
    def send_signal(self, signal: dict, current_price: float = None) -> bool:
        if signal.get("direction") == "NEUTRAL":
            return False
        msg = self.format_signal_message(signal, current_price)
        return self.send_message(msg)

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
