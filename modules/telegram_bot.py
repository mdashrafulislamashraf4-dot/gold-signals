"""
============================================================
  modules/telegram_bot.py
  Telegram Bot — সব ধরনের মেসেজ ফরম্যাট ও পাঠানো
============================================================
"""

import logging
from datetime import datetime
from typing import Optional, Union

import requests

logger = logging.getLogger(__name__)


class TelegramBot:
    """Telegram Bot API wrapper"""

    BASE_URL = "https://api.telegram.org/bot{token}/{method}"

    def __init__(self, token: str, chat_ids: list):
        self.token    = token
        self.chat_ids = chat_ids if isinstance(chat_ids, list) else [chat_ids]

    # ─────────────────────────────────────────────────────────
    # Core Send Methods
    # ─────────────────────────────────────────────────────────
    def send_message(self, text: str, chat_id: str = None, parse_mode: str = "HTML",
                     disable_preview: bool = True) -> bool:
        """টেলিগ্রামে মেসেজ পাঠায়"""
        targets = [chat_id] if chat_id else self.chat_ids
        success = True

        for cid in targets:
            try:
                url = self.BASE_URL.format(token=self.token, method="sendMessage")
                payload = {
                    "chat_id":                  cid,
                    "text":                     text,
                    "parse_mode":               parse_mode,
                    "disable_web_page_preview": disable_preview,
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
                        data={"chat_id": cid, "caption": caption, "parse_mode": "HTML"},
                        files={"photo": f},
                        timeout=30,
                    )
                if not resp.ok:
                    logger.error(f"Photo send failed: {resp.text}")
            except Exception as e:
                logger.error(f"Photo send error: {e}")
        return True

    # ─────────────────────────────────────────────────────────
    # Signal Alert Format
    # ─────────────────────────────────────────────────────────
    def format_signal_message(self, signal: dict, current_price: float = None) -> str:
        """ট্রেডিং সিগনাল ফরম্যাট করে"""
        direction = signal.get("direction", "NEUTRAL")
        confidence = signal.get("confidence", 0)

        if direction == "BUY":
            action_emoji = "🟢 BUY 📈"
            arrow = "⬆️"
        elif direction == "SELL":
            action_emoji = "🔴 SELL 📉"
            arrow = "⬇️"
        else:
            action_emoji = "⚪ NEUTRAL ↔️"
            arrow = "↔️"

        entry = signal.get("entry", 0)
        tp1   = signal.get("tp1", 0)
        tp2   = signal.get("tp2", 0)
        tp3   = signal.get("tp3", 0)
        sl    = signal.get("sl", 0)
        rr    = signal.get("rr_ratio", "1:2")
        tf    = signal.get("timeframe", "H1")
        risk  = signal.get("risk_level", "MEDIUM")
        valid = signal.get("validity", "4-8 hours")

        # Confidence bar
        conf_bar = "█" * (confidence // 10) + "░" * (10 - confidence // 10)

        # Reasoning
        reasoning = signal.get("reasoning", [])
        reason_text = ""
        for i, r in enumerate(reasoning[:4], 1):
            reason_text += f"  {i}. {r}\n"

        # Warnings
        warnings = signal.get("warnings", [])
        warn_text = ""
        for w in warnings[:2]:
            warn_text += f"  ⚠️ {w}\n"

        # Patterns
        patterns = signal.get("patterns", [])
        pattern_text = ""
        for p in patterns[:2]:
            pattern_text += f"  🕯️ {p[2]}\n"

        msg = f"""🏆 <b>XAUUSD GOLD SIGNAL</b> 🏆
━━━━━━━━━━━━━━━━━━━━━━━━━

{arrow} <b>Action: {action_emoji}</b>
💰 <b>Entry:</b> <code>{entry}</code>
🎯 <b>TP1:</b> <code>{tp1}</code> (+{abs(round(tp1-entry,1))} pips)
🎯 <b>TP2:</b> <code>{tp2}</code> (+{abs(round(tp2-entry,1))} pips)
🎯 <b>TP3:</b> <code>{tp3}</code> (+{abs(round(tp3-entry,1))} pips)
🛑 <b>SL:</b> <code>{sl}</code> (-{abs(round(sl-entry,1))} pips)
📊 <b>R:R Ratio:</b> {rr}
⏱️ <b>Timeframe:</b> {tf}
⚡ <b>Valid for:</b> {valid}

📈 <b>Confidence: {confidence}%</b>
[{conf_bar}]

🔍 <b>Analysis Score:</b>
  📊 Technical: {signal.get('tech_score', 0)}/100
  📰 News: {signal.get('news_score', 0)}/100
  🤖 AI Score: {signal.get('ai_score', 0):.0f}/100

⚠️ <b>Risk Level:</b> {risk}
💼 <b>Risk per trade:</b> {signal.get('risk_per_trade', 2)}%

📝 <b>Reasoning:</b>
{reason_text if reason_text else "  • Technical & fundamental alignment"}
"""

        if pattern_text:
            msg += f"\n🕯️ <b>Patterns:</b>\n{pattern_text}"

        if warn_text:
            msg += f"\n⚠️ <b>Warnings:</b>\n{warn_text}"

        msg += f"""
━━━━━━━━━━━━━━━━━━━━━━━━━
🤖 <i>AI Gold Signal System | {signal.get('timestamp', '')[:16]}</i>
📌 <i>Always use proper risk management!</i>"""

        return msg

    # ─────────────────────────────────────────────────────────
    # TP/SL Hit Alert
    # ─────────────────────────────────────────────────────────
    def format_tp_sl_alert(self, alert_type: str, signal: dict, current_price: float) -> str:
        """TP বা SL হিট হলে নোটিফিকেশন পাঠায়"""
        direction = signal.get("direction", "")
        entry = signal.get("entry_price", signal.get("entry", 0))

        if alert_type == "TP1":
            emoji  = "✅"
            title  = "TARGET 1 HIT! 🎯"
            profit = abs(round(current_price - entry, 2))
            msg    = f"TP1 reached! Consider moving SL to breakeven."
        elif alert_type == "TP2":
            emoji  = "🎉"
            title  = "TARGET 2 HIT! 🎯🎯"
            profit = abs(round(current_price - entry, 2))
            msg    = f"Excellent! TP2 reached! Take profits!"
        elif alert_type == "SL":
            emoji  = "❌"
            title  = "STOP LOSS HIT 🛑"
            profit = -abs(round(current_price - entry, 2))
            msg    = f"SL triggered. Wait for next signal."
        else:
            emoji  = "ℹ️"
            title  = "SIGNAL UPDATE"
            profit = 0
            msg    = ""

        direction_icon = "📈" if direction == "BUY" else "📉"

        return f"""{emoji} <b>{title}</b>
━━━━━━━━━━━━━━━━━━━━━━━━━
{direction_icon} Signal: <b>{direction}</b>
💰 Entry was: <code>{entry}</code>
📍 Current Price: <code>{current_price}</code>
{'✅ Profit' if profit >= 0 else '❌ Loss'}: <code>{abs(profit)} USD</code>

{msg}
━━━━━━━━━━━━━━━━━━━━━━━━━
🤖 <i>AI Gold Signal System</i>"""

    # ─────────────────────────────────────────────────────────
    # News Alert
    # ─────────────────────────────────────────────────────────
    def format_news_alert(self, news: dict, impact_analysis: str = "") -> str:
        """গুরুত্বপূর্ণ নিউজ অ্যালার্ট ফরম্যাট করে"""
        impact  = news.get("impact", "MEDIUM")
        title   = news.get("title", "")
        source  = news.get("source", "")
        link    = news.get("link", "")

        if impact == "HIGH":
            emoji = "🚨🚨"
        elif impact == "MEDIUM":
            emoji = "⚠️"
        else:
            emoji = "📰"

        msg = f"""{emoji} <b>GOLD MARKET NEWS ALERT</b> {emoji}
━━━━━━━━━━━━━━━━━━━━━━━━━
📌 <b>{title[:200]}</b>

📎 Source: <i>{source}</i>
⚡ Impact: <b>{impact}</b>
"""
        if impact_analysis:
            msg += f"\n🤖 <b>AI Analysis:</b>\n<i>{impact_analysis[:400]}</i>\n"

        if link:
            msg += f'\n🔗 <a href="{link}">Read Full Article</a>'

        msg += f"""
━━━━━━━━━━━━━━━━━━━━━━━━━
🤖 <i>AI Gold Signal System | Monitor your positions!</i>"""

        return msg

    # ─────────────────────────────────────────────────────────
    # Daily Report
    # ─────────────────────────────────────────────────────────
    def format_daily_report(self, stats: dict, date: str = None) -> str:
        """দৈনিক পারফরম্যান্স রিপোর্ট ফরম্যাট করে"""
        date    = date or stats.get("date", "Today")
        total   = stats.get("total", 0)
        tp_hits = stats.get("tp_hits", 0)
        sl_hits = stats.get("sl_hits", 0)
        pending = stats.get("pending", 0)
        win_rate = stats.get("win_rate", 0)

        if win_rate >= 70:
            performance_emoji = "🔥 Excellent"
        elif win_rate >= 55:
            performance_emoji = "✅ Good"
        elif win_rate >= 40:
            performance_emoji = "⚠️ Average"
        else:
            performance_emoji = "❌ Poor"

        # Win rate bar
        bar_len = int(win_rate / 10)
        rate_bar = "█" * bar_len + "░" * (10 - bar_len)

        msg = f"""📊 <b>DAILY PERFORMANCE REPORT</b>
🗓️ Date: <b>{date}</b>
━━━━━━━━━━━━━━━━━━━━━━━━━

📈 <b>Signal Summary</b>
  📌 Total Signals: <b>{total}</b>
  ✅ TP Hit: <b>{tp_hits}</b>
  ❌ SL Hit: <b>{sl_hits}</b>
  ⏳ Pending: <b>{pending}</b>

🎯 <b>Win Rate: {win_rate}%</b>
[{rate_bar}]
Performance: {performance_emoji}

"""
        # Add signal details
        signals = stats.get("signals", [])[:5]
        if signals:
            msg += "📋 <b>Today's Signals:</b>\n"
            for s in signals:
                result_icon = "✅" if s.get("tp_hit", 0) > 0 else ("❌" if s.get("sl_hit", 0) > 0 else "⏳")
                dir_icon    = "📈" if s.get("direction") == "BUY" else "📉"
                msg += f"  {result_icon} {dir_icon} {s.get('direction')} @ {s.get('entry_price')} — {s.get('result', 'PENDING')}\n"

        msg += f"""
━━━━━━━━━━━━━━━━━━━━━━━━━
🤖 <i>AI Gold Signal System | Daily Report</i>
💡 <i>Keep practicing risk management for consistent profits!</i>"""

        return msg

    # ─────────────────────────────────────────────────────────
    # Weekly Report
    # ─────────────────────────────────────────────────────────
    def format_weekly_report(self, stats: dict, ai_summary: str = "") -> str:
        """সাপ্তাহিক পারফরম্যান্স রিপোর্ট ফরম্যাট করে"""
        total    = stats.get("total", 0)
        tp_hits  = stats.get("tp_hits", 0)
        sl_hits  = stats.get("sl_hits", 0)
        win_rate = stats.get("win_rate", 0)
        buys     = stats.get("buys", 0)
        sells    = stats.get("sells", 0)
        from_date = stats.get("from_date", "This week")

        if win_rate >= 70:
            grade = "A+ 🏆"
        elif win_rate >= 60:
            grade = "A 🥇"
        elif win_rate >= 50:
            grade = "B 🥈"
        elif win_rate >= 40:
            grade = "C 🥉"
        else:
            grade = "D ⚠️"

        msg = f"""🗓️ <b>WEEKLY PERFORMANCE REPORT</b>
📅 Week: <b>{from_date}</b>
━━━━━━━━━━━━━━━━━━━━━━━━━

📊 <b>Signal Statistics</b>
  📌 Total Signals: <b>{total}</b>
  📈 BUY Signals: <b>{buys}</b>
  📉 SELL Signals: <b>{sells}</b>
  ✅ TP Hit: <b>{tp_hits}</b>
  ❌ SL Hit: <b>{sl_hits}</b>

🎯 <b>Win Rate: {win_rate}%</b>
📝 <b>Grade: {grade}</b>

"""
        if ai_summary:
            msg += f"🤖 <b>AI Analysis:</b>\n<i>{ai_summary[:500]}</i>\n\n"

        msg += f"""━━━━━━━━━━━━━━━━━━━━━━━━━
🤖 <i>AI Gold Signal System | Weekly Report</i>
📅 <i>Next week: Keep disciplined and follow the system!</i>"""

        return msg

    # ─────────────────────────────────────────────────────────
    # Price Update
    # ─────────────────────────────────────────────────────────
    def format_price_update(self, price: float, correlated: dict) -> str:
        """বর্তমান গোল্ড প্রাইস আপডেট ফরম্যাট করে"""
        corr_text = ""
        for name, val in correlated.items():
            chg = val.get("change_pct", 0)
            arrow = "▲" if chg >= 0 else "▼"
            emoji = "📈" if chg >= 0 else "📉"
            corr_text += f"  {emoji} {name}: {val.get('price', 'N/A')} ({arrow}{abs(chg)}%)\n"

        return f"""💰 <b>GOLD PRICE UPDATE</b>
━━━━━━━━━━━━━━━━━━━━━━━━━
🥇 <b>XAUUSD: <code>{price}</code> USD/oz</b>

📊 <b>Correlated Markets:</b>
{corr_text if corr_text else "  Data loading..."}
━━━━━━━━━━━━━━━━━━━━━━━━━
🤖 <i>AI Gold Signal System</i>"""

    # ─────────────────────────────────────────────────────────
    # Send Signal
    # ─────────────────────────────────────────────────────────
    def send_signal(self, signal: dict, current_price: float = None) -> bool:
        """ট্রেডিং সিগনাল টেলিগ্রামে পাঠায়"""
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

    def send_daily_report(self, stats: dict) -> bool:
        msg = self.format_daily_report(stats)
        return self.send_message(msg)

    def send_weekly_report(self, stats: dict, ai_summary: str = "") -> bool:
        msg = self.format_weekly_report(stats, ai_summary)
        return self.send_message(msg)

    def send_startup_message(self) -> bool:
        msg = """🚀 <b>AI GOLD SIGNAL SYSTEM STARTED</b>
━━━━━━━━━━━━━━━━━━━━━━━━━
✅ System is now ACTIVE
📊 Monitoring: XAUUSD (Gold)
🤖 AI Engine: Gemini AI
📰 News Monitor: Active
⏰ Signal Check: Every 15 min

<b>Available Commands:</b>
/signal — Latest signal
/price — Current gold price
/news — Latest news
/analysis — Full analysis
/calendar — Economic events
/report — Today's report
/status — System status
/help — All commands

━━━━━━━━━━━━━━━━━━━━━━━━━
💡 <i>System will send signals 24/7 when opportunities arise!</i>"""
        return self.send_message(msg)

    # ─────────────────────────────────────────────────────────
    # Economic Calendar Alert
    # ─────────────────────────────────────────────────────────
    def format_economic_calendar(self, events: list) -> str:
        """ইকোনমিক ক্যালেন্ডার ফরম্যাট করে"""
        if not events:
            return "📅 No major economic events found for today."

        msg = """📅 <b>ECONOMIC CALENDAR</b>
━━━━━━━━━━━━━━━━━━━━━━━━━
<i>Events that may affect Gold price:</i>

"""
        for ev in events[:10]:
            impact = ev.get("impact", "MEDIUM")
            emoji  = "🔴" if impact == "HIGH" else ("🟡" if impact == "MEDIUM" else "🟢")
            msg += f"{emoji} <b>{ev.get('event', '')[:80]}</b>\n"
            if ev.get("time"):
                msg += f"   ⏰ {str(ev.get('time', ''))[:50]}\n"
            msg += "\n"

        msg += "━━━━━━━━━━━━━━━━━━━━━━━━━\n🔴 High Impact | 🟡 Medium | 🟢 Low"
        return msg
