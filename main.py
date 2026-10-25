"""
============================================================
  main.py
  Gold QuickScalp AI — Adaptive TP/SL Scalping Engine
  Commander A Specification — XAUUSD Only
  Run: python main.py
============================================================
"""

import logging
import os
import signal
import sys
import threading
import time
from datetime import datetime
import pytz

# ── Logging Configuration ──────────────────────────────────
os.makedirs("logs", exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(
            f"logs/gold_quickscalp_{datetime.now().strftime('%Y%m%d')}.log",
            encoding="utf-8",
        ),
    ],
)
logger = logging.getLogger("main")

# ── Module Imports ─────────────────────────────────────────
from config import (
    OPERATING_MODE,
    TELEGRAM_BOT_TOKEN,
    TELEGRAM_CHAT_IDS,
    GEMINI_API_KEY,
    NEWS_API_KEY,
    TIMEZONE,
    SIGNAL_CHECK_INTERVAL,
    RISK_PER_TRADE,
    MAX_RISK_PER_TRADE,
    MAX_DAILY_LOSS_PCT,
    MAX_CONSECUTIVE_LOSSES,
    LIVE_EXECUTION_AUTHORIZED,
)
from modules.database        import DatabaseManager
from modules.risk_engine     import RiskEngine
from modules.trade_manager   import TradeManager
from modules.setup_engines   import SetupEngines
from modules.market_data     import MarketDataFetcher
from modules.news_analyzer   import NewsAnalyzer
from modules.ai_analyzer     import AIAnalyzer
from modules.telegram_bot    import TelegramBot
from modules.signal_engine   import SignalEngine
from modules.scheduler       import TaskScheduler
from modules.command_handler import CommandHandler

# Optional Flask web server
try:
    from dashboard.routes import dashboard_bp, init_dashboard_context
    from flask import Flask
    web_app = Flask(__name__, template_folder="dashboard/templates")
    web_app.register_blueprint(dashboard_bp)
    HAS_DASHBOARD = True
except Exception as e:
    logger.debug(f"Dashboard routes note: {e}")
    HAS_DASHBOARD = False


def start_web_server():
    """Runs local diagnostic dashboard or cloud health check server for Render / Railway"""
    port = int(os.environ.get("PORT", 8080))
    if HAS_DASHBOARD:
        import logging as py_logging
        py_logging.getLogger("werkzeug").setLevel(py_logging.ERROR)
        try:
            logger.info(f"🌐 Web Dashboard running on http://0.0.0.0:{port}")
            web_app.run(host="0.0.0.0", port=port, use_reloader=False)
            return
        except Exception as e:
            logger.warning(f"Web server warning: {e}")

    # Fallback minimal HTTP health check for Cloud deployments
    try:
        from http.server import HTTPServer, BaseHTTPRequestHandler
        class HealthCheckHandler(BaseHTTPRequestHandler):
            def do_GET(self):
                self.send_response(200)
                self.send_header("Content-type", "text/plain")
                self.end_headers()
                self.wfile.write(b"Gold QuickScalp AI is Online")
            def log_message(self, format, *args):
                pass
        server = HTTPServer(("0.0.0.0", port), HealthCheckHandler)
        logger.info(f"🌐 Cloud Health Check Server running on port {port}")
        server.serve_forever()
    except Exception as e:
        logger.warning(f"Fallback HTTP server error: {e}")


def validate_config():
    """Validates required credentials according to operating mode"""
    errors = []
    if OPERATING_MODE in ("TELEGRAM_SIGNAL", "PAPER", "LIVE"):
        if not TELEGRAM_BOT_TOKEN or TELEGRAM_BOT_TOKEN == "YOUR_TELEGRAM_BOT_TOKEN_HERE":
            logger.warning("⚠️  TELEGRAM_BOT_TOKEN not configured in .env (Telegram signals will be skipped)")
        if not TELEGRAM_CHAT_IDS or TELEGRAM_CHAT_IDS == ["YOUR_CHAT_ID_HERE"]:
            logger.warning("⚠️  TELEGRAM_CHAT_ID not configured in .env")
    return errors


