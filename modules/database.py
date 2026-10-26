"""
============================================================
  modules/database.py
  Database Manager for Gold QuickScalp AI
  SQLite with WAL Mode, Persistent Sequential Trade IDs & Risk State
============================================================
"""

import logging
import os
import sqlite3
import uuid
from datetime import datetime
from typing import Optional, List, Dict, Any
import pytz

from config import DB_PATH, TIMEZONE, PAPER_INITIAL_BALANCE

logger = logging.getLogger(__name__)


class DatabaseManager:
    """SQLite Database Manager with WAL mode, atomic sequential IDs, and audit logging"""

    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path
        self._init_db()

    def get_connection(self) -> sqlite3.Connection:
        """Returns SQLite connection with WAL journal mode and dict row factory"""
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        conn = sqlite3.connect(self.db_path, timeout=30.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA synchronous=NORMAL;")
        return conn

    def _init_db(self):
        """Initializes tables, indexes, and runs schema migrations"""
        with self.get_connection() as conn:
            cursor = conn.cursor()

            # 1. Sequential Trade Counter Table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS trade_counter (
                    id INTEGER PRIMARY KEY CHECK (id = 1),
                    counter INTEGER NOT NULL DEFAULT 0
                )
            """)
            cursor.execute("INSERT OR IGNORE INTO trade_counter (id, counter) VALUES (1, 0)")

            # 2. Signals & Trades Table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS signals (
                    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
                    trade_id            INTEGER NOT NULL,
                    signal_uuid         TEXT UNIQUE,
                    timestamp           TEXT NOT NULL,
                    mode                TEXT DEFAULT 'PAPER',
                    direction           TEXT NOT NULL,
                    entry_price         REAL NOT NULL,
                    tp1                 REAL NOT NULL,
                    tp2                 REAL NOT NULL,
                    sl                  REAL NOT NULL,
                    status              TEXT DEFAULT 'ACTIVE',
                    result              TEXT DEFAULT 'PENDING',
                    tp1_hit             INTEGER DEFAULT 0,
                    tp2_hit             INTEGER DEFAULT 0,
                    sl_hit              INTEGER DEFAULT 0,
                    partial_closed      INTEGER DEFAULT 0,
                    be_moved            INTEGER DEFAULT 0,
                    close_price         REAL,
                    exit_time           TEXT,
                    exit_reason         TEXT,
                    pnl_usd             REAL DEFAULT 0.0,
                    pnl_r               REAL DEFAULT 0.0,
                    pnl_pips            REAL DEFAULT 0.0,
                    commission          REAL DEFAULT 0.0,
                    slippage            REAL DEFAULT 0.0,
                    risk_pct            REAL DEFAULT 0.25,
                    suggested_lot       REAL DEFAULT 0.01,
                    spread              REAL DEFAULT 0.25,
                    setup_engine        TEXT,
                    target_basis        TEXT,
                    reasoning           TEXT
                )
            """)

            # Dynamic migration for signals table columns
            existing_cols = [c[1] for c in cursor.execute("PRAGMA table_info(signals)").fetchall()]
            new_columns = {
                "trade_id": "INTEGER DEFAULT 0",
                "tp1_hit": "INTEGER DEFAULT 0",
                "tp2_hit": "INTEGER DEFAULT 0",
                "partial_closed": "INTEGER DEFAULT 0",
                "be_moved": "INTEGER DEFAULT 0",
                "setup_engine": "TEXT",
            }
            for col, col_def in new_columns.items():
                if col not in existing_cols:
                    try:
                        cursor.execute(f"ALTER TABLE signals ADD COLUMN {col} {col_def}")
                        logger.info(f"Database migration: added column '{col}' to signals table.")
                    except Exception as e:
                        logger.warning(f"Migration note for {col}: {e}")

            # 3. Paper Trading Account
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS paper_account (
                    id                  INTEGER PRIMARY KEY CHECK (id = 1),
                    balance             REAL NOT NULL,
                    equity              REAL NOT NULL,
                    closed_pnl          REAL DEFAULT 0.0,
                    open_pnl            REAL DEFAULT 0.0,
                    total_trades        INTEGER DEFAULT 0,
                    winning_trades      INTEGER DEFAULT 0,
                    losing_trades       INTEGER DEFAULT 0,
                    updated_at          TEXT NOT NULL
                )
            """)
            now_iso = datetime.now(pytz.timezone(TIMEZONE)).isoformat()
            cursor.execute("""
                INSERT OR IGNORE INTO paper_account 
                (id, balance, equity, closed_pnl, open_pnl, total_trades, winning_trades, losing_trades, updated_at)
                VALUES (1, ?, ?, 0.0, 0.0, 0, 0, 0, ?)
            """, (PAPER_INITIAL_BALANCE, PAPER_INITIAL_BALANCE, now_iso))

            # 4. Trade Management Audit Log
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS trade_management_log (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    signal_id   INTEGER,
                    trade_id    INTEGER,
                    timestamp   TEXT NOT NULL,
                    event_type  TEXT NOT NULL,
                    old_price   REAL,
                    new_price   REAL,
                    reason      TEXT
                )
            """)

            trade_log_cols = [c[1] for c in cursor.execute("PRAGMA table_info(trade_management_log)").fetchall()]
            if "trade_id" not in trade_log_cols:
                try:
                    cursor.execute("ALTER TABLE trade_management_log ADD COLUMN trade_id INTEGER DEFAULT 0")
                except Exception as e:
                    logger.warning(f"Migration note for trade_management_log.trade_id: {e}")

            # 5. Risk State Table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS risk_state (
                    id                    INTEGER PRIMARY KEY AUTOINCREMENT,
                    date_str              TEXT UNIQUE,
                    daily_loss_usd        REAL DEFAULT 0.0,
                    daily_pnl_usd         REAL DEFAULT 0.0,
                    consecutive_losses    INTEGER DEFAULT 0,
                    consecutive_loss_halt INTEGER DEFAULT 0,
                    cooldown_until        TEXT,
                    kill_switch           INTEGER DEFAULT 0,
                    updated_at            TEXT NOT NULL
                )
            """)

            # Migration for risk_state
            risk_cols = [c[1] for c in cursor.execute("PRAGMA table_info(risk_state)").fetchall()]
            if "consecutive_loss_halt" not in risk_cols:
                try:
                    cursor.execute("ALTER TABLE risk_state ADD COLUMN consecutive_loss_halt INTEGER DEFAULT 0")
                except Exception as e:
                    logger.warning(f"Migration note for consecutive_loss_halt: {e}")

            
            # 6. Subscribers Table (Multi-user and Channel broadcasting)
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS subscribers (
                    chat_id     TEXT PRIMARY KEY,
                    username    TEXT DEFAULT '',
                    first_name  TEXT DEFAULT '',
                    is_active   INTEGER DEFAULT 1,
                    created_at  TEXT NOT NULL
                )
            ''')

            # Auto-register configured admin chat IDs
            try:
                from config import TELEGRAM_CHAT_IDS
                now_iso = datetime.now(pytz.timezone(TIMEZONE)).isoformat()
                for cid in TELEGRAM_CHAT_IDS:
                    if cid:
                        cursor.execute("""
                            INSERT OR IGNORE INTO subscribers (chat_id, username, first_name, is_active, created_at)
                            VALUES (?, 'Admin', 'Owner', 1, ?)
                        """, (str(cid), now_iso))
            except Exception as e:
                logger.debug(f"Admin auto-register note: {e}")

            conn.commit()

    # ─────────────────────────────────────────────────────────
    # Sequential Trade ID Generation (Atomic)
    # ─────────────────────────────────────────────────────────
    def get_next_trade_id(self) -> int:
        """
        Atomically increments and returns next persistent sequential trade ID (#001, #002, etc.).
        Survives crashes and restarts.
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("BEGIN IMMEDIATE")
            cursor.execute("UPDATE trade_counter SET counter = counter + 1 WHERE id = 1")
            cursor.execute("SELECT counter FROM trade_counter WHERE id = 1")
            row = cursor.fetchone()
            next_id = row[0] if row else 1
            conn.commit()
            return int(next_id)

    def get_current_trade_counter(self) -> int:
        """Returns the current counter value without incrementing"""
        with self.get_connection() as conn:
            row = conn.execute("SELECT counter FROM trade_counter WHERE id = 1").fetchone()
            return int(row[0]) if row else 0

    # ─────────────────────────────────────────────────────────
    # Signal Persistence & State Tracking
    # ─────────────────────────────────────────────────────────
    def save_signal(self, signal: Dict[str, Any]) -> int:
        """Saves a newly generated trade signal to database"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO signals (
                        trade_id, signal_uuid, timestamp, mode, direction,
                        entry_price, tp1, tp2, sl, status, result,
                        tp1_hit, tp2_hit, sl_hit, partial_closed, be_moved,
                        risk_pct, suggested_lot, spread, setup_engine,
                        target_basis, reasoning
                    ) VALUES (
                        ?, ?, ?, ?, ?,
                        ?, ?, ?, ?, 'ACTIVE', 'PENDING',
                        0, 0, 0, 0, 0,
                        ?, ?, ?, ?,
                        ?, ?
                    )
                """, (
                    signal.get("trade_id", 0),
                    signal.get("signal_uuid", str(uuid.uuid4())),
                    signal.get("timestamp", datetime.now(pytz.timezone(TIMEZONE)).isoformat()),
                    signal.get("mode", "PAPER"),
                    signal.get("direction"),
                    signal.get("entry"),
                    signal.get("tp1"),
                    signal.get("tp2"),
                    signal.get("sl"),
                    signal.get("risk_pct", 0.25),
                    signal.get("suggested_lot", 0.01),
                    signal.get("spread", 0.25),
                    signal.get("setup_engine", "Unknown"),
                    signal.get("target_basis", ""),
                    signal.get("reasoning", "")
                ))
                conn.commit()
                return cursor.lastrowid
        except Exception as e:
            logger.error(f"Error saving signal: {e}")
            return -1

    def get_active_signals(self) -> List[Dict[str, Any]]:
        """Returns all ACTIVE and PENDING signals"""
        try:
            with self.get_connection() as conn:
                rows = conn.execute("""
                    SELECT * FROM signals
                    WHERE status = 'ACTIVE' AND result = 'PENDING'
                    ORDER BY id ASC
                """).fetchall()
                return [dict(r) for r in rows]
        except Exception as e:
            logger.error(f"Error fetching active signals: {e}")
            return []

    def get_signal_by_trade_id(self, trade_id: int) -> Optional[Dict[str, Any]]:
        """Finds signal record by sequential trade ID"""
        with self.get_connection() as conn:
            row = conn.execute("SELECT * FROM signals WHERE trade_id = ?", (trade_id,)).fetchone()
            return dict(row) if row else None

    def mark_tp1_hit(self, signal_id: int, exit_price: float, new_sl: float, pnl_usd: float, now_str: str):
        """Marks TP1 as hit, updates partial close, and sets SL to Break-Even"""
        with self.get_connection() as conn:
            conn.execute("""
                UPDATE signals
                SET tp1_hit = 1,
                    partial_closed = 1,
                    be_moved = 1,
                    sl = ?
                WHERE id = ?
            """, (new_sl, signal_id))
            conn.execute("""
                INSERT INTO trade_management_log (signal_id, trade_id, timestamp, event_type, old_price, new_price, reason)
                SELECT id, trade_id, ?, 'TP1_HIT', entry_price, ?, 'TP1 reached; partial closed & SL moved to BE'
                FROM signals WHERE id = ?
            """, (now_str, exit_price, signal_id))
            conn.commit()

    def close_signal(
        self,
        signal_id: int,
        result: str,
        close_price: float,
        exit_reason: str,
        pnl_usd: float,
        pnl_r: float,
        pnl_pips: float,
        commission: float = 0.0,
        slippage: float = 0.0,
    ):
        """Closes a trade signal definitively"""
        now_str = datetime.now(pytz.timezone(TIMEZONE)).isoformat()
        with self.get_connection() as conn:
            tp2_hit_val = 1 if result == "TP2_HIT" else 0
            sl_hit_val = 1 if result in ("SL_HIT", "SL_AFTER_TP1") else 0

            conn.execute("""
                UPDATE signals
                SET status = 'CLOSED',
                    result = ?,
                    tp2_hit = CASE WHEN ? = 1 THEN 1 ELSE tp2_hit END,
                    sl_hit = CASE WHEN ? = 1 THEN 1 ELSE sl_hit END,
                    close_price = ?,
                    exit_time = ?,
                    exit_reason = ?,
                    pnl_usd = ?,
                    pnl_r = ?,
                    pnl_pips = ?,
                    commission = ?,
                    slippage = ?
                WHERE id = ?
            """, (
                result, tp2_hit_val, sl_hit_val, close_price, now_str, exit_reason,
                pnl_usd, pnl_r, pnl_pips, commission, slippage, signal_id
            ))

            conn.execute("""
                INSERT INTO trade_management_log (signal_id, trade_id, timestamp, event_type, old_price, new_price, reason)
                SELECT id, trade_id, ?, ?, entry_price, ?, ?
                FROM signals WHERE id = ?
            """, (now_str, result, close_price, exit_reason, signal_id))
            conn.commit()

    def cleanup_ghost_signals(self):
        """Clean up active/pending trades on startup to prevent stale state across restarts"""
        try:
            with self.get_connection() as conn:
                conn.execute("""
                    UPDATE signals
                    SET status = 'CLOSED', result = 'EXPIRED_ON_STARTUP', exit_reason = 'System restarted'
                    WHERE status = 'ACTIVE' AND result = 'PENDING'
                """)
                conn.commit()
            logger.info("Ghost signals checked and cleaned on startup.")
        except Exception as e:
            logger.error(f"Cleanup ghost signals error: {e}")

    def get_daily_stats(self) -> Dict[str, Any]:
        """Calculates today's closed trade statistics"""
        try:
            today_str = datetime.now(pytz.timezone(TIMEZONE)).strftime("%Y-%m-%d")
            with self.get_connection() as conn:
                rows = conn.execute("""
                    SELECT * FROM signals
                    WHERE timestamp LIKE ? AND status = 'CLOSED'
                """, (f"{today_str}%",)).fetchall()
                trades = [dict(r) for r in rows]
                total = len(trades)
                wins = sum(1 for t in trades if t.get("result") in ("TP1_HIT", "TP2_HIT") or t.get("pnl_usd", 0) > 0)
                losses = sum(1 for t in trades if t.get("result") == "SL_HIT" and t.get("pnl_usd", 0) <= 0)
                pnl = sum(t.get("pnl_usd", 0.0) for t in trades)
                winrate = round((wins / total * 100.0), 1) if total > 0 else 0.0
                return {
                    "total_trades": total,
                    "wins": wins,
                    "losses": losses,
                    "winrate": winrate,
                    "pnl_usd": round(pnl, 2),
                }
        except Exception as e:
            logger.error(f"Error getting daily stats: {e}")
            return {"total_trades": 0, "wins": 0, "losses": 0, "winrate": 0.0, "pnl_usd": 0.0}

    # ─────────────────────────────────────────────────────────
    # Paper Account Helpers
    # ─────────────────────────────────────────────────────────
    def get_paper_account(self) -> Dict[str, Any]:
        """Retrieves paper account balance and metrics"""
        with self.get_connection() as conn:
            row = conn.execute("SELECT * FROM paper_account WHERE id = 1").fetchone()
            if row:
                return dict(row)
            return {
                "balance": PAPER_INITIAL_BALANCE,
                "equity": PAPER_INITIAL_BALANCE,
                "closed_pnl": 0.0,
                "open_pnl": 0.0,
                "total_trades": 0,
                "winning_trades": 0,
                "losing_trades": 0,
                "updated_at": datetime.now(pytz.timezone(TIMEZONE)).isoformat(),
            }

    def update_paper_account(self, pnl: float, is_win: bool):
        """Updates paper trading account on closed trade or partial realization"""
        now_str = datetime.now(pytz.timezone(TIMEZONE)).isoformat()
        with self.get_connection() as conn:
            acc = self.get_paper_account()
            new_bal = round(acc["balance"] + pnl, 2)
            new_eq = new_bal
            closed_pnl = round(acc["closed_pnl"] + pnl, 2)
            total = acc["total_trades"] + 1
            wins = acc["winning_trades"] + (1 if is_win else 0)
            losses = acc["losing_trades"] + (0 if is_win else 1)

            conn.execute("""
                UPDATE paper_account
                SET balance = ?, equity = ?, closed_pnl = ?, open_pnl = 0.0,
                    total_trades = ?, winning_trades = ?, losing_trades = ?, updated_at = ?
                WHERE id = 1
            """, (new_bal, new_eq, closed_pnl, total, wins, losses, now_str))
            conn.commit()

    def reset_paper_account(self, initial_balance: float = PAPER_INITIAL_BALANCE):
        """Resets paper account to starting balance"""
        now_str = datetime.now(pytz.timezone(TIMEZONE)).isoformat()
        with self.get_connection() as conn:
            conn.execute("""
                UPDATE paper_account
                SET balance = ?, equity = ?, closed_pnl = 0.0, open_pnl = 0.0,
                    total_trades = 0, winning_trades = 0, losing_trades = 0, updated_at = ?
                WHERE id = 1
            """, (initial_balance, initial_balance, now_str))
            conn.commit()

    # ─────────────────────────────────────────────────────────
    # Risk State Helpers (1% DD & 3 Consecutive Losses)
    # ─────────────────────────────────────────────────────────
    def get_or_create_daily_risk_state(self) -> Dict[str, Any]:
        """Gets or initializes the risk state record for today"""
        today_str = datetime.now(pytz.timezone(TIMEZONE)).strftime("%Y-%m-%d")
        now_str = datetime.now(pytz.timezone(TIMEZONE)).isoformat()

        with self.get_connection() as conn:
            row = conn.execute("SELECT * FROM risk_state WHERE date_str = ?", (today_str,)).fetchone()
            if row:
                return dict(row)
            conn.execute("""
                INSERT INTO risk_state (date_str, daily_loss_usd, daily_pnl_usd, consecutive_losses, consecutive_loss_halt, cooldown_until, kill_switch, updated_at)
                VALUES (?, 0.0, 0.0, 0, 0, NULL, 0, ?)
            """, (today_str, now_str))
            conn.commit()
            row = conn.execute("SELECT * FROM risk_state WHERE date_str = ?", (today_str,)).fetchone()
            return dict(row)

    def record_trade_loss(self, loss_usd: float):
        """Records a realized loss: updates daily loss and consecutive loss counter"""
        today_str = datetime.now(pytz.timezone(TIMEZONE)).strftime("%Y-%m-%d")
        now_str = datetime.now(pytz.timezone(TIMEZONE)).isoformat()
        state = self.get_or_create_daily_risk_state()

        new_loss = round(state["daily_loss_usd"] + abs(loss_usd), 2)
        new_pnl = round(state["daily_pnl_usd"] - abs(loss_usd), 2)
        consec = state["consecutive_losses"] + 1

        with self.get_connection() as conn:
            conn.execute("""
                UPDATE risk_state
                SET daily_loss_usd = ?, daily_pnl_usd = ?, consecutive_losses = ?, consecutive_loss_halt = 0, updated_at = ?
                WHERE date_str = ?
            """, (new_loss, new_pnl, consec, now_str, today_str))
            conn.commit()

    def record_trade_win(self, profit_usd: float):
        """Records a realized win: resets consecutive losses and updates daily profit"""
        today_str = datetime.now(pytz.timezone(TIMEZONE)).strftime("%Y-%m-%d")
        now_str = datetime.now(pytz.timezone(TIMEZONE)).isoformat()
        state = self.get_or_create_daily_risk_state()

        new_pnl = round(state["daily_pnl_usd"] + profit_usd, 2)

        with self.get_connection() as conn:
            conn.execute("""
                UPDATE risk_state
                SET daily_pnl_usd = ?, consecutive_losses = 0, updated_at = ?
                WHERE date_str = ?
            """, (new_pnl, now_str, today_str))
            conn.commit()

    def reset_risk_halts(self):
        """Explicitly resets consecutive loss halt and daily loss halt (e.g. from /reset command)"""
        today_str = datetime.now(pytz.timezone(TIMEZONE)).strftime("%Y-%m-%d")
        now_str = datetime.now(pytz.timezone(TIMEZONE)).isoformat()
        with self.get_connection() as conn:
            conn.execute("""
                UPDATE risk_state
                SET consecutive_losses = 0, consecutive_loss_halt = 0, cooldown_until = NULL, updated_at = ?
                WHERE date_str = ?
            """, (now_str, today_str))
            conn.commit()
        logger.info("Risk halt manually reset.")

    def set_cooldown(self, cooldown_iso: str):
        """Sets cooldown timestamp after a stop-loss event"""
        today_str = datetime.now(pytz.timezone(TIMEZONE)).strftime("%Y-%m-%d")
        with self.get_connection() as conn:
            conn.execute("""
                UPDATE risk_state
                SET cooldown_until = ?, updated_at = ?
                WHERE date_str = ?
            """, (cooldown_iso, datetime.now(pytz.timezone(TIMEZONE)).isoformat(), today_str))
            conn.commit()

    def set_kill_switch(self, active: bool):
        """Sets emergency kill switch state"""
        today_str = datetime.now(pytz.timezone(TIMEZONE)).strftime("%Y-%m-%d")
        val = 1 if active else 0
        with self.get_connection() as conn:
            conn.execute("""
                UPDATE risk_state
                SET kill_switch = ?, updated_at = ?
                WHERE date_str = ?
            """, (val, datetime.now(pytz.timezone(TIMEZONE)).isoformat(), today_str))
            conn.commit()


    # ─────────────────────────────────────────────────────────
    # Subscriber Management (Multi-User & Channels)
    # ─────────────────────────────────────────────────────────
    def register_subscriber(self, chat_id: str, username: str = "", first_name: str = "") -> bool:
        """Registers or re-activates a subscriber chat ID"""
        now_str = datetime.now(pytz.timezone(TIMEZONE)).isoformat()
        with self.get_connection() as conn:
            conn.execute("""
                INSERT INTO subscribers (chat_id, username, first_name, is_active, created_at)
                VALUES (?, ?, ?, 1, ?)
                ON CONFLICT(chat_id) DO UPDATE SET
                    username = excluded.username,
                    first_name = excluded.first_name,
                    is_active = 1
            """, (str(chat_id), str(username or ""), str(first_name or ""), now_str))
            conn.commit()
        logger.info(f"Subscriber registered/updated: {chat_id} ({username})")
        return True

    def deactivate_subscriber(self, chat_id: str):
        """Deactivates a subscriber (e.g. if bot was blocked)"""
        with self.get_connection() as conn:
            conn.execute("UPDATE subscribers SET is_active = 0 WHERE chat_id = ?", (str(chat_id),))
            conn.commit()

    def get_all_subscribers(self) -> list:
        """Returns all active subscriber chat IDs"""
        with self.get_connection() as conn:
            rows = conn.execute("SELECT chat_id FROM subscribers WHERE is_active = 1").fetchall()
            return [str(r["chat_id"]) for r in rows]

    def get_subscriber_count(self) -> int:
        """Returns active subscriber count"""
        with self.get_connection() as conn:
            row = conn.execute("SELECT COUNT(*) as cnt FROM subscribers WHERE is_active = 1").fetchone()
            return row["cnt"] if row else 0


    # ─────────────────────────────────────────────────────────
    # Engine Performance Breakdown
    # ─────────────────────────────────────────────────────────
    def get_engine_performance_stats(self) -> dict:
        """Returns trade count, wins, losses, and win rate per engine"""
        with self.get_connection() as conn:
            rows = conn.execute("""
                SELECT
                    COALESCE(setup_engine, 'Unknown') as engine,
                    COUNT(*) as total_trades,
                    SUM(CASE WHEN result IN ('TP_HIT', 'TP1_HIT', 'TP2_HIT') THEN 1 ELSE 0 END) as wins,
                    SUM(CASE WHEN result = 'SL_HIT' THEN 1 ELSE 0 END) as losses,
                    COALESCE(SUM(pnl_usd), 0.0) as total_pnl
                FROM signals
                WHERE status = 'CLOSED'
                GROUP BY setup_engine
            """).fetchall()
            stats = {}
            for r in rows:
                t = r["total_trades"]
                w = r["wins"]
                l = r["losses"]
                wr = (w / (w + l) * 100) if (w + l) > 0 else 0.0
                stats[r["engine"]] = {
                    "total": t,
                    "wins": w,
                    "losses": l,
                    "win_rate": round(wr, 1),
                    "pnl_usd": round(r["total_pnl"], 2),
                }
            return stats
