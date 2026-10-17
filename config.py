"""
============================================================
  AI GOLD SIGNAL SYSTEM — config.py
  সব ধরনের কনফিগারেশন এবং সেটিংস
============================================================
"""

import os
from dotenv import load_dotenv

load_dotenv()

# ── Telegram ──────────────────────────────────────────────
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_IDS  = [
    cid.strip()
    for cid in os.getenv("TELEGRAM_CHAT_ID", "").split(",")
    if cid.strip()
]

# ── AI / News APIs ────────────────────────────────────────
GEMINI_API_KEY       = os.getenv("GEMINI_API_KEY", "")
NEWS_API_KEY         = os.getenv("NEWS_API_KEY", "")
ALPHA_VANTAGE_KEY    = os.getenv("ALPHA_VANTAGE_KEY", "")

# ── System ────────────────────────────────────────────────
TIMEZONE                = os.getenv("TIMEZONE", "Asia/Dhaka")
SIGNAL_CHECK_INTERVAL   = int(os.getenv("SIGNAL_CHECK_INTERVAL", "1"))
RISK_PER_TRADE          = float(os.getenv("RISK_PER_TRADE", "0.5"))   # 0.25% - 0.5% per trade
MIN_CONFIDENCE          = int(os.getenv("MIN_CONFIDENCE", "70"))
NEWS_CHECK_INTERVAL     = int(os.getenv("NEWS_CHECK_INTERVAL", "15"))
DAILY_REPORT_TIME       = os.getenv("DAILY_REPORT_TIME", "23:59")

# ── Trading ───────────────────────────────────────────────
GOLD_SYMBOL  = os.getenv("GOLD_SYMBOL", "GC=F")
TIMEFRAMES   = os.getenv("TIMEFRAMES", "4h,1h,15m,5m").split(",")
MIN_RR_RATIO = float(os.getenv("MIN_RR_RATIO", "1.8"))

# ── Database ──────────────────────────────────────────────
DB_PATH = os.getenv("DB_PATH", "database/signals.db")

# ── News keywords for gold ────────────────────────────────
GOLD_NEWS_KEYWORDS = [
    "gold", "XAU", "XAUUSD", "gold price",
    "Federal Reserve", "Fed rate", "interest rate",
    "US dollar", "DXY", "inflation", "CPI", "NFP",
    "war", "conflict", "geopolitical", "sanction",
    "Ukraine", "Russia", "Middle East", "Iran",
    "China", "US China", "trade war",
    "safe haven", "precious metal",
    "FOMC", "GDP", "unemployment",
    "nuclear", "missile", "military",
]

# ── Timeframe mapping ─────────────────────────────────────
TF_MAP = {
    "1m":  "1m",
    "5m":  "5m",
    "15m": "15m",
    "1h":  "60m",
    "4h":  "1h",   # yfinance max 60m for intraday
    "1d":  "1d",
}

# ── Signal messages ───────────────────────────────────────
SIGNAL_EMOJIS = {
    "BUY":     "🟢 BUY",
    "SELL":    "🔴 SELL",
    "NEUTRAL": "⚪ NEUTRAL",
    "WAIT":    "🟡 WAIT",
}
