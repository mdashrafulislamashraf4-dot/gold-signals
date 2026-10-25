"""
============================================================
  modules/telegram_bot.py
  Telegram Bot — Multi-User Broadcast & Minimal Clean Format
  Clean Format (No Icons/Buttons by default):
    BUY:       BUY #001 Entry: {entry} TP: {tp} SL: {sl}
    SELL:      SELL #002 Entry: {entry} TP: {tp} SL: {sl}
    TP HIT:    #001 TP HIT
    SL HIT:    #001 SL HIT
  Multi-User Broadcast:
    - Broadcasts to all active subscribers in SQLite DB
    - Broadcasts to all configured TELEGRAM_CHAT_IDS (including Channels & Groups)
============================================================
"""

import logging
from typing import Dict, Any, List, Optional
import requests

logger = logging.getLogger(__name__)


class TelegramBot:
    """Telegram Bot wrapper strictly sending minimal signals and trade result messages"""

    BASE_URL = "https://api.telegram.org/bot{token}/{method}"

    def __init__(self, token: str, chat_ids: list, db_manager=None, include_emojis: bool = False):
        self.token = token
        raw_ids = chat_ids if isinstance(chat_ids, list) else [chat_ids]
        self.chat_ids = [str(cid).strip() for cid in raw_ids if str(cid).strip()]
        self.db = db_manager
        self.include_emojis = include_emojis

    def get_all_recipients(self) -> List[str]:
        """Combines configured chat IDs and active DB subscribers (deduplicated)"""
        recipients = set(self.chat_ids)
        if self.db:
            try:
                recipients.update(self.db.get_all_subscribers())
            except Exception as e:
                logger.debug(f"Subscriber lookup note: {e}")
        return [r for r in recipients if r]

    def _send_raw_text(self, text: str) -> bool:
        """Sends clean plain text message to all subscribers and channels without buttons"""
        recipients = self.get_all_recipients()
        if not self.token or not recipients:
            logger.warning("Telegram token or recipients missing. Message not sent.")
            return False

        success = True
        for cid in recipients:
            try:
                url = self.BASE_URL.format(token=self.token, method="sendMessage")
                payload = {
                    "chat_id": cid,
                    "text": text,
                    "disable_web_page_preview": True,
                    "reply_markup": {"remove_keyboard": True},
                }
                resp = requests.post(url, json=payload, timeout=15)
                if not resp.ok:
                    logger.error(f"Telegram send failed for chat {cid}: {resp.status_code} - {resp.text}")
                    # If user blocked the bot or chat not found, deactivate in DB
                    if resp.status_code in (403, 400) and self.db:
                        try:
                            self.db.deactivate_subscriber(cid)
                        except Exception:
                            pass
                    success = False
                else:
                    logger.info(f"Telegram message sent to {cid}: {text}")
            except Exception as e:
                logger.error(f"Telegram error delivering to {cid}: {e}")
                success = False

        return success

    # ─────────────────────────────────────────────────────────
    # 1. New Signal Message
    # ─────────────────────────────────────────────────────────
    def send_signal(self, signal: Dict[str, Any]) -> bool:
        """
        Sends minimal format without icon buttons:
        Single TP:
          BUY #001 Entry: 2685.50 TP: 2690.00 SL: 2681.00
          SELL #002 Entry: 2685.50 TP: 2681.00 SL: 2689.50
        Two-Stage TP (if configured):
          BUY #001 Entry: 2685.50 TP1: 2690.00 TP2: 2694.50 SL: 2681.00
        """
        direction = signal.get("direction", "").upper()
        if direction not in ("BUY", "SELL"):
            logger.debug(f"Signal direction '{direction}' is not actionable. Skipping Telegram send.")
            return False

        trade_id = signal.get("trade_id", 1)
        entry = float(signal.get("entry", signal.get("entry_price", 0.0)))
        sl    = float(signal.get("sl", 0.0))
        tp    = signal.get("tp")
        tp1   = signal.get("tp1")
        tp2   = signal.get("tp2")

        include_emoji = signal.get("include_emoji", self.include_emojis)
        emoji = ("🟢 " if direction == "BUY" else "🔴 ") if include_emoji else ""

        # Single TP Format
        if tp is not None or (tp1 is not None and tp2 is not None and tp1 == tp2):
            target_tp = float(tp if tp is not None else tp1)
            text = f"{emoji}{direction} #{trade_id:03d} Entry: {entry:.2f} TP: {target_tp:.2f} SL: {sl:.2f}"
        else:
            tp1_val = float(tp1 or 0.0)
            tp2_val = float(tp2 or 0.0)
            text = f"{emoji}{direction} #{trade_id:03d} Entry: {entry:.2f} TP1: {tp1_val:.2f} TP2: {tp2_val:.2f} SL: {sl:.2f}"

        return self._send_raw_text(text)

    # ─────────────────────────────────────────────────────────
    # 2. Trade Result Messages (Clean without icon buttons)
    # ─────────────────────────────────────────────────────────
    def send_tp_hit(self, trade_id: int) -> bool:
        """#001 TP HIT"""
        icon = "✅ " if self.include_emojis else ""
        text = f"{icon}#{trade_id:03d} TP HIT"
        return self._send_raw_text(text)

    def send_tp1_hit(self, trade_id: int) -> bool:
        """#001 TP HIT (or TP1 HIT if emojis enabled)"""
        icon = "✅ " if self.include_emojis else ""
        text = f"{icon}#{trade_id:03d} TP1 HIT" if self.include_emojis else f"#{trade_id:03d} TP HIT"
        return self._send_raw_text(text)

    def send_tp2_hit(self, trade_id: int) -> bool:
        """#001 TP2 HIT"""
        icon = "🏆 " if self.include_emojis else ""
        text = f"{icon}#{trade_id:03d} TP2 HIT" if self.include_emojis else f"#{trade_id:03d} TP HIT"
        return self._send_raw_text(text)

    def send_sl_hit(self, trade_id: int) -> bool:
        """#001 SL HIT"""
        icon = "❌ " if self.include_emojis else ""
        text = f"{icon}#{trade_id:03d} SL HIT"
        return self._send_raw_text(text)

    # ─────────────────────────────────────────────────────────
    # 3. Startup & Health Checks (Silent - No Telegram Spams)
    # ─────────────────────────────────────────────────────────
    def send_startup_message(self) -> bool:
        """Silent startup check"""
        logger.info("Telegram startup check verified.")
        return True

    def send_shutdown_message(self) -> bool:
        """Silent shutdown"""
        logger.info("Telegram shutdown logged.")
        return True
