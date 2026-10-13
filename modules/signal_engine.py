"""
============================================================
  modules/signal_engine.py
  সিগনাল জেনারেশন এবং রিস্ক ম্যানেজমেন্ট ইঞ্জিন
============================================================
"""

import logging
import sqlite3
from datetime import datetime

import pytz

from config import TIMEZONE, RISK_PER_TRADE, DB_PATH

logger = logging.getLogger(__name__)


class SignalEngine:
    """
    টেকনিক্যাল + নিউজ + AI স্কোর কম্বাইন করে
    চূড়ান্ত ট্রেডিং সিগনাল তৈরি করে
    """

    # Weight configuration
    WEIGHTS = {
        "technical": 0.50,
        "news":      0.25,
        "ai":        0.25,
    }

    def __init__(self):
        self._init_db()

    # ─────────────────────────────────────────────────────────
    # Database
    # ─────────────────────────────────────────────────────────
    def _init_db(self):
        """SQLite database তৈরি করে"""
        import os
        os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)

        with sqlite3.connect(DB_PATH) as conn:
            conn.execute("PRAGMA journal_mode=WAL;")
            conn.execute("PRAGMA synchronous=NORMAL;")
            conn.execute("""
                CREATE TABLE IF NOT EXISTS signals (
                    id              INTEGER PRIMARY KEY AUTOINCREMENT,
                    daily_trade_num INTEGER DEFAULT 1,
                    timestamp       TEXT    NOT NULL,
                    direction       TEXT    NOT NULL,
                    entry_price     REAL,
                    tp1             REAL,
                    tp2             REAL,
                    tp3             REAL,
                    sl              REAL,
                    confidence      INTEGER,
                    tech_score      INTEGER,
                    news_score      INTEGER,
                    timeframe       TEXT,
                    status          TEXT DEFAULT 'ACTIVE',
                    result          TEXT DEFAULT 'PENDING',
                    tp_hit          INTEGER DEFAULT 0,
                    sl_hit          INTEGER DEFAULT 0,
                    close_price     REAL,
                    pnl_pips        REAL,
                    reasoning       TEXT,
                    rr_ratio        TEXT
                )
            """)
            try:
                conn.execute("ALTER TABLE signals ADD COLUMN daily_trade_num INTEGER DEFAULT 1")
            except Exception:
                pass
            conn.execute("""
                CREATE TABLE IF NOT EXISTS news_alerts (
                    id        INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    title     TEXT,
                    source    TEXT,
                    impact    TEXT,
                    sent      INTEGER DEFAULT 0
                )
            """)
            conn.commit()
        logger.info("Database initialized")

    # ─────────────────────────────────────────────────────────
    # Generate Signal
    # ─────────────────────────────────────────────────────────
    def generate_signal(
        self,
        technical_result: dict,
        news_result:      dict,
        ai_result:        dict,
        current_price:    float,
        timeframe:        str = "H1",
    ) -> dict:
        """
        সব এনালাইসিস থেকে চূড়ান্ত সিগনাল তৈরি করে
        """
        tech_score = technical_result.get("score", 50)
        news_score = news_result.get("score", 50)
        ai_conf    = ai_result.get("confidence", 60)

        # Convert AI direction to score
        ai_dir = ai_result.get("direction", "NEUTRAL")
        if ai_dir == "BUY":
            ai_score = 50 + (ai_conf / 2)
        elif ai_dir == "SELL":
            ai_score = 50 - (ai_conf / 2)
        else:
            ai_score = 50

        # Weighted combined score
        combined_score = (
            tech_score * self.WEIGHTS["technical"] +
            news_score * self.WEIGHTS["news"] +
            ai_score   * self.WEIGHTS["ai"]
        )

        # Determine direction
        if combined_score >= 65:
            direction = "BUY"
        elif combined_score <= 35:
            direction = "SELL"
        else:
            direction = "NEUTRAL"

        # Use AI prices if available, else calculate
        entry = ai_result.get("entry", current_price) or current_price
        tp1   = ai_result.get("tp1", 0)
        tp2   = ai_result.get("tp2", 0)
        tp3   = ai_result.get("tp3", 0)
        sl    = ai_result.get("sl",  0)

        # Fallback: ATR-based TP/SL
        atr = technical_result.get("details", {}).get("ATR", 15)
        if atr is None or atr == 0:
            atr = 15

        if tp1 == 0 or tp1 == current_price:
            if direction == "BUY":
                tp1 = round(current_price + atr * 1.5, 2)
                tp2 = round(current_price + atr * 3.0, 2)
                tp3 = round(current_price + atr * 5.0, 2)
                sl  = round(current_price - atr * 1.2, 2)
            elif direction == "SELL":
                tp1 = round(current_price - atr * 1.5, 2)
                tp2 = round(current_price - atr * 3.0, 2)
                tp3 = round(current_price - atr * 5.0, 2)
                sl  = round(current_price + atr * 1.2, 2)
            else:
                tp1 = tp2 = tp3 = current_price
                sl  = current_price

        # Calculate R:R
        if direction in ("BUY", "SELL") and sl != 0 and tp2 != 0:
            risk   = abs(entry - sl)
            reward = abs(tp2 - entry)
            rr     = round(reward / risk, 1) if risk > 0 else 0
            rr_str = f"1:{rr}"
        else:
            rr_str = ai_result.get("rr_ratio", "1:2")

        # Confidence
        confidence = int(min(abs(combined_score - 50) * 2 + 40, 95))

        # Reasoning
        reasoning = (
            ai_result.get("reasoning", []) or
            technical_result.get("buy_signals", [])[:3] or
            technical_result.get("sell_signals", [])[:3]
        )

        signal = {
            "direction":    direction,
            "entry":        round(entry, 2),
            "tp1":          round(tp1, 2),
            "tp2":          round(tp2, 2),
            "tp3":          round(tp3, 2),
            "sl":           round(sl, 2),
            "confidence":   confidence,
            "combined_score": round(combined_score, 1),
            "tech_score":   tech_score,
            "news_score":   news_score,
            "ai_score":     round(ai_score, 1),
            "rr_ratio":     rr_str,
            "timeframe":    timeframe,
            "risk_level":   ai_result.get("risk_level", "মাঝারি (Medium)"),
            "validity":     ai_result.get("validity", "৪-৮ ঘণ্টা"),
            "reasoning":    reasoning,
            "warnings":     ai_result.get("warnings", []),
            "patterns":     technical_result.get("patterns", []),
            "risk_per_trade": RISK_PER_TRADE,
            "timestamp":    datetime.now(pytz.timezone(TIMEZONE)).isoformat(),
        }

        # Return calculated signal (only saved to DB when dispatched to Telegram)
        return signal

    # ─────────────────────────────────────────────────────────
    # Save & Update Signals in DB
    # ─────────────────────────────────────────────────────────
    def save_signal(self, signal: dict) -> int:
        """সিগনাল টেলিগ্রামে পাঠানোর পর ডেটাবেসে ACTIVE হিসেবে সেভ করে (আজকের দিনের ট্রেড নম্বর সহ)"""
        try:
            tz = pytz.timezone(TIMEZONE)
            today_str = datetime.now(tz).strftime("%Y-%m-%d")

            with sqlite3.connect(DB_PATH) as conn:
                cur = conn.cursor()
                row = cur.execute("SELECT COUNT(*) FROM signals WHERE timestamp LIKE ?", (f"{today_str}%",)).fetchone()
                daily_num = (row[0] if row else 0) + 1
                signal["daily_trade_num"] = daily_num

                cur.execute("""
                    INSERT INTO signals
                    (daily_trade_num, timestamp, direction, entry_price, tp1, tp2, tp3, sl,
                     confidence, tech_score, news_score, timeframe, status, result,
                     tp_hit, sl_hit, reasoning, rr_ratio)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?,?, 'ACTIVE', 'PENDING', 0, 0, ?,?)
                """, (
                    daily_num,
                    signal["timestamp"],
                    signal["direction"],
                    signal["entry"],
                    signal["tp1"],
                    signal["tp2"],
                    signal["tp3"],
                    signal["sl"],
                    signal["confidence"],
                    signal["tech_score"],
                    signal["news_score"],
                    signal["timeframe"],
                    str(signal.get("reasoning", [])),
                    signal["rr_ratio"],
                ))
                conn.commit()
                return cur.lastrowid
        except Exception as e:
            logger.error(f"DB save error: {e}")
            return -1

    def get_active_signals(self) -> list:
        """চালু থাকা সব ACTIVE সিগনাল বের করে"""
        try:
            with sqlite3.connect(DB_PATH) as conn:
                conn.row_factory = sqlite3.Row
                rows = conn.execute("""
                    SELECT * FROM signals WHERE status='ACTIVE' ORDER BY id DESC
                """).fetchall()
            return [dict(r) for r in rows]
        except Exception as e:
            logger.error(f"DB get active signals error: {e}")
            return []

    def mark_tp1_hit(self, signal_id: int, current_price: float, breakeven_sl: float):
        """TP1 হিট হলে আপডেট করে এবং স্টপ লস (SL) এন্ট্রি প্রাইসে (Breakeven) স্থানান্তর করে। ট্রেড ACTIVE থাকে TP2-এর জন্য।"""
        try:
            with sqlite3.connect(DB_PATH) as conn:
                conn.execute("""
                    UPDATE signals
                    SET tp_hit=1, close_price=?, sl=?, result='TP1_HIT'
                    WHERE id=?
                """, (current_price, breakeven_sl, signal_id))
                conn.commit()
            logger.info(f"Signal #{signal_id} TP1 marked at {current_price}, SL moved to breakeven {breakeven_sl}")
        except Exception as e:
            logger.error(f"DB TP1 update error: {e}")

    def close_signal(self, signal_id: int, result: str, close_price: float, tp_hit: int = 0, sl_hit: int = 0):
        """সিগনাল সম্পন্ন হলে বা বন্ধ হলে স্ট্যাটাস CLOSED করে এবং PnL হিসাব করে"""
        try:
            with sqlite3.connect(DB_PATH) as conn:
                conn.row_factory = sqlite3.Row
                row = conn.execute("SELECT direction, entry_price FROM signals WHERE id=?", (signal_id,)).fetchone()
                pnl_pips = 0.0
                if row:
                    entry = row["entry_price"] or close_price
                    direction = row["direction"]
                    diff = (close_price - entry) if direction == "BUY" else (entry - close_price)
                    pnl_pips = round(diff * 10, 1)  # 1 USD move = 10 pips in XAUUSD

                conn.execute("""
                    UPDATE signals
                    SET result=?, close_price=?, tp_hit=?, sl_hit=?, pnl_pips=?, status='CLOSED'
                    WHERE id=?
                """, (result, close_price, tp_hit, sl_hit, pnl_pips, signal_id))
                conn.commit()
            logger.info(f"Signal #{signal_id} CLOSED with result: {result} at {close_price} (PnL: {pnl_pips} pips)")
        except Exception as e:
            logger.error(f"DB close signal error: {e}")

    def update_signal_result(self, signal_id: int, result: str, close_price: float, tp_hit: int = 0, sl_hit: int = 0):
        """Backward compatibility wrapper for close_signal"""
        self.close_signal(signal_id, result, close_price, tp_hit, sl_hit)

    def cleanup_ghost_signals(self, max_hours: int = 12):
        """পূর্বে জমে থাকা ১২ ঘণ্টার বেশি পুরনো সক্রিয় সিগনাল স্বয়ংক্রিয়ভাবে বন্ধ করে (রিসেন্ট ট্রেড সুরক্ষিত রাখে)"""
        try:
            tz = pytz.timezone(TIMEZONE)
            now = datetime.now(tz)
            with sqlite3.connect(DB_PATH) as conn:
                conn.row_factory = sqlite3.Row
                rows = conn.execute("SELECT id, timestamp FROM signals WHERE status='ACTIVE'").fetchall()
                expired = 0
                for r in rows:
                    try:
                        sig_time = datetime.fromisoformat(r["timestamp"])
                        if (now - sig_time).total_seconds() > max_hours * 3600:
                            conn.execute("UPDATE signals SET status='CLOSED', result='EXPIRED' WHERE id=?", (r["id"],))
                            expired += 1
                    except Exception:
                        pass
                conn.commit()
            if expired > 0:
                logger.info(f"Cleaned up {expired} expired active signals (> {max_hours}h old)")
        except Exception as e:
            logger.error(f"Cleanup ghost signals error: {e}")

    # ─────────────────────────────────────────────────────────
    # Performance Stats
    # ─────────────────────────────────────────────────────────
    def get_daily_stats(self) -> dict:
        """আজকের সিগনাল পারফরম্যান্স বের করে"""
        try:
            tz    = pytz.timezone(TIMEZONE)
            today = datetime.now(tz).strftime("%Y-%m-%d")

            with sqlite3.connect(DB_PATH) as conn:
                conn.row_factory = sqlite3.Row
                rows = conn.execute("""
                    SELECT * FROM signals
                    WHERE timestamp LIKE ?
                    ORDER BY timestamp DESC
                """, (f"{today}%",)).fetchall()

            signals = [dict(r) for r in rows]
            tp_hits = sum(1 for s in signals if s.get("tp_hit", 0) > 0)
            sl_hits = sum(1 for s in signals if s.get("sl_hit", 0) > 0)
            pending = sum(1 for s in signals if s.get("status") == "ACTIVE")

            total_closed = tp_hits + sl_hits
            win_rate = (tp_hits / total_closed * 100) if total_closed > 0 else 0

            return {
                "date":      today,
                "total":     len(signals),
                "tp_hits":   tp_hits,
                "sl_hits":   sl_hits,
                "pending":   pending,
                "win_rate":  round(win_rate, 1),
                "signals":   signals,
            }
        except Exception as e:
            logger.error(f"Daily stats error: {e}")
            return {"total": 0, "tp_hits": 0, "sl_hits": 0, "win_rate": 0, "signals": []}

    def get_weekly_stats(self) -> dict:
        """এই সপ্তাহের সিগনাল পারফরম্যান্স বের করে"""
        try:
            tz      = pytz.timezone(TIMEZONE)
            now     = datetime.now(tz)
            # Monday of this week
            monday  = now - __import__("datetime").timedelta(days=now.weekday())
            from_dt = monday.strftime("%Y-%m-%d")

            with sqlite3.connect(DB_PATH) as conn:
                conn.row_factory = sqlite3.Row
                rows = conn.execute("""
                    SELECT * FROM signals
                    WHERE timestamp >= ?
                    ORDER BY timestamp DESC
                """, (from_dt,)).fetchall()

            signals  = [dict(r) for r in rows]
            tp_hits  = sum(1 for s in signals if s.get("tp_hit", 0) > 0)
            sl_hits  = sum(1 for s in signals if s.get("sl_hit", 0) > 0)
            total_cl = tp_hits + sl_hits
            win_rate = (tp_hits / total_cl * 100) if total_cl > 0 else 0

            buys  = sum(1 for s in signals if s.get("direction") == "BUY")
            sells = sum(1 for s in signals if s.get("direction") == "SELL")

            return {
                "from_date": from_dt,
                "total":     len(signals),
                "buys":      buys,
                "sells":     sells,
                "tp_hits":   tp_hits,
                "sl_hits":   sl_hits,
                "win_rate":  round(win_rate, 1),
                "signals":   signals[:20],
            }
        except Exception as e:
            logger.error(f"Weekly stats error: {e}")
            return {"total": 0, "tp_hits": 0, "sl_hits": 0, "win_rate": 0}

    # ─────────────────────────────────────────────────────────
    # Active Signal Monitoring
    # ─────────────────────────────────────────────────────────
    def check_active_signals(self, current_price: float) -> list:
        """
        চালু সিগনালগুলো চেক করে TP/SL হিট হয়েছে কি না।
        TP1 একবার হিট হলে স্টপ লস Breakeven-এ নেওয়া হয় এবং আর TP1 এলার্ট দেওয়া হয় না।
        """
        alerts = []
        try:
            with sqlite3.connect(DB_PATH) as conn:
                conn.row_factory = sqlite3.Row
                rows = conn.execute("""
                    SELECT * FROM signals WHERE status='ACTIVE'
                """).fetchall()

            tz = pytz.timezone(TIMEZONE)
            now = datetime.now(tz)

            for row in rows:
                s   = dict(row)
                sid = s["id"]
                dir = s["direction"]
                entry = s.get("entry_price", 0)
                tp1, tp2, tp3, sl = s.get("tp1", 0), s.get("tp2", 0), s.get("tp3", 0), s.get("sl", 0)
                tp_hit = s.get("tp_hit", 0)

                # Timeout check: Auto-close signals older than 12 hours
                try:
                    sig_time = datetime.fromisoformat(s["timestamp"])
                    if (now - sig_time).total_seconds() > 12 * 3600:
                        logger.info(f"Signal #{sid} timed out after 12h — closing")
                        self.close_signal(sid, result="TIMEOUT", close_price=current_price, tp_hit=tp_hit)
                        continue
                except Exception:
                    pass

                if dir == "BUY":
                    # TP3 check
                    if tp3 and current_price >= tp3:
                        self.close_signal(sid, result="TP3_HIT", close_price=current_price, tp_hit=3)
                        alerts.append({"type": "TP3", "signal": s, "price": current_price})
                    # TP2 check
                    elif tp2 and current_price >= tp2 and tp_hit < 2:
                        self.close_signal(sid, result="TP2_HIT", close_price=current_price, tp_hit=2)
                        alerts.append({"type": "TP2", "signal": s, "price": current_price})
                    # TP1 check (only once if tp_hit < 1)
                    elif tp1 and current_price >= tp1 and tp_hit < 1:
                        be_sl = round(entry + 0.30, 2)  # Spread buffer to protect profits
                        self.mark_tp1_hit(sid, current_price, breakeven_sl=be_sl)
                        alerts.append({"type": "TP1", "signal": s, "price": current_price})
                    # Stop loss check
                    elif sl and current_price <= sl:
                        if tp_hit >= 1:
                            self.close_signal(sid, result="BREAKEVEN_CLOSED", close_price=current_price, tp_hit=tp_hit)
                            alerts.append({"type": "BREAKEVEN", "signal": s, "price": current_price})
                        else:
                            self.close_signal(sid, result="SL_HIT", close_price=current_price, sl_hit=1)
                            alerts.append({"type": "SL", "signal": s, "price": current_price})

                elif dir == "SELL":
                    # TP3 check
                    if tp3 and current_price <= tp3:
                        self.close_signal(sid, result="TP3_HIT", close_price=current_price, tp_hit=3)
                        alerts.append({"type": "TP3", "signal": s, "price": current_price})
                    # TP2 check
                    elif tp2 and current_price <= tp2 and tp_hit < 2:
                        self.close_signal(sid, result="TP2_HIT", close_price=current_price, tp_hit=2)
                        alerts.append({"type": "TP2", "signal": s, "price": current_price})
                    # TP1 check (only once if tp_hit < 1)
                    elif tp1 and current_price <= tp1 and tp_hit < 1:
                        be_sl = round(entry - 0.30, 2)  # Spread buffer to protect profits
                        self.mark_tp1_hit(sid, current_price, breakeven_sl=be_sl)
                        alerts.append({"type": "TP1", "signal": s, "price": current_price})
                    # Stop loss check
                    elif sl and current_price >= sl:
                        if tp_hit >= 1:
                            self.close_signal(sid, result="BREAKEVEN_CLOSED", close_price=current_price, tp_hit=tp_hit)
                            alerts.append({"type": "BREAKEVEN", "signal": s, "price": current_price})
                        else:
                            self.close_signal(sid, result="SL_HIT", close_price=current_price, sl_hit=1)
                            alerts.append({"type": "SL", "signal": s, "price": current_price})

        except Exception as e:
            logger.error(f"Signal monitoring error: {e}", exc_info=True)

        return alerts
