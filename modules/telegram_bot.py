"""
============================================================
  modules/telegram_bot.py
  Telegram Bot — Minimal Message Specification Only
  Strict Format:
    BUY:       🟢 BUY #001 Entry: {entry} TP1: {tp1} TP2: {tp2} SL: {sl}
    SELL:      🔴 SELL #002 Entry: {entry} TP1: {tp1} TP2: {tp2} SL: {sl}
    TP1:       ✅ #001 TP1 HIT
    TP2:       🏆 #001 TP2 HIT
    Stop loss: ❌ #001 SL HIT
  NO analysis, NO promotional text, NO daily summaries, NO warnings.
============================================================
"""

import logging
from typing import Dict, Any, List, Optional
import requests

logger = logging.getLogger(__name__)


class TelegramBot:
    """Telegram Bot wrapper strictly sending minimal signals and trade result messages"""

    BASE_URL = "https://api.telegram.org/bot{token}/{method}"

    def __init__(self, token: str, chat_ids: list):
        self.token = token
        self.chat_ids = chat_ids if isinstance(chat_ids, list) else [chat_ids]

    def _send_raw_text(self, text: str) -> bool:
        """Sends raw plain text message to all configured chat IDs"""
        if not self.token or not self.chat_ids:
            logger.warning("Telegram token or chat IDs missing. Message not sent.")
            return False

        success = True
        for cid in self.chat_ids:
            try:
                url = self.BASE_URL.format(token=self.token, method="sendMessage")
                payload = {
                    "chat_id": cid,
                    "text": text,
                    "disable_web_page_preview": True,
                }
                resp = requests.post(url, json=payload, timeout=15)
                if not resp.ok:
                    logger.error(f"Telegram send failed for chat {cid}: {resp.status_code} - {resp.text}")
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
        Sends minimal format:
        Single TP:
          🟢 BUY #001 Entry: 2685.50 TP: 2690.00 SL: 2681.00
          🔴 SELL #002 Entry: 2685.50 TP: 2681.00 SL: 2689.50
        Two-Stage TP (if configured):
          🟢 BUY #001 Entry: 2685.50 TP1: 2690.00 TP2: 2694.50 SL: 2681.00
        """
        direction = signal.get("direction", "").upper()
        if direction not in ("BUY", "SELL"):
            logger.debug(f"Signal direction '{direction}' is not actionable. Skipping Telegram send.")
            return False

        trade_id = signal.get("trade_id", 1)
        emoji = "🟢" if direction == "BUY" else "🔴"
        entry = float(signal.get("entry", signal.get("entry_price", 0.0)))
        sl    = float(signal.get("sl", 0.0))
        tp    = signal.get("tp")
        tp1   = signal.get("tp1")
        tp2   = signal.get("tp2")

        # Single TP Format
        if tp is not None or (tp1 is not None and tp2 is not None and tp1 == tp2):
            target_tp = float(tp if tp is not None else tp1)
            text = f"{emoji} {direction} #{trade_id:03d} Entry: {entry:.2f} TP: {target_tp:.2f} SL: {sl:.2f}"
        else:
            tp1_val = float(tp1 or 0.0)
            tp2_val = float(tp2 or 0.0)
            text = f"{emoji} {direction} #{trade_id:03d} Entry: {entry:.2f} TP1: {tp1_val:.2f} TP2: {tp2_val:.2f} SL: {sl:.2f}"

        return self._send_raw_text(text)

    # ─────────────────────────────────────────────────────────
    # 2. Trade Result Messages
    # ─────────────────────────────────────────────────────────
    def send_tp_hit(self, trade_id: int) -> bool:
        """✅ #001 TP HIT"""
        text = f"✅ #{trade_id:03d} TP HIT"
        return self._send_raw_text(text)

    def send_tp1_hit(self, trade_id: int) -> bool:
        """✅ #001 TP1 HIT"""
        text = f"✅ #{trade_id:03d} TP1 HIT"
        return self._send_raw_text(text)

    def send_tp2_hit(self, trade_id: int) -> bool:
        """🏆 #001 TP2 HIT"""
        text = f"🏆 #{trade_id:03d} TP2 HIT"
        return self._send_raw_text(text)

    def send_sl_hit(self, trade_id: int) -> bool:
        """❌ #001 SL HIT"""
        text = f"❌ #{trade_id:03d} SL HIT"
        return self._send_raw_text(text)

    # ─────────────────────────────────────────────────────────
    # 3. Startup & Health Checks
    # ─────────────────────────────────────────────────────────
    def send_startup_message(self) -> bool:
        """Pings Telegram to verify API credentials and connectivity"""
        return self._send_raw_text("🟢 Gold QuickScalp AI initialized.")

    def send_shutdown_message(self) -> bool:
        """Pings Telegram on shutdown"""
        return self._send_raw_text("🛑 Gold QuickScalp AI stopped.")
