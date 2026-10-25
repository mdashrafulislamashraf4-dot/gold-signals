"""
============================================================
  Gold QuickScalp AI — config.py
  Adaptive TP/SL Scalping Engine for XAUUSD Only
  Commander A Specification
============================================================
"""

import os
from dotenv import load_dotenv

load_dotenv()

# ── Operating Mode & Safety ────────────────────────────────
# Supported modes: "BACKTEST", "PAPER", "TELEGRAM_SIGNAL"
# Automated live order execution is STRICTLY DISABLED by default.
OPERATING_MODE = os.getenv("OPERATING_MODE", "PAPER").upper()
if OPERATING_MODE not in ("BACKTEST", "PAPER", "TELEGRAM_SIGNAL"):
    OPERATING_MODE = "PAPER"

LIVE_EXECUTION_AUTHORIZED = False  # Hard safety lock

# Emergency kill switch
KILL_SWITCH_ACTIVE = os.getenv("KILL_SWITCH_ACTIVE", "False").lower() in ("true", "1")

# ── Telegram Configuration ────────────────────────────────
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_IDS = [
    cid.strip()
    for cid in os.getenv("TELEGRAM_CHAT_ID", "").split(",")
    if cid.strip()
]

# ── External AI & News API Keys ───────────────────────────
GEMINI_API_KEY    = os.getenv("GEMINI_API_KEY", "")
NEWS_API_KEY      = os.getenv("NEWS_API_KEY", "")
ALPHA_VANTAGE_KEY = os.getenv("ALPHA_VANTAGE_KEY", "")

# ── System Settings & Timezone ────────────────────────────
TIMEZONE                    = os.getenv("TIMEZONE", "Asia/Dhaka")
SIGNAL_CHECK_INTERVAL       = int(os.getenv("SIGNAL_CHECK_INTERVAL", "5"))  # M5 cadence
MONITOR_CHECK_INTERVAL_SEC  = int(os.getenv("MONITOR_CHECK_INTERVAL_SEC", "15"))  # Trade monitor tick
NEWS_CHECK_INTERVAL_SECONDS = int(os.getenv("NEWS_CHECK_INTERVAL_SECONDS", "60"))

# ── Trading Instrument & Timeframes (XAUUSD ONLY) ─────────
INSTRUMENT       = "XAUUSD"
GOLD_SYMBOL      = os.getenv("GOLD_SYMBOL", "GC=F")
TIMEFRAME_TREND  = "15m"   # M15: Trend context (EMA 50, EMA 200, structure)
TIMEFRAME_SETUP  = "5m"    # M5: Setup detection (sweeps, BOS, pullbacks, breakouts)
TIMEFRAME_EXEC   = "1m"    # M1: Entry confirmation (EMA 20, closed-candle PA)

# ── Risk Management (Commander A Strict Spec) ─────────────
# Default risk per trade: 0.25% of equity; absolute ceiling: 0.50%
RISK_PER_TRADE             = min(float(os.getenv("RISK_PER_TRADE", "0.25")), 0.50)
MAX_RISK_PER_TRADE         = float(os.getenv("MAX_RISK_PER_TRADE", "0.50"))

# One open simulated trade at a time
MAX_SIMULTANEOUS_POSITIONS = 1

# Initial daily drawdown stop: 1%
ENABLE_DAILY_LOSS_LIMIT    = os.getenv("ENABLE_DAILY_LOSS_LIMIT", "True").lower() in ("true", "1")
MAX_DAILY_LOSS_PCT         = float(os.getenv("MAX_DAILY_LOSS_PCT", "1.0"))

# Consecutive loss limit is disabled per user request
ENABLE_CONSECUTIVE_LOSS_LIMIT = os.getenv("ENABLE_CONSECUTIVE_LOSS_LIMIT", "False").lower() in ("true", "1")
MAX_CONSECUTIVE_LOSSES     = int(os.getenv("MAX_CONSECUTIVE_LOSSES", "0"))

# Post-SL cooldown buffer
COOLDOWN_MINUTES_AFTER_SL  = int(os.getenv("COOLDOWN_MINUTES_AFTER_SL", "15"))

# Maximum permitted spread ($0.65 typical ceiling)
MAX_SPREAD_ALLOWED         = float(os.getenv("MAX_SPREAD_ALLOWED", "0.65"))

# Volatility spike filter multiplier
VOLATILITY_SPIKE_THRESHOLD_ATR_MULT = float(os.getenv("VOLATILITY_SPIKE_THRESHOLD_ATR_MULT", "2.5"))

# ── Webhook Security ──────────────────────────────────────
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "xauusd-smc-secret-key-2026")

# ── Adaptive Targets & Trade Management ───────────────────
# Minimum cost-adjusted R:R to accept trade
MIN_RR_RATIO          = float(os.getenv("MIN_RR_RATIO", "1.1"))
TARGET_RR_CANDIDATES  = [1.2, 1.5, 2.0]

# Partial position closing at TP1 (e.g. 0.50 = 50% closed at TP1)
PARTIAL_CLOSE_RATIO   = float(os.getenv("PARTIAL_CLOSE_RATIO", "0.50"))

# Move SL to break-even after TP1 is achieved
ENABLE_BREAK_EVEN     = os.getenv("ENABLE_BREAK_EVEN", "True").lower() in ("true", "1")
BREAK_EVEN_BUFFER     = float(os.getenv("BREAK_EVEN_BUFFER", "0.10"))  # $0.10 buffer above entry to cover cost

# ── Broker Contract Specifications (Standard XAUUSD CFD) ─
BROKER_NAME               = os.getenv("BROKER_NAME", "Standard CFD")
LOT_SIZE                  = float(os.getenv("BROKER_LOT_SIZE", "100.0"))        # 1 lot = 100 troy oz
MIN_LOT                   = float(os.getenv("BROKER_MIN_LOT", "0.01"))
LOT_STEP                  = float(os.getenv("BROKER_LOT_STEP", "0.01"))
POINT_VALUE               = float(os.getenv("BROKER_POINT_VALUE", "1.0"))       # $1/0.01 per lot
COMMISSION_PER_LOT        = float(os.getenv("COMMISSION_PER_LOT", "4.0"))       # $4 round-turn
ESTIMATED_SLIPPAGE_POINTS = float(os.getenv("ESTIMATED_SLIPPAGE_POINTS", "0.05")) # $0.05 slippage

# Paper trading starting balance
PAPER_INITIAL_BALANCE     = float(os.getenv("PAPER_INITIAL_BALANCE", "10000.0"))

# ── Database ──────────────────────────────────────────────
DB_PATH = os.getenv("DB_PATH", "database/signals.db")

# ── Macro Economic Keywords ───────────────────────────────
HIGH_IMPACT_EVENTS = [
    "CPI", "PCE", "Nonfarm Payrolls", "NFP", "Unemployment Rate",
    "FOMC", "Fed Interest Rate", "Federal Reserve", "Powell",
    "GDP", "PPI", "Retail Sales"
]

GOLD_NEWS_KEYWORDS = [
    "gold", "XAU", "XAUUSD", "gold price",
    "Federal Reserve", "Fed rate", "interest rate",
    "US dollar", "DXY", "inflation", "CPI", "NFP",
    "war", "conflict", "geopolitical", "safe haven"
]
