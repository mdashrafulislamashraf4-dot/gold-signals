"""
============================================================
  dashboard/routes.py
  REST API & Webhook Endpoints for Web Dashboard
  Real-time market status, signal monitoring, and TradingView alerts.
============================================================
"""

import json
import logging
from datetime import datetime
from typing import Dict, Any, Optional

from flask import Blueprint, render_template, request, jsonify
from config import WEBHOOK_SECRET, OPERATING_MODE
from modules.database import DatabaseManager
from modules.risk_engine import RiskEngine

logger = logging.getLogger(__name__)

dashboard_bp = Blueprint(
    "dashboard",
    __name__,
    template_folder="templates",
    static_folder="static",
)

# Shared system references injected from main.py
system_context: Dict[str, Any] = {}


def init_dashboard_context(
    market_data,
    technical,
    news_analyzer,
    signal_engine,
    trade_manager,
    db_manager: Optional[DatabaseManager] = None,
    risk_engine: Optional[RiskEngine] = None,
):
    global system_context
    system_context["market_data"] = market_data
    system_context["technical"] = technical
    system_context["news"] = news_analyzer
    system_context["signal_engine"] = signal_engine
    system_context["trade_manager"] = trade_manager
    system_context["db"] = db_manager or DatabaseManager()
    system_context["risk"] = risk_engine or RiskEngine(system_context["db"])
    logger.info("Dashboard Blueprint context initialized successfully.")


@dashboard_bp.route("/")
def index():
    return render_template("index.html")


@dashboard_bp.route("/api/status")
def api_status():
    md = system_context.get("market_data")
    ta = system_context.get("technical")
    na = system_context.get("news")
    se = system_context.get("signal_engine")
    db = system_context.get("db")
    re = system_context.get("risk")

    snapshot = md.get_market_snapshot() if md else {}
    acc = db.get_paper_account() if db else {}
    risk_state = db.get_or_create_daily_risk_state() if db else {}

    # Get latest active or most recent signal
    latest_sig = {}
    if db:
        with db.get_connection() as conn:
            row = conn.execute("SELECT * FROM signals ORDER BY id DESC LIMIT 1").fetchone()
            if row:
                latest_sig = dict(row)
                if latest_sig.get("reasoning"):
                    latest_sig["reasoning"] = latest_sig["reasoning"].split("\n")

    return jsonify({
        "mode": OPERATING_MODE,
        "market": snapshot,
        "technical": {
            "trend_15m": system_context.get("last_trend_15m", "NEUTRAL"),
            "sweep": system_context.get("last_sweep", {}),
        },
        "news": {
            "news_risk": system_context.get("last_news_risk", False),
        },
        "signal": latest_sig,
        "account": acc,
        "risk_state": risk_state,
        "health": md.get_health_status() if md else {"status": "UNKNOWN"},
    })


@dashboard_bp.route("/api/signals")
def api_signals():
    db = system_context.get("db")
    if not db:
        return jsonify([])
    with db.get_connection() as conn:
        rows = conn.execute("""
            SELECT id, signal_uuid, timestamp, direction, entry_price, sl, tp1,
                   suggested_lot, rr_ratio, status, result, pnl_usd, target_basis
            FROM signals
            ORDER BY id DESC LIMIT 50
        """).fetchall()
        return jsonify([dict(r) for r in rows])


@dashboard_bp.route("/api/backtest")
def api_backtest():
    db = system_context.get("db")
    if not db:
        return jsonify([])
    with db.get_connection() as conn:
        rows = conn.execute("""
            SELECT target_mode as mode, win_rate_pct as win_rate,
                   profit_factor, net_profit_usd as net_profit
            FROM backtest_results
            ORDER BY id DESC LIMIT 5
        """).fetchall()
        return jsonify([dict(r) for r in rows])


@dashboard_bp.route("/api/killswitch", methods=["POST"])
def api_killswitch():
    re = system_context.get("risk")
    db = system_context.get("db")
    if not re or not db:
        return jsonify({"success": False, "error": "System not initialized"}), 500

    state = db.get_or_create_daily_risk_state()
    new_state = not bool(state.get("kill_switch"))
    re.trigger_kill_switch(new_state)
    return jsonify({"success": True, "kill_switch": new_state})


@dashboard_bp.route("/api/paper/reset", methods=["POST"])
def api_paper_reset():
    db = system_context.get("db")
    if not db:
        return jsonify({"success": False}), 500
    db.reset_paper_account(10000.0)
    return jsonify({"success": True, "message": "Paper account reset to $10,000"})


@dashboard_bp.route("/api/webhook/tradingview", methods=["POST"])
def api_webhook_tradingview():
    """
    Receives Pine Script v6 strategy webhook alerts.
    Validates secret, performs risk check, and dispatches to Telegram and Paper account.
    """
    try:
        data = request.get_json(force=True, silent=True) or {}
        incoming_secret = data.get("secret", "")

        if incoming_secret != WEBHOOK_SECRET:
            logger.warning(f"Unauthorized webhook attempt with secret: {incoming_secret}")
            return jsonify({"status": "error", "message": "Unauthorized secret"}), 401

        action = data.get("action", "").upper()
        symbol = data.get("symbol", "XAUUSD")
        entry = float(data.get("entry", 0))
        sl = float(data.get("sl", 0))
        tp = float(data.get("tp", 0))

        if action not in ("BUY", "SELL") or entry <= 0:
            return jsonify({"status": "error", "message": "Invalid webhook payload"}), 400

        logger.info(f"Received verified TradingView webhook: {action} {symbol} @ {entry} (SL: {sl}, TP: {tp})")

        # Pass through Risk Engine
        re = system_context.get("risk")
        se = system_context.get("signal_engine")
        db = system_context.get("db")

        approval = re.evaluate_trade_approval(current_spread=0.25, current_atr=3.0, avg_atr=3.0)
        if not approval["approved"]:
            logger.warning(f"Webhook signal rejected by risk engine: {approval['details']}")
            return jsonify({"status": "rejected", "reason": approval["details"]}), 403

        # Create paper signal
        signal_dict = {
            "signal_uuid": f"TV-{str(datetime.now().timestamp())[-6:]}",
            "mode": OPERATING_MODE,
            "direction": action,
            "entry": entry,
            "tp1": tp,
            "tp2": tp,
            "tp3": tp,
            "sl": sl,
            "confidence": 85,
            "tech_score": 85,
            "news_score": 50,
            "ai_score": 75,
            "timeframe": "TradingView 1M/5M Alert",
            "risk_per_trade": data.get("risk_pct", 0.25),
            "suggested_lot": 0.05,
            "spread": 0.25,
            "rr_ratio": f"1:{round(abs(tp-entry)/abs(entry-sl), 1) if abs(entry-sl)>0 else 1.0}",
            "target_basis": "TradingView Webhook Alert Target",
            "reasoning": ["TradingView Pine Script v6 verified bar-close alert"],
            "timestamp": datetime.now().isoformat(),
        }

        sig_id = se.save_signal(signal_dict) if se else -1
        return jsonify({"status": "accepted", "signal_id": sig_id, "signal_uuid": signal_dict["signal_uuid"]})

    except Exception as e:
        logger.error(f"Error handling TradingView webhook: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500
