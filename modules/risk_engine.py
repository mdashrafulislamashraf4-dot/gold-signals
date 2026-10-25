"""
============================================================
  modules/risk_engine.py
  Risk Guardian & Position Sizing Engine for Gold QuickScalp AI
  Strict Commander A Specification:
    - Default risk: 0.25% per trade (Max 0.50%)
    - 1 open simulated trade at a time
    - Initial daily drawdown stop: 1%
    - 3 consecutive losses halt (requires explicit /reset)
    - News risk warning (does not silently kill strategy)
============================================================
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, Any, Optional
import pytz

from config import (
    TIMEZONE,
    RISK_PER_TRADE,
    MAX_RISK_PER_TRADE,
    ENABLE_DAILY_LOSS_LIMIT,
    MAX_DAILY_LOSS_PCT,
    ENABLE_CONSECUTIVE_LOSS_LIMIT,
    MAX_CONSECUTIVE_LOSSES,
    MAX_SIMULTANEOUS_POSITIONS,
    COOLDOWN_MINUTES_AFTER_SL,
    MAX_SPREAD_ALLOWED,
    VOLATILITY_SPIKE_THRESHOLD_ATR_MULT,
    LOT_SIZE,
    MIN_LOT,
    LOT_STEP,
    KILL_SWITCH_ACTIVE,
)
from modules.database import DatabaseManager

logger = logging.getLogger(__name__)


class RiskEngine:
    """
    Authoritative Risk Guardian.
    Validates capital safety, enforces 1% drawdown limit, 3-loss halt,
    spread constraints, and exact broker contract sizing.
    """

    def __init__(self, db_manager: Optional[DatabaseManager] = None):
        self.db = db_manager or DatabaseManager()
        self.default_risk_pct = min(RISK_PER_TRADE, MAX_RISK_PER_TRADE)
        self.kill_switch_memory = KILL_SWITCH_ACTIVE

    # ─────────────────────────────────────────────────────────
    # Stop-Loss Calculation & Invalidation
    # ─────────────────────────────────────────────────────────
    def calculate_stop_loss(
        self,
        direction: str,
        entry_price: float,
        sweep_level: Optional[float] = None,
        last_swing_extreme: Optional[float] = None,
        ob_extreme: Optional[float] = None,
        atr: float = 2.0,
    ) -> Dict[str, Any]:
        """Calculates dynamic structural SL placed beyond invalidation extreme + ATR buffer"""
        atr_buffer = round(max(atr * 1.1, 1.50), 2)
        min_sl_distance = 1.50
        max_sl_distance = max(8.50, round(atr * 2.8, 2))

        candidates = []
        if direction == "BUY":
            if sweep_level is not None and sweep_level < entry_price:
                invalidation_level = sweep_level
            else:
                for lvl in [last_swing_extreme, ob_extreme]:
                    if lvl is not None and lvl < entry_price:
                        candidates.append(lvl)
                invalidation_level = max(candidates) if candidates else round(entry_price - (atr * 1.3), 2)

            raw_sl = round(invalidation_level - atr_buffer, 2)
            risk_dist = round(entry_price - raw_sl, 2)

            if risk_dist < min_sl_distance:
                raw_sl = round(entry_price - min_sl_distance, 2)
                risk_dist = min_sl_distance

            if risk_dist > max_sl_distance:
                return {
                    "valid": False,
                    "reason": f"Stop loss distance (${risk_dist:.2f}) exceeds maximum allowed scalping stop (${max_sl_distance:.2f}).",
                    "sl": raw_sl,
                    "risk_distance": risk_dist,
                    "invalidation_level": invalidation_level,
                }

            return {
                "valid": True,
                "reason": "Valid structural stop loss calculated.",
                "sl": raw_sl,
                "risk_distance": risk_dist,
                "invalidation_level": invalidation_level,
                "atr_buffer": atr_buffer,
            }

        elif direction == "SELL":
            if sweep_level is not None and sweep_level > entry_price:
                invalidation_level = sweep_level
            else:
                for lvl in [last_swing_extreme, ob_extreme]:
                    if lvl is not None and lvl > entry_price:
                        candidates.append(lvl)
                invalidation_level = min(candidates) if candidates else round(entry_price + (atr * 1.3), 2)

            raw_sl = round(invalidation_level + atr_buffer, 2)
            risk_dist = round(raw_sl - entry_price, 2)

            if risk_dist < min_sl_distance:
                raw_sl = round(entry_price + min_sl_distance, 2)
                risk_dist = min_sl_distance

            if risk_dist > max_sl_distance:
                return {
                    "valid": False,
                    "reason": f"Stop loss distance (${risk_dist:.2f}) exceeds maximum allowed scalping stop (${max_sl_distance:.2f}).",
                    "sl": raw_sl,
                    "risk_distance": risk_dist,
                    "invalidation_level": invalidation_level,
                }

            return {
                "valid": True,
                "reason": "Valid structural stop loss calculated.",
                "sl": raw_sl,
                "risk_distance": risk_dist,
                "invalidation_level": invalidation_level,
                "atr_buffer": atr_buffer,
            }

        return {"valid": False, "reason": "Invalid direction", "sl": entry_price, "risk_distance": 0.0}

    # ─────────────────────────────────────────────────────────
    # Position Sizing based on Broker Contract Specification
    # ─────────────────────────────────────────────────────────
    def calculate_position_size(
        self,
        account_equity: float,
        risk_distance: float,
        custom_risk_pct: Optional[float] = None,
        risk_pct: Optional[float] = None,
    ) -> Dict[str, Any]:
        """
        Calculates position size strictly respecting broker contract specifications:
        - 1 standard lot = 100 troy oz
        - $1.00 move per lot = $100.00 PnL
        - Minimum lot = 0.01 (1 oz)
        - Lot step = 0.01
        Rejects if minimum 0.01 lot risk exceeds max permitted risk ceiling (0.50%).
        """
        chosen_pct = risk_pct if risk_pct is not None else (custom_risk_pct or self.default_risk_pct)
        effective_risk_pct = min(chosen_pct, MAX_RISK_PER_TRADE)
        dollar_risk_allowed = round(account_equity * (effective_risk_pct / 100.0), 2)

        cost_per_point_per_lot = LOT_SIZE  # $100 per $1.00 move
        dollar_risk_per_lot = risk_distance * cost_per_point_per_lot

        if dollar_risk_per_lot <= 0:
            return {"valid": False, "lot": 0.0, "reason": "Invalid zero or negative risk distance"}

        raw_lot = dollar_risk_allowed / dollar_risk_per_lot
        steps = int(raw_lot / LOT_STEP)
        calculated_lot = round(steps * LOT_STEP, 2)

        min_lot_risk = round(MIN_LOT * dollar_risk_per_lot, 2)
        hard_max_dollar_risk = round(account_equity * (MAX_RISK_PER_TRADE / 100.0), 2)

        if min_lot_risk > hard_max_dollar_risk:
            return {
                "valid": False,
                "lot": 0.0,
                "reason": (
                    f"Stop distance (${risk_distance:.2f}) causes minimum lot size ({MIN_LOT}) risk "
                    f"(${min_lot_risk:.2f}) to exceed maximum permitted risk ceiling (${hard_max_dollar_risk:.2f})."
                ),
            }

        final_lot = max(calculated_lot, MIN_LOT)
        actual_dollar_risk = round(final_lot * dollar_risk_per_lot, 2)
        actual_risk_pct = round((actual_dollar_risk / account_equity) * 100.0, 3)

        return {
            "valid": True,
            "lot": final_lot,
            "dollar_risk": actual_dollar_risk,
            "risk_pct": actual_risk_pct,
            "account_equity": account_equity,
        }

    # ─────────────────────────────────────────────────────────
    # Pre-Trade Risk Filter & Guardrails
    # ─────────────────────────────────────────────────────────
    def evaluate_trade_approval(
        self,
        current_spread: float,
        current_atr: float,
        avg_atr: float,
        latest_candle_time: Optional[datetime] = None,
        is_news_blackout: bool = False,
        news_event_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Evaluates hard safety conditions:
        1. Emergency kill switch
        2. Daily drawdown stop (1%)
        3. 3 Consecutive losses halt
        4. Single active trade restriction
        5. Spread ceiling check
        6. Volatility spike check
        7. Stale data check
        8. News risk warning
        """
        # 1. Kill Switch
        risk_state = self.db.get_or_create_daily_risk_state()
        if risk_state.get("kill_switch") or self.kill_switch_memory:
            return {
                "approved": False,
                "reason": "EMERGENCY_KILL_SWITCH_ACTIVE",
                "details": "Emergency kill switch is currently active.",
            }

        # 2. Maximum Simultaneous Positions
        with self.db.get_connection() as conn:
            active_count = conn.execute(
                "SELECT COUNT(*) FROM signals WHERE status = 'ACTIVE' AND result = 'PENDING'"
            ).fetchone()[0]

            if active_count >= MAX_SIMULTANEOUS_POSITIONS:
                return {
                    "approved": False,
                    "reason": "MAX_POSITION_REACHED",
                    "details": f"Already have {active_count} active position(s). Max allowed: {MAX_SIMULTANEOUS_POSITIONS}.",
                }

        # 3. Consecutive Losses Halt (Disabled per user request)
        if ENABLE_CONSECUTIVE_LOSS_LIMIT and MAX_CONSECUTIVE_LOSSES > 0:
            consec_losses = risk_state.get("consecutive_losses", 0)
            halted = risk_state.get("consecutive_loss_halt", 0)
            if consec_losses >= MAX_CONSECUTIVE_LOSSES or halted:
                return {
                    "approved": False,
                    "reason": "MAX_CONSECUTIVE_LOSSES_REACHED",
                    "details": (
                        f"Trading halted after {consec_losses} consecutive losses. "
                        "Requires explicit /reset command or next-day reset."
                    ),
                }

        # 4. Daily Drawdown Stop
        if ENABLE_DAILY_LOSS_LIMIT and MAX_DAILY_LOSS_PCT > 0:
            paper_acc = self.db.get_paper_account()
            equity = paper_acc.get("equity", 10000.0)
            daily_loss_limit_usd = round(equity * (MAX_DAILY_LOSS_PCT / 100.0), 2)
            current_daily_loss = risk_state.get("daily_loss_usd", 0.0)

            if daily_loss_limit_usd > 0 and current_daily_loss >= daily_loss_limit_usd:
                return {
                    "approved": False,
                    "reason": "DAILY_LOSS_LIMIT_REACHED",
                    "details": (
                        f"Daily loss limit reached (${current_daily_loss:.2f} >= ${daily_loss_limit_usd:.2f} max allowed {MAX_DAILY_LOSS_PCT}%). "
                        "Trading paused until next day."
                    ),
                }

        # 5. Cooldown after SL
        cooldown_iso = risk_state.get("cooldown_until")
        if cooldown_iso:
            try:
                cooldown_time = datetime.fromisoformat(cooldown_iso)
                now_tz = datetime.now(pytz.timezone(TIMEZONE))
                if now_tz < cooldown_time:
                    rem_sec = int((cooldown_time - now_tz).total_seconds())
                    return {
                        "approved": False,
                        "reason": "COOLDOWN_ACTIVE",
                        "details": f"Post-stop loss cooldown active ({rem_sec // 60}m {rem_sec % 60}s remaining).",
                    }
            except Exception as e:
                logger.warning(f"Cooldown parse error: {e}")

        # 6. Spread Ceiling Filter
        spread_max = min(MAX_SPREAD_ALLOWED, 0.50)  # Conservative spread filter
        if current_spread > spread_max:
            return {
                "approved": False,
                "reason": "SPREAD_TOO_HIGH",
                "details": f"Spread (${current_spread:.2f}) exceeds maximum allowed threshold (${spread_max:.2f}).",
            }

        # 7. Volatility Spike Filter
        if avg_atr > 0 and current_atr > (avg_atr * VOLATILITY_SPIKE_THRESHOLD_ATR_MULT):
            return {
                "approved": False,
                "reason": "ABNORMAL_VOLATILITY_SPIKE",
                "details": f"ATR (${current_atr:.2f}) is abnormally elevated ({current_atr/avg_atr:.1f}x average).",
            }

        # 8. Stale Market Data Check
        if latest_candle_time:
            now_utc = datetime.now(pytz.UTC)
            candle_utc = latest_candle_time if latest_candle_time.tzinfo else pytz.UTC.localize(latest_candle_time)
            age_sec = (now_utc - candle_utc).total_seconds()
            if age_sec > 600:
                return {
                    "approved": False,
                    "reason": "STALE_DATA_DETECTED",
                    "details": f"Latest candle data is {int(age_sec)}s old; data feed may be delayed.",
                }

        # 9. News Risk Warning
        news_warning_text = ""
        if is_news_blackout:
            news_warning_text = f"High-impact news warning: {news_event_name or 'Major Economic Release'} window active."
            logger.warning(f"Trade approval issued with warning: {news_warning_text}")

        return {
            "approved": True,
            "reason": "ALL_RISK_GATES_CLEARED",
            "details": "Risk gates passed.",
            "news_warning": news_warning_text,
        }

    # ─────────────────────────────────────────────────────────
    # Risk State Management Actions
    # ─────────────────────────────────────────────────────────
    def trigger_sl_cooldown(self, minutes: int = COOLDOWN_MINUTES_AFTER_SL):
        """Sets cooldown after stop loss execution"""
        now_tz = datetime.now(pytz.timezone(TIMEZONE))
        cooldown_until = (now_tz + timedelta(minutes=minutes)).isoformat()
        self.db.set_cooldown(cooldown_until)
        logger.info(f"Stop loss cooldown activated until {cooldown_until}")

    def reset_consecutive_loss_halt(self):
        """Explicit reset for the 3-consecutive-loss halt (called by /reset command)"""
        self.db.reset_risk_halts()
        logger.info("Consecutive loss halt explicitly reset by operator.")

    def trigger_kill_switch(self, active: bool = True):
        """Toggles emergency kill switch"""
        self.kill_switch_memory = active
        self.db.set_kill_switch(active)
        logger.warning(f"Kill switch set to {active}")

    def toggle_kill_switch(self, active: bool):
        """Alias for trigger_kill_switch"""
        self.trigger_kill_switch(active)
