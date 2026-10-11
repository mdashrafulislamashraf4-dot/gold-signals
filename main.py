"""
============================================================
  main.py
  AI GOLD SIGNAL SYSTEM — Main Entry Point
  চালু করতে: python main.py
============================================================
"""

import logging
import os
import signal
import sys
import time
from datetime import datetime

import pytz

# ── Setup logging ──────────────────────────────────────────
os.makedirs("logs", exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(
            f"logs/gold_signals_{datetime.now().strftime('%Y%m%d')}.log",
            encoding="utf-8",
        ),
    ],
)
logger = logging.getLogger("main")

# ── Import modules ─────────────────────────────────────────
from config import (
    TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_IDS,
    GEMINI_API_KEY, NEWS_API_KEY,
    TIMEZONE, SIGNAL_CHECK_INTERVAL,
)
from modules.market_data     import MarketDataFetcher
from modules.technical       import TechnicalAnalyzer
from modules.news_analyzer   import NewsAnalyzer
from modules.ai_analyzer     import AIAnalyzer
from modules.signal_engine   import SignalEngine
from modules.telegram_bot    import TelegramBot
from modules.scheduler       import TaskScheduler
from modules.command_handler import CommandHandler
import threading
from flask import Flask

web_app = Flask(__name__)

@web_app.route('/')
def home():
    return "AI Gold Signal System is RUNNING 24/7!"

def start_web_server():
    port = int(os.environ.get("PORT", 8080))
    import logging as py_logging
    py_logging.getLogger('werkzeug').setLevel(py_logging.ERROR)
    try:
        web_app.run(host="0.0.0.0", port=port, use_reloader=False)
    except Exception as e:
        logger.warning(f"Web server warning: {e}")


def validate_config():
    """কনফিগারেশন ভেলিডেট করে"""
    errors = []
    if not TELEGRAM_BOT_TOKEN or TELEGRAM_BOT_TOKEN == "YOUR_TELEGRAM_BOT_TOKEN_HERE":
        errors.append("❌ TELEGRAM_BOT_TOKEN is not set in .env file")
    if not TELEGRAM_CHAT_IDS:
        errors.append("❌ TELEGRAM_CHAT_ID is not set in .env file")
    if not GEMINI_API_KEY or GEMINI_API_KEY == "YOUR_GEMINI_API_KEY_HERE":
        logger.warning("⚠️  GEMINI_API_KEY not set — using fallback analysis")
    if not NEWS_API_KEY or NEWS_API_KEY == "YOUR_NEWS_API_KEY_HERE":
        logger.warning("⚠️  NEWS_API_KEY not set — using free RSS feeds only")
    return errors


def print_banner():
    """স্টার্টআপ ব্যানার প্রিন্ট করে"""
    banner = """
╔══════════════════════════════════════════════════════════════╗
║                                                              ║
║     🏆  AI GOLD (XAUUSD) SIGNAL SYSTEM  🏆                  ║
║                                                              ║
║     📊 Technical Analysis  +  🤖 AI (Gemini)                ║
║     📰 News Sentiment      +  📈 Multi-Timeframe            ║
║     📱 Telegram Bot        +  💾 SQLite Database            ║
║                                                              ║
║     ⚡ Monitoring XAUUSD 24/7 for profit opportunities      ║
║                                                              ║
╚══════════════════════════════════════════════════════════════╝
"""
    print(banner)


