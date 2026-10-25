"""
============================================================
  modules/signal_engine.py
  Signal Orchestration & Institutional Execution Gatekeeper
  Connects Setup Engines, Risk Guardian, Trade Manager & Telegram Bot
============================================================
"""

import logging
import uuid
from datetime import datetime
from typing import Dict, Any, Optional, List
import pytz

from config import (
    TIMEZONE,
    OPERATING_MODE,
    MAX_SIMULTANEOUS_POSITIONS,
)
from modules.database import DatabaseManager
from modules.risk_engine import RiskEngine
from modules.setup_engines import SetupEngines
from modules.trade_manager import TradeManager
from modules.telegram_bot import TelegramBot

logger = logging.getLogger(__name__)


class SignalEngine:
    """
    Coordinates setup discovery across the 3 independent engines, passes candidates
    through the Risk Guardian, assigns sequential trade IDs, and directs trade management.
    """

    def __init__(
        self,
        db_manager: Optional[DatabaseManager] = None,
        risk_engine: Optional[RiskEngine] = None,
        setup_engines: Optional[SetupEngines] = None,
        telegram_bot: Optional[TelegramBot] = None,
        trade_manager: Optional[TradeManager] = None,
    ):
        self.db = db_manager or DatabaseManager()
        self.risk = risk_engine or RiskEngine(self.db)
        self.engines = setup_engines or SetupEngines()
        self.telegram = telegram_bot
        self.trade_manager = trade_manager or TradeManager(self.db, self.risk)

    def generate_and_dispatch(
        self,
        df_15m: Any,
        df_5m: Any,
        df_1m: Optional[Any],
        current_price: float,
        current_spread: float,
        news_risk: bool = False,
        news_event_name: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Evaluates the 3 setup engines, applies hard risk gates, assigns sequential trade ID,
        records the signal in SQLite, and dispatches minimal Telegram alert.
        """
        # 1. Enforce single open simulated trade rule
        active_trades = self.db.get_active_signals()
        if len(active_trades) >= MAX_SIMULTANEOUS_POSITIONS:
            logger.debug(f"Position active (#{active_trades[0].get('trade_id')}). New setups skipped until trade closes.")
            return None

        # 2. Evaluate all 3 setup engines
        setup = self.engines.evaluate_all_setups(
            df_15m=df_15m,
            df_5m=df_5m,
            df_1m=df_1m,
            current_price=current_price,
            current_spread=current_spread,
        )

        if not setup.get("valid") or setup.get("direction") not in ("BUY", "SELL"):
            logger.debug(f"No trade setup triggered: {setup.get('reason')}")
            return None

        direction = setup["direction"]
        entry     = setup["entry"]
        sl        = setup["sl"]
        tp1       = setup["tp1"]
        tp2       = setup["tp2"]
        risk_dist = abs(entry - sl)

        # 3. Risk Guardian Approval Gate
        latest_candle_time = df_5m.index[-1] if hasattr(df_5m, "index") and len(df_5m) > 0 else None
        atr_val = getattr(setup, "atr", 2.50)

        risk_approval = self.risk.evaluate_trade_approval(
            current_spread=current_spread,
            current_atr=atr_val,
            avg_atr=atr_val,
            latest_candle_time=latest_candle_time,
            is_news_blackout=news_risk,
            news_event_name=news_event_name,
        )

        if not risk_approval["approved"]:
            logger.info(f"Setup rejected by Risk Guardian: {risk_approval['reason']} - {risk_approval['details']}")
            return None

        # 4. Position Sizing
        paper_acc = self.db.get_paper_account()
        equity = paper_acc.get("equity", 10000.0)
        sizing = self.risk.calculate_position_size(equity, risk_dist)

        if not sizing["valid"]:
            logger.info(f"Setup rejected by Position Sizer: {sizing['reason']}")
            return None

        # 5. Acquire Atomic Sequential Trade ID
        trade_id = self.db.get_next_trade_id()
        now_iso = datetime.now(pytz.timezone(TIMEZONE)).isoformat()

        signal_payload = {
            "trade_id": trade_id,
            "signal_uuid": f"XAU-{trade_id:04d}-{str(uuid.uuid4())[:6].upper()}",
            "timestamp": now_iso,
            "mode": OPERATING_MODE,
            "direction": direction,
            "entry": entry,
            "tp1": tp1,
            "tp2": tp2,
            "sl": sl,
            "risk_pct": sizing["risk_pct"],
            "suggested_lot": sizing["lot"],
            "spread": current_spread,
            "setup_engine": setup.get("engine_name", "Unknown"),
            "target_basis": setup.get("target_basis", ""),
            "sl_reason": setup.get("sl_reason", ""),
            "reasoning": setup.get("reasoning", ""),
        }

        # 6. Save in SQLite
        db_sig_id = self.db.save_signal(signal_payload)
        signal_payload["id"] = db_sig_id

        logger.info(
            f"⚡ NEW SIGNAL #{trade_id:03d} [{signal_payload['setup_engine']}]: "
            f"{direction} @ {entry} | TP1: {tp1} | TP2: {tp2} | SL: {sl} | Lot: {sizing['lot']}"
        )

        # 7. Dispatch Minimal Telegram Message
        if self.telegram and OPERATING_MODE in ("PAPER", "TELEGRAM_SIGNAL", "LIVE"):
            self.telegram.send_signal(signal_payload)

        return signal_payload

    def monitor_active_trades(
        self,
        current_price: float,
        current_spread: float,
        df_1m: Optional[Any] = None,
    ) -> List[Dict[str, Any]]:
        """
        Monitors active trades for TP1, TP2, and SL events.
        Dispatches minimal Telegram trade result messages when hit.
        """
        events = self.trade_manager.process_open_trades(
            current_price=current_price,
            current_spread=current_spread,
            df_1m=df_1m,
        )

        for ev in events:
            ev_type  = ev["event"]
            trade_id = ev["trade_id"]

            if ev_type in ("TP_HIT", "TP1_HIT"):
                logger.info(f"✅ Trade #{trade_id:03d} reached TP at {ev.get('exit_price')}. Trade closed with profit.")
                if self.telegram:
                    self.telegram.send_tp_hit(trade_id)

            elif ev_type == "TP2_HIT":
                logger.info(f"🏆 Trade #{trade_id:03d} reached TP2 at {ev.get('exit_price')}. Trade closed.")
                if self.telegram:
                    self.telegram.send_tp2_hit(trade_id)

            elif ev_type == "SL_HIT":
                logger.info(f"❌ Trade #{trade_id:03d} hit Stop Loss at {ev.get('exit_price')}. Trade closed.")
                if self.telegram:
                    self.telegram.send_sl_hit(trade_id)

        return events

    def cleanup_ghost_signals(self):
        """Cleans orphaned active signals on startup"""
        self.db.cleanup_ghost_signals()

    def get_active_signals(self) -> List[Dict[str, Any]]:
        """Returns all currently active and pending signals"""
        return self.db.get_active_signals()

    def save_signal(self, signal: Dict[str, Any]) -> int:
        """Saves a signal to the database"""
        return self.db.save_signal(signal)

    def get_daily_stats(self) -> Dict[str, Any]:
        """Returns daily trading statistics"""
        return self.db.get_daily_stats()