def print_banner():
    """Prints startup configuration summary"""
    banner = f"""
╔══════════════════════════════════════════════════════════════╗
║              GOLD QUICKSCALP AI — COMMANDER A                ║
║           Adaptive TP/SL XAUUSD Continuous Scalper           ║
╠══════════════════════════════════════════════════════════════╣
║  Instrument:   XAUUSD (Gold CFD Only)                        ║
║  Timeframes:   M15 (Trend) | M5 (Setup) | M1 (Confirmation)  ║
║  Engines:      1. Liquidity Sweep + BOS                      ║
║                2. Trend Pullback + EMA 20/50 Retest          ║
║                3. Range Breakout + Retest                    ║
║  Mode:         {OPERATING_MODE:<45} ║
║  Live Orders:  DISABLED BY DEFAULT (Safety Locked)           ║
║  Risk / Trade: {RISK_PER_TRADE}% of equity (Max {MAX_RISK_PER_TRADE}%)                   ║
║  DD Stop:      {MAX_DAILY_LOSS_PCT}% Daily Drawdown Ceiling                  ║
║  Monitoring:   24/7 Continuous (Session Restrictions: None)  ║
╚══════════════════════════════════════════════════════════════╝
"""
    print(banner)


def main():
    """Main system orchestrator"""
    print_banner()

    validate_config()
    logger.info("Initializing Gold QuickScalp AI components...")

    # 1. Database & State Recovery
    db_manager = DatabaseManager()
    logger.info(f"SQLite Database verified (Counter: #{db_manager.get_current_trade_counter():03d})")

    # 2. Risk Guardian
    risk_engine = RiskEngine(db_manager)

    # 3. Trade Lifecycle Manager
    trade_manager = TradeManager(db_manager, risk_engine)

    # 4. Market Data Ingestion
    market_data = MarketDataFetcher()

    # 5. Setup Engines (3 Independent Engines)
    setup_engines = SetupEngines()

    # 6. Telegram Bot Interface
    telegram_bot = TelegramBot(token=TELEGRAM_BOT_TOKEN, chat_ids=TELEGRAM_CHAT_IDS)

    # 7. Signal Engine
    signal_engine = SignalEngine(
        db_manager=db_manager,
        risk_engine=risk_engine,
        setup_engines=setup_engines,
        telegram_bot=telegram_bot,
        trade_manager=trade_manager,
    )
    signal_engine.cleanup_ghost_signals()

    # 8. External News & AI Context
    news_analyzer = NewsAnalyzer()
    ai_analyzer   = AIAnalyzer(api_key=GEMINI_API_KEY)

    # 9. Cloud / Web Server Port Binding (Mandatory for Render / Railway)
    if HAS_DASHBOARD:
        try:
            init_dashboard_context(
                market_data=market_data,
                technical=setup_engines,
                news_analyzer=news_analyzer,
                signal_engine=signal_engine,
                trade_manager=trade_manager,
                db_manager=db_manager,
                risk_engine=risk_engine,
            )
        except Exception as e:
            logger.debug(f"Dashboard init note: {e}")
    threading.Thread(target=start_web_server, daemon=True).start()

    # 10. Background 24/7 Scheduler
    scheduler = TaskScheduler(
        market_data=market_data,
        signal_engine=signal_engine,
        news_analyzer=news_analyzer,
        ai_analyzer=ai_analyzer,
    )

    # 11. Telegram Command Handler (/start, /status, /reset)
    cmd_handler = CommandHandler(
        market_data=market_data,
        signal_engine=signal_engine,
        telegram_bot=telegram_bot,
        risk_engine=risk_engine,
        news_analyzer=news_analyzer,
        ai_analyzer=ai_analyzer,
        scheduler=scheduler,
    )

    # 12. Test Telegram Connectivity
    if TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_IDS:
        logger.info("Verifying Telegram connection...")
        try:
            telegram_bot.send_startup_message()
            logger.info("Telegram connection confirmed.")
        except Exception as e:
            logger.warning(f"Telegram startup test warning: {e}")

    # 13. Start Services
    scheduler.start()
    if TELEGRAM_BOT_TOKEN:
        cmd_handler.start_polling()

    logger.info("🚀 Gold QuickScalp AI is actively monitoring XAUUSD...")

    # 14. Graceful Shutdown Handler
    def shutdown(signum, frame):
        logger.info("\n🛑 Halting Gold QuickScalp AI gracefully...")
        scheduler.stop()
        cmd_handler.stop_polling()
        if TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_IDS:
            telegram_bot.send_shutdown_message()
        logger.info("System halted cleanly. Goodbye.")
        sys.exit(0)

    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    # 15. Keep-Alive Loop with Hourly Heartbeat
    while True:
        try:
            time.sleep(60)
            now_tz = datetime.now(pytz.timezone(TIMEZONE))
            if now_tz.minute == 0:
                p = market_data.get_current_price()
                logger.info(f"💓 Heartbeat | XAUUSD: {p} | Mode: {OPERATING_MODE} | {now_tz.strftime('%H:%M %Z')}")
        except KeyboardInterrupt:
            shutdown(None, None)
        except Exception as e:
            logger.error(f"Main loop note: {e}")
            time.sleep(5)


if __name__ == "__main__":
    main()