def main():
    """মেইন ফাংশন — সব মডিউল শুরু করে"""
    print_banner()

    # ── Validate Config ────────────────────────────────────
    errors = validate_config()
    if errors:
        for e in errors:
            logger.error(e)
        logger.error("\n❌ Please fix the above errors in your .env file")
        logger.error("📖 See .env.example for reference")
        sys.exit(1)

    logger.info("✅ Configuration validated")
    logger.info(f"🕐 Timezone: {TIMEZONE}")
    logger.info(f"📊 Signal check interval: {SIGNAL_CHECK_INTERVAL} minutes")
    logger.info(f"📱 Telegram Chat IDs: {TELEGRAM_CHAT_IDS}")

    # ── Initialize Modules ─────────────────────────────────
    logger.info("🔧 Initializing modules...")

    market_data   = MarketDataFetcher()
    technical     = TechnicalAnalyzer()
    news_analyzer = NewsAnalyzer()
    ai_analyzer   = AIAnalyzer(api_key=GEMINI_API_KEY)
    signal_engine = SignalEngine()
    telegram_bot  = TelegramBot(token=TELEGRAM_BOT_TOKEN, chat_ids=TELEGRAM_CHAT_IDS)

    logger.info("✅ All modules initialized")

    # ── Test Telegram Connection ───────────────────────────
    logger.info("📱 Testing Telegram connection...")
    if not telegram_bot.send_startup_message():
        logger.error("❌ Cannot send Telegram message. Check your bot token and chat ID.")
        sys.exit(1)
    logger.info("✅ Telegram connection successful!")

    # ── Initialize Scheduler ───────────────────────────────
    scheduler = TaskScheduler(
        market_data=market_data,
        technical=technical,
        news_analyzer=news_analyzer,
        ai_analyzer=ai_analyzer,
        signal_engine=signal_engine,
        telegram_bot=telegram_bot,
    )

    # ── Initialize Command Handler ─────────────────────────
    cmd_handler = CommandHandler(
        market_data=market_data,
        technical=technical,
        news_analyzer=news_analyzer,
        ai_analyzer=ai_analyzer,
        signal_engine=signal_engine,
        telegram_bot=telegram_bot,
        scheduler=scheduler,
    )

    # ── Start Services ─────────────────────────────────────
    logger.info("🚀 Starting all services...")
    threading.Thread(target=start_web_server, daemon=True).start()
    scheduler.start()
    cmd_handler.start_polling()

    logger.info("━" * 60)
    logger.info("✅ AI GOLD SIGNAL SYSTEM IS RUNNING!")
    logger.info("📊 Analyzing XAUUSD market continuously...")
    logger.info("📱 Telegram bot is listening for commands...")
    logger.info("Press Ctrl+C to stop")
    logger.info("━" * 60)

    # ── Run initial analysis immediately ───────────────────
    logger.info("🔍 Running initial analysis...")
    time.sleep(3)
    try:
        init_sig = scheduler.run_analysis(send_regardless=True)
        if init_sig and init_sig.get("direction") == "NEUTRAL":
            telegram_bot.send_message(
                f"📊 <b>Initial Market Scan Complete</b>\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"💰 <b>Gold Price:</b> <code>${init_sig.get('entry', 0)}</code>\n"
                f"⚖️ <b>Status:</b> <b>NEUTRAL / WAITING</b>\n"
                f"📈 <b>Technical Score:</b> <b>{init_sig.get('tech_score', 0)}/100</b>\n"
                f"🤖 <b>AI Confidence:</b> <b>{init_sig.get('confidence', 0)}%</b>\n\n"
                f"<i>The system is scanning every 15 mins and will alert immediately when a high-probability BUY/SELL setup is detected!</i>"
            )
    except Exception as e:
        logger.error(f"Initial analysis error: {e}")

    # ── Graceful Shutdown ──────────────────────────────────
    def shutdown(signum, frame):
        logger.info("\n🛑 Shutting down gracefully...")
        scheduler.stop()
        cmd_handler.stop_polling()
        telegram_bot.send_message("🛑 <b>AI Gold Signal System has been stopped.</b>")
        logger.info("✅ System stopped. Goodbye!")
        sys.exit(0)

    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    # ── Keep running ───────────────────────────────────────
    while True:
        try:
            time.sleep(60)
            # Log heartbeat every hour
            now = datetime.now(pytz.timezone(TIMEZONE))
            if now.minute == 0:
                price = market_data.get_current_price()
                logger.info(f"💓 Heartbeat | Gold: {price} | {now.strftime('%H:%M %Z')}")
        except KeyboardInterrupt:
            shutdown(None, None)
        except Exception as e:
            logger.error(f"Main loop error: {e}")
            time.sleep(10)


if __name__ == "__main__":
    main()
