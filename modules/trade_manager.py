"""
============================================================
  modules/trade_manager.py
  Dynamic Trade Manager for Gold QuickScalp AI
  Two-Stage TP Lifecycle, Partial Close & Conservative Execution Rules
============================================================
"""

import logging
from datetime import datetime
from typing import Dict, Any, List, Optional
import pytz
import pandas as pd

from config import (
    TIMEZONE,
    PARTIAL_CLOSE_RATIO,
    ENABLE_BREAK_EVEN,
    BREAK_EVEN_BUFFER,
    LOT_SIZE,
    COMMISSION_PER_LOT,
    ESTIMATED_SLIPPAGE_POINTS,
)
from modules.database import DatabaseManager
from modules.risk_engine import RiskEngine

logger = logging.getLogger(__name__)


class TradeManager:
    """
    Monitors and manages active XAUUSD positions.
    Enforces sequential trade IDs, two-stage TP (TP1 partial close + BE move, TP2 runner exit),
    conservative execution rules, and zero duplicate alerts.
    """

    def __init__(self, db_manager: Optional[DatabaseManager] = None, risk_engine: Optional[RiskEngine] = None):
        self.db = db_manager or DatabaseManager()
        self.risk = risk_engine or RiskEngine(self.db)

    def process_open_trades(
        self,
        current_price: float,
        current_spread: float,
        df_1m: Optional[pd.DataFrame] = None,
    ) -> List[Dict[str, Any]]:
        """
        Evaluates open trades against incoming market data.
        Returns a list of confirmed trade events (e.g. TP1_HIT, TP2_HIT, SL_HIT).
        """
        events = []
        now_tz = datetime.now(pytz.timezone(TIMEZONE))
        now_str = now_tz.isoformat()

        # Query all currently active and pending trades
        active_trades = self.db.get_active_signals()
        if not active_trades:
            return events

        # Determine price boundaries (candle High/Low if available, else current spot)
        candle_high = current_price
        candle_low  = current_price
        if df_1m is not None and not df_1m.empty:
            try:
                last_bar = df_1m.iloc[-1]
                candle_high = max(current_price, float(last_bar["High"]))
                candle_low  = min(current_price, float(last_bar["Low"]))
            except Exception as e:
                logger.debug(f"Error parsing 1M bar high/low: {e}")

        for trade in active_trades:
            sig_id     = trade["id"]
            trade_id   = trade.get("trade_id") or sig_id
            direction  = trade["direction"]
            entry      = float(trade["entry_price"])
            sl         = float(trade["sl"])
            tp1        = float(trade["tp1"])
            tp2        = float(trade["tp2"])
            tp1_hit    = int(trade.get("tp1_hit", 0))
            full_lot   = float(trade.get("suggested_lot", 0.01))
            risk_dist  = abs(entry - sl) or 2.0

            comm_total = round(full_lot * COMMISSION_PER_LOT, 2)
            slippage_pt = ESTIMATED_SLIPPAGE_POINTS

            # ─────────────────────────────────────────────────────
            # STAGE 1: TP1 NOT YET HIT
            # ─────────────────────────────────────────────────────
            if tp1_hit == 0:
                if direction == "BUY":
                    sl_touched  = candle_low <= sl
                    tp1_touched = candle_high >= tp1

                    # Conservative Execution Rule:
                    # If candle simultaneously spans both SL and TP, conservative
                    # rule assumes adverse SL hit first.
                    if sl_touched and tp1_touched:
                        logger.warning(f"Trade #{trade_id:03d}: Candle touched both SL and TP1. Conservative rule triggers SL.")
                        sl_touched = True
                        tp1_touched = False

                    if sl_touched:
                        exit_price = round(sl - slippage_pt, 2)
                        pnl_dist   = exit_price - entry
                        gross_pnl  = round(pnl_dist * full_lot * LOT_SIZE, 2)
                        net_pnl    = round(gross_pnl - comm_total, 2)
                        pnl_r      = round(pnl_dist / risk_dist, 2)
                        pnl_pips   = round(pnl_dist * 10.0, 1)

                        self.db.close_signal(
                            signal_id=sig_id,
                            result="SL_HIT",
                            close_price=exit_price,
                            exit_reason="Stop Loss hit",
                            pnl_usd=net_pnl,
                            pnl_r=pnl_r,
                            pnl_pips=pnl_pips,
                            commission=comm_total,
                            slippage=slippage_pt,
                        )
                        self.db.update_paper_account(net_pnl, is_win=False)
                        self.db.record_trade_loss(abs(net_pnl))
                        self.risk.trigger_sl_cooldown()

                        events.append({
                            "event": "SL_HIT",
                            "trade_id": trade_id,
                            "signal_id": sig_id,
                            "exit_price": exit_price,
                            "net_pnl": net_pnl,
                        })
                        continue

                    elif tp1_touched:
                        exit_price = round(tp1 - slippage_pt, 2)
                        partial_ratio = PARTIAL_CLOSE_RATIO  # e.g. 0.50
                        partial_lot   = round(full_lot * partial_ratio, 2)
                        pnl_dist      = exit_price - entry
                        gross_pnl     = round(pnl_dist * partial_lot * LOT_SIZE, 2)
                        comm_partial  = round(partial_lot * COMMISSION_PER_LOT, 2)
                        net_partial   = round(gross_pnl - comm_partial, 2)

                        # Move SL to Break-Even (entry + buffer)
                        new_sl = round(entry + BREAK_EVEN_BUFFER, 2) if ENABLE_BREAK_EVEN else sl

                        self.db.mark_tp1_hit(
                            signal_id=sig_id,
                            exit_price=exit_price,
                            new_sl=new_sl,
                            pnl_usd=net_partial,
                            now_str=now_str,
                        )
                        self.db.update_paper_account(net_partial, is_win=True)
                        self.db.record_trade_win(net_partial)

                        events.append({
                            "event": "TP1_HIT",
                            "trade_id": trade_id,
                            "signal_id": sig_id,
                            "exit_price": exit_price,
                            "partial_pnl": net_partial,
                            "new_sl": new_sl,
                        })
                        continue

                elif direction == "SELL":
                    sl_touched  = candle_high >= sl
                    tp1_touched = candle_low <= tp1

                    if sl_touched and tp1_touched:
                        logger.warning(f"Trade #{trade_id:03d}: Candle touched both SL and TP1. Conservative rule triggers SL.")
                        sl_touched = True
                        tp1_touched = False

                    if sl_touched:
                        exit_price = round(sl + slippage_pt, 2)
                        pnl_dist   = entry - exit_price
                        gross_pnl  = round(pnl_dist * full_lot * LOT_SIZE, 2)
                        net_pnl    = round(gross_pnl - comm_total, 2)
                        pnl_r      = round(pnl_dist / risk_dist, 2)
                        pnl_pips   = round(pnl_dist * 10.0, 1)

                        self.db.close_signal(
                            signal_id=sig_id,
                            result="SL_HIT",
                            close_price=exit_price,
                            exit_reason="Stop Loss hit",
                            pnl_usd=net_pnl,
                            pnl_r=pnl_r,
                            pnl_pips=pnl_pips,
                            commission=comm_total,
                            slippage=slippage_pt,
                        )
                        self.db.update_paper_account(net_pnl, is_win=False)
                        self.db.record_trade_loss(abs(net_pnl))
                        self.risk.trigger_sl_cooldown()

                        events.append({
                            "event": "SL_HIT",
                            "trade_id": trade_id,
                            "signal_id": sig_id,
                            "exit_price": exit_price,
                            "net_pnl": net_pnl,
                        })
                        continue

                    elif tp1_touched:
                        exit_price = round(tp1 + slippage_pt, 2)
                        partial_ratio = PARTIAL_CLOSE_RATIO
                        partial_lot   = round(full_lot * partial_ratio, 2)
                        pnl_dist      = entry - exit_price
                        gross_pnl     = round(pnl_dist * partial_lot * LOT_SIZE, 2)
                        comm_partial  = round(partial_lot * COMMISSION_PER_LOT, 2)
                        net_partial   = round(gross_pnl - comm_partial, 2)

                        new_sl = round(entry - BREAK_EVEN_BUFFER, 2) if ENABLE_BREAK_EVEN else sl

                        self.db.mark_tp1_hit(
                            signal_id=sig_id,
                            exit_price=exit_price,
                            new_sl=new_sl,
                            pnl_usd=net_partial,
                            now_str=now_str,
                        )
                        self.db.update_paper_account(net_partial, is_win=True)
                        self.db.record_trade_win(net_partial)

                        events.append({
                            "event": "TP1_HIT",
                            "trade_id": trade_id,
                            "signal_id": sig_id,
                            "exit_price": exit_price,
                            "partial_pnl": net_partial,
                            "new_sl": new_sl,
                        })
                        continue

            # ─────────────────────────────────────────────────────
            # STAGE 2: TP1 ALREADY HIT (RUNNER POSITION ONLY)
            # ─────────────────────────────────────────────────────
            else:
                remaining_lot = round(full_lot * (1.0 - PARTIAL_CLOSE_RATIO), 2)
                comm_rem      = round(remaining_lot * COMMISSION_PER_LOT, 2)

                if direction == "BUY":
                    be_sl_touched = candle_low <= sl
                    tp2_touched   = candle_high >= tp2

                    if be_sl_touched and tp2_touched:
                        # Conservative rule: adverse exit first
                        be_sl_touched = True
                        tp2_touched = False

                    if be_sl_touched:
                        exit_price = round(sl - slippage_pt, 2)
                        pnl_dist   = exit_price - entry
                        gross_pnl  = round(pnl_dist * remaining_lot * LOT_SIZE, 2)
                        net_pnl    = round(gross_pnl - comm_rem, 2)
                        pnl_r      = round(pnl_dist / risk_dist, 2)
                        pnl_pips   = round(pnl_dist * 10.0, 1)

                        self.db.close_signal(
                            signal_id=sig_id,
                            result="SL_HIT",
                            close_price=exit_price,
                            exit_reason="Break-Even Stop Loss reached after TP1",
                            pnl_usd=net_pnl,
                            pnl_r=pnl_r,
                            pnl_pips=pnl_pips,
                            commission=comm_rem,
                            slippage=slippage_pt,
                        )
                        self.db.update_paper_account(net_pnl, is_win=(net_pnl >= 0))

                        events.append({
                            "event": "SL_HIT",
                            "trade_id": trade_id,
                            "signal_id": sig_id,
                            "exit_price": exit_price,
                            "net_pnl": net_pnl,
                        })
                        continue

                    elif tp2_touched:
                        exit_price = round(tp2 - slippage_pt, 2)
                        pnl_dist   = exit_price - entry
                        gross_pnl  = round(pnl_dist * remaining_lot * LOT_SIZE, 2)
                        net_pnl    = round(gross_pnl - comm_rem, 2)
                        pnl_r      = round(pnl_dist / risk_dist, 2)
                        pnl_pips   = round(pnl_dist * 10.0, 1)

                        self.db.close_signal(
                            signal_id=sig_id,
                            result="TP2_HIT",
                            close_price=exit_price,
                            exit_reason="Target TP2 reached",
                            pnl_usd=net_pnl,
                            pnl_r=pnl_r,
                            pnl_pips=pnl_pips,
                            commission=comm_rem,
                            slippage=slippage_pt,
                        )
                        self.db.update_paper_account(net_pnl, is_win=True)
                        self.db.record_trade_win(net_pnl)

                        events.append({
                            "event": "TP2_HIT",
                            "trade_id": trade_id,
                            "signal_id": sig_id,
                            "exit_price": exit_price,
                            "net_pnl": net_pnl,
                        })
                        continue

                elif direction == "SELL":
                    be_sl_touched = candle_high >= sl
                    tp2_touched   = candle_low <= tp2

                    if be_sl_touched and tp2_touched:
                        be_sl_touched = True
                        tp2_touched = False

                    if be_sl_touched:
                        exit_price = round(sl + slippage_pt, 2)
                        pnl_dist   = entry - exit_price
                        gross_pnl  = round(pnl_dist * remaining_lot * LOT_SIZE, 2)
                        net_pnl    = round(gross_pnl - comm_rem, 2)
                        pnl_r      = round(pnl_dist / risk_dist, 2)
                        pnl_pips   = round(pnl_dist * 10.0, 1)

                        self.db.close_signal(
                            signal_id=sig_id,
                            result="SL_HIT",
                            close_price=exit_price,
                            exit_reason="Break-Even Stop Loss reached after TP1",
                            pnl_usd=net_pnl,
                            pnl_r=pnl_r,
                            pnl_pips=pnl_pips,
                            commission=comm_rem,
                            slippage=slippage_pt,
                        )
                        self.db.update_paper_account(net_pnl, is_win=(net_pnl >= 0))

                        events.append({
                            "event": "SL_HIT",
                            "trade_id": trade_id,
                            "signal_id": sig_id,
                            "exit_price": exit_price,
                            "net_pnl": net_pnl,
                        })
                        continue

                    elif tp2_touched:
                        exit_price = round(tp2 + slippage_pt, 2)
                        pnl_dist   = entry - exit_price
                        gross_pnl  = round(pnl_dist * remaining_lot * LOT_SIZE, 2)
                        net_pnl    = round(gross_pnl - comm_rem, 2)
                        pnl_r      = round(pnl_dist / risk_dist, 2)
                        pnl_pips   = round(pnl_dist * 10.0, 1)

                        self.db.close_signal(
                            signal_id=sig_id,
                            result="TP2_HIT",
                            close_price=exit_price,
                            exit_reason="Target TP2 reached",
                            pnl_usd=net_pnl,
                            pnl_r=pnl_r,
                            pnl_pips=pnl_pips,
                            commission=comm_rem,
                            slippage=slippage_pt,
                        )
                        self.db.update_paper_account(net_pnl, is_win=True)
                        self.db.record_trade_win(net_pnl)

                        events.append({
                            "event": "TP2_HIT",
                            "trade_id": trade_id,
                            "signal_id": sig_id,
                            "exit_price": exit_price,
                            "net_pnl": net_pnl,
                        })
                        continue

        return events
