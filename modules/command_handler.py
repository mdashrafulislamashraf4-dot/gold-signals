"""
============================================================
  modules/command_handler.py
  Telegram Command Handler — Clean Text & Auto-Subscriber
  Commands: /start, /status, /subscribers, /reset
  Minimal plain text responses without icon buttons / emojis.
  Auto-registers anyone who sends /start to receive broadcast signals.
============================================================
"""

import logging
import threading
import time

import requests

from config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_IDS

logger = logging.getLogger(__name__)


class CommandHandler:
    """Handles Telegram bot commands and auto-registers subscribers"""

    BASE_URL = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"

    def __init__(
        self,
        market_data,
        signal_engine,
        telegram_bot,
        risk_engine=None,
        news_analyzer=None,
        ai_analyzer=None,
        scheduler=None,
        technical=None,
        db_manager=None,
    ):
        self.md = market_data
        self.se = signal_engine
        self.bot = telegram_bot
        self.risk = risk_engine
        self.na = news_analyzer
        self.ai = ai_analyzer
        self.sch = scheduler
        self.ta = technical
        self.db = db_manager or getattr(self.se, 'db', None)

        self._offset = 0
        self._running = False
        self._poll_thread = None

    def start_polling(self):
        self._running = True
        self._poll_thread = threading.Thread(target=self._poll_loop, daemon=True)
        self._poll_thread.start()
        logger.info("Telegram command polling started")

    def stop_polling(self):
        self._running = False

    def _poll_loop(self):
        while self._running:
            try:
                updates = self._get_updates()
                for update in updates:
                    self._process_update(update)
            except Exception as e:
                logger.error(f"Poll error: {e}")
            time.sleep(1.5)

    def _get_updates(self) -> list:
        try:
            resp = requests.get(
                f"{self.BASE_URL}/getUpdates",
                params={"offset": self._offset, "timeout": 25},
                timeout=30,
            )
            if resp.ok:
                data = resp.json()
                updates = data.get("result", [])
                if updates:
                    self._offset = updates[-1]["update_id"] + 1
                return updates
        except Exception as e:
            logger.error(f"getUpdates error: {e}")
        return []

    def _process_update(self, update: dict):
        message = update.get("message", {})
        if not message:
            return
        chat_id = str(message.get("chat", {}).get("id", ""))
        text = message.get("text", "").strip()
        if not text:
            return

        sender = message.get("from", {})
        username = sender.get("username", "")
        first_name = sender.get("first_name", "")

        logger.info(f"Command received from {chat_id} ({username}): {text}")

        # 1. /start: Auto-registers ANY user or group into subscribers list
        if text.startswith("/start"):
            if self.db:
                self.db.register_subscriber(chat_id, username, first_name)
            self._cmd_start(chat_id)
            return

        # 2. /status: Open to all users to check market and bot health
        if text.startswith("/status"):
            self._cmd_status(chat_id)
            return

        # 3. /subscribers: Check total active users/channels
        if text.startswith("/subscribers"):
            cnt = self.db.get_subscriber_count() if self.db else len(TELEGRAM_CHAT_IDS)
            self._reply(chat_id, f"Subscribers: {cnt} active")
            return

        # 4. /reset: Protected admin command only
        if text.startswith("/reset"):
            if TELEGRAM_CHAT_IDS and chat_id not in TELEGRAM_CHAT_IDS:
                self._reply(chat_id, "Unauthorized. Only configured admin can execute /reset.")
                return
            self._cmd_reset(chat_id)
            return

        logger.debug(f"Unrecognized command: {text}")

    def _reply(self, chat_id: str, text: str):
        """Send a clean plain text reply without icon buttons and remove any keyboards"""
        try:
            url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
            resp = requests.post(url, json={
                "chat_id": chat_id,
                "text": text,
                "disable_web_page_preview": True,
                "reply_markup": {"remove_keyboard": True},
            }, timeout=15)
            if not resp.ok:
                logger.error(f"Reply failed: {resp.text}")
        except Exception as e:
            logger.error(f"Reply error: {e}")

    # ─────────────────────────────────────────────────────────
    # /start
    # ─────────────────────────────────────────────────────────
    def _cmd_start(self, chat_id: str):
        try:
            price = self.md.get_current_price() or 0.0
            text = (
                f"Gold QuickScalp AI\n"
                f"Subscribed to XAUUSD Signals.\n"
                f"Gold: ${price:.2f}\n"
                f"Commands: /status"
            )
            self._reply(chat_id, text)
            logger.info(f"/start responded to {chat_id}")
        except Exception as e:
            self._reply(chat_id, "Error fetching status.")
            logger.error(f"/start error: {e}")

    # ─────────────────────────────────────────────────────────
    # /status
    # ─────────────────────────────────────────────────────────
    def _cmd_status(self, chat_id: str):
        try:
            price = self.md.get_current_price() or 0.0
            stats = self.se.get_daily_stats()
            active = self.se.get_active_signals()
            risk_state = {}
            if self.risk:
                risk_state = self.risk.db.get_or_create_daily_risk_state()

            active_line = "None"
            if active:
                sig = active[0]
                tid = sig.get("trade_id", sig.get("id", 0))
                active_line = f"#{tid:03d} {sig.get('direction')} @ {sig.get('entry_price', 0):.2f}"

            consec = risk_state.get("consecutive_losses", 0)
            daily_loss = risk_state.get("daily_loss_usd", 0.0)
            sub_count = self.db.get_subscriber_count() if self.db else 1

            text = (
                f"Status\n"
                f"Gold: ${price:.2f}\n"
                f"Active: {active_line}\n"
                f"Today: {stats['wins']}W {stats['losses']}L PnL: ${stats['pnl_usd']:.2f}\n"
                f"Subscribers: {sub_count}\n"
                f"Daily loss: ${daily_loss:.2f}"
            )
            self._reply(chat_id, text)
            logger.info(f"/status responded to {chat_id}")
        except Exception as e:
            self._reply(chat_id, "Error fetching status.")
            logger.error(f"/status error: {e}")

    # ─────────────────────────────────────────────────────────
    # /reset
    # ─────────────────────────────────────────────────────────
    def _cmd_reset(self, chat_id: str):
        try:
            if self.risk:
                self.risk.reset_consecutive_loss_halt()
                self._reply(chat_id, "Trading halt cleared. System resumed.")
                logger.info(f"/reset executed by {chat_id} — consecutive loss halt cleared")
            else:
                self._reply(chat_id, "Risk engine not available.")
        except Exception as e:
            self._reply(chat_id, "Reset failed.")
            logger.error(f"/reset error: {e}")
