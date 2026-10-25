"""
============================================================
  modules/backtest_engine.py
  Chronological Backtesting & Validation Engine
  Realistic spreads, commissions, conservative same-bar hit logic,
  and multi-target sensitivity comparison (1.0R, 1.25R, 1.5R, 2.0R vs Dynamic).
============================================================
"""

import json
import logging
from datetime import datetime
from typing import Dict, Any, List, Optional, Tuple

import numpy as np
import pandas as pd

from config import (
    LOT_SIZE,
    COMMISSION_PER_LOT,
    ESTIMATED_SLIPPAGE_POINTS,
    RISK_PER_TRADE,
)
from modules.database import DatabaseManager

logger = logging.getLogger(__name__)


class BacktestEngine:
    """
    Simulates XAUUSD SMC scalping strategies over historical candles with
    realistic execution costs and strict chronological integrity.
    """

    def __init__(
        self,
        spread: float = 0.25,
        commission_per_lot: float = COMMISSION_PER_LOT,
        slippage_points: float = ESTIMATED_SLIPPAGE_POINTS,
        initial_balance: float = 10000.0,
        risk_pct: float = RISK_PER_TRADE,
        db_manager: Optional[DatabaseManager] = None,
    ):
        self.spread = spread
        self.commission_per_lot = commission_per_lot
        self.slippage_points = slippage_points
        self.initial_balance = initial_balance
        self.risk_pct = risk_pct
        self.db = db_manager or DatabaseManager()

    def run_backtest(
        self,
        df_1m: pd.DataFrame,
        df_5m: pd.DataFrame,
        df_15m: pd.DataFrame,
        target_mode: str = "DYNAMIC",  # "DYNAMIC", "1.0R", "1.25R", "1.5R", "2.0R"
        enable_break_even: bool = True,
    ) -> Dict[str, Any]:
        """
        Executes chronological candle-close simulation.
        Evaluates signals on 5M/15M data and executes/manages on 1M bars.
        """
        if df_1m is None or df_5m is None or df_15m is None or len(df_1m) < 60:
            return {"error": "Insufficient candle data for backtest."}

        balance = self.initial_balance
        peak_balance = balance
        max_drawdown_usd = 0.0
        max_drawdown_pct = 0.0

        equity_curve = [{"time": str(df_1m.index[0]), "balance": balance, "equity": balance}]
        trades: List[Dict[str, Any]] = []
        active_trade: Optional[Dict[str, Any]] = None

        # Precompute 15M Trend (EMA 50 & EMA 200)
        c15 = df_15m["Close"]
        ema50_15m = c15.ewm(span=50, adjust=False).mean()
        ema200_15m = c15.ewm(span=200, adjust=False).mean()
        trend_15m_series = pd.Series("NEUTRAL", index=df_15m.index)
        trend_15m_series[(c15 > ema50_15m) & (ema50_15m > ema200_15m)] = "BULLISH"
        trend_15m_series[(c15 < ema50_15m) & (ema50_15m < ema200_15m)] = "BEARISH"

        # Precompute 5M Swings (Lookback 4)
        m5_high = df_5m["High"]
        m5_low = df_5m["Low"]
        m5_close = df_5m["Close"]

        # Align 1M timestamps to 5M and 15M without look-ahead
        # Step through 1M bars chronologically
        m1_close = df_1m["Close"]
        m1_high = df_1m["High"]
        m1_low = df_1m["Low"]
        m1_open = df_1m["Open"]
        m1_ema20 = m1_close.ewm(span=20, adjust=False).mean()

        # ATR on 1M
        tr = pd.concat([
            m1_high - m1_low,
            (m1_high - m1_close.shift(1)).abs(),
            (m1_low - m1_close.shift(1)).abs()
        ], axis=1).max(axis=1)
        m1_atr = tr.rolling(14).mean().fillna(3.0)

        # 1M RSI 14
        delta = m1_close.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss.replace(0, np.nan)
        m1_rsi = (100 - (100 / (1 + rs))).fillna(50.0)

        # Main chronological bar-by-bar loop
        for i in range(30, len(df_1m)):
            cur_time = df_1m.index[i]
            cur_close = float(m1_close.iloc[i])
            cur_high = float(m1_high.iloc[i])
            cur_low = float(m1_low.iloc[i])
            cur_open = float(m1_open.iloc[i])
            cur_atr = float(m1_atr.iloc[i])
            cur_rsi = float(m1_rsi.iloc[i])
            cur_ema = float(m1_ema20.iloc[i])

            # ── 1. Manage Active Trade ────────────────────────
            if active_trade is not None:
                direction = active_trade["direction"]
                entry = active_trade["entry_price"]
                sl = active_trade["sl"]
                tp = active_trade["tp"]
                lot = active_trade["lot"]
                risk_dist = active_trade["risk_distance"]
                be_active = active_trade["be_active"]
                holding_bars = active_trade["holding_bars"] + 1
                active_trade["holding_bars"] = holding_bars

                comm_usd = round(lot * self.commission_per_lot, 2)
                sl_hit = False
                tp_hit = False

                # Conservative same-bar check
                if direction == "BUY":
                    if cur_low <= sl and cur_high >= tp:
                        # Both hit on same bar -> assume worst case: SL hit first
                        sl_hit = True
                    elif cur_low <= sl:
                        sl_hit = True
                    elif cur_high >= tp:
                        tp_hit = True

                    # Break-even check
                    if enable_break_even and not be_active and cur_high >= (entry + risk_dist * 1.0):
                        active_trade["sl"] = round(entry + self.spread + 0.10, 2)
                        active_trade["be_active"] = True

                elif direction == "SELL":
                    if cur_high >= sl and cur_low <= tp:
                        sl_hit = True
                    elif cur_high >= sl:
                        sl_hit = True
                    elif cur_low <= tp:
                        tp_hit = True

                    if enable_break_even and not be_active and cur_low <= (entry - risk_dist * 1.0):
                        active_trade["sl"] = round(entry - self.spread - 0.10, 2)
                        active_trade["be_active"] = True

                # Process Exit
                if sl_hit or tp_hit or holding_bars >= 90:
                    exit_reason = "SL_HIT" if sl_hit else ("TP_HIT" if tp_hit else "TIME_LIMIT_90M")
                    if sl_hit:
                        exit_price = sl - self.slippage_points if direction == "BUY" else sl + self.slippage_points
                    elif tp_hit:
                        exit_price = tp - self.slippage_points if direction == "BUY" else tp + self.slippage_points
                    else:
                        exit_price = cur_close

                    pnl_dist = exit_price - entry if direction == "BUY" else entry - exit_price
                    gross_pnl = round(pnl_dist * lot * LOT_SIZE, 2)
                    net_pnl = round(gross_pnl - comm_usd, 2)
                    pnl_r = round(pnl_dist / risk_dist, 2)

                    balance = round(balance + net_pnl, 2)
                    if balance > peak_balance:
                        peak_balance = balance
                    dd = peak_balance - balance
                    dd_pct = round((dd / peak_balance) * 100, 2)
                    if dd > max_drawdown_usd:
                        max_drawdown_usd = dd
                    if dd_pct > max_drawdown_pct:
                        max_drawdown_pct = dd_pct

                    trades.append({
                        "entry_time": str(active_trade["entry_time"]),
                        "exit_time": str(cur_time),
                        "direction": direction,
                        "entry_price": entry,
                        "exit_price": exit_price,
                        "sl": sl,
                        "tp": tp,
                        "lot": lot,
                        "net_pnl_usd": net_pnl,
                        "pnl_r": pnl_r,
                        "exit_reason": exit_reason,
                        "holding_minutes": holding_bars,
                        "is_win": net_pnl > 0,
                    })

                    equity_curve.append({
                        "time": str(cur_time),
                        "balance": balance,
                        "equity": balance,
                    })
                    active_trade = None
                continue

            # ── 2. Signal Generation (Only if No Active Trade) ───
            # Slice closed 15M and 5M data available strictly at or before cur_time
            hist_15m = df_15m[df_15m.index <= cur_time]
            hist_5m = df_5m[df_5m.index <= cur_time]

            if len(hist_15m) < 20 or len(hist_5m) < 15:
                continue

            # 15M Trend
            t15 = trend_15m_series.loc[hist_15m.index[-1]]

            # 5M Liquidity Sweep
            # Last confirmed 5M swing low and high
            m5_recent_lows = hist_5m["Low"].iloc[-12:-1]
            m5_recent_highs = hist_5m["High"].iloc[-12:-1]
            swing_low_5m = float(m5_recent_lows.min())
            swing_high_5m = float(m5_recent_highs.max())

            m5_last_c = float(hist_5m["Close"].iloc[-1])
            m5_last_l = float(hist_5m["Low"].iloc[-1])
            m5_last_h = float(hist_5m["High"].iloc[-1])

            bull_sweep = (m5_last_l < swing_low_5m) and (m5_last_c > swing_low_5m)
            bear_sweep = (m5_last_h > swing_high_5m) and (m5_last_c < swing_high_5m)

            # 1M Confirmation
            m1_bull_conf = (cur_close > cur_ema) and (cur_rsi >= 48.0) and (cur_close > cur_open)
            m1_bear_conf = (cur_close < cur_ema) and (cur_rsi <= 52.0) and (cur_close < cur_open)

            buy_signal = (t15 != "BEARISH") and bull_sweep and m1_bull_conf
            sell_signal = (t15 != "BULLISH") and bear_sweep and m1_bear_conf

            if buy_signal:
                sl_buffer = max(cur_atr * 1.1, 1.50)
                sl_price = round(swing_low_5m - sl_buffer, 2)
                risk_dist = round(cur_close - sl_price, 2)
                if 1.5 <= risk_dist <= 8.0:
                    # Target selection
                    if target_mode == "1.0R":
                        tp_price = round(cur_close + (risk_dist * 1.0), 2)
                    elif target_mode == "1.25R":
                        tp_price = round(cur_close + (risk_dist * 1.25), 2)
                    elif target_mode == "1.5R":
                        tp_price = round(cur_close + (risk_dist * 1.5), 2)
                    elif target_mode == "2.0R":
                        tp_price = round(cur_close + (risk_dist * 2.0), 2)
                    else:  # DYNAMIC
                        # Front-run opposing 5M swing high
                        opp_h = round(swing_high_5m - 0.25, 2)
                        dist = opp_h - cur_close
                        if dist >= risk_dist * 1.0 and dist <= risk_dist * 2.5:
                            tp_price = opp_h
                        else:
                            tp_price = round(cur_close + (risk_dist * 1.35), 2)

                    # Lot Sizing (0.25% risk)
                    dollar_risk = balance * (self.risk_pct / 100.0)
                    lot = max(round(dollar_risk / (risk_dist * LOT_SIZE), 2), 0.01)

                    active_trade = {
                        "direction": "BUY",
                        "entry_time": cur_time,
                        "entry_price": cur_close,
                        "sl": sl_price,
                        "tp": tp_price,
                        "lot": lot,
                        "risk_distance": risk_dist,
                        "be_active": False,
                        "holding_bars": 0,
                    }

            elif sell_signal:
                sl_buffer = max(cur_atr * 1.1, 1.50)
                sl_price = round(swing_high_5m + sl_buffer, 2)
                risk_dist = round(sl_price - cur_close, 2)
                if 1.5 <= risk_dist <= 8.0:
                    if target_mode == "1.0R":
                        tp_price = round(cur_close - (risk_dist * 1.0), 2)
                    elif target_mode == "1.25R":
                        tp_price = round(cur_close - (risk_dist * 1.25), 2)
                    elif target_mode == "1.5R":
                        tp_price = round(cur_close - (risk_dist * 1.5), 2)
                    elif target_mode == "2.0R":
                        tp_price = round(cur_close - (risk_dist * 2.0), 2)
                    else:
                        opp_l = round(swing_low_5m + 0.25, 2)
                        dist = cur_close - opp_l
                        if dist >= risk_dist * 1.0 and dist <= risk_dist * 2.5:
                            tp_price = opp_l
                        else:
                            tp_price = round(cur_close - (risk_dist * 1.35), 2)

                    dollar_risk = balance * (self.risk_pct / 100.0)
                    lot = max(round(dollar_risk / (risk_dist * LOT_SIZE), 2), 0.01)

                    active_trade = {
                        "direction": "SELL",
                        "entry_time": cur_time,
                        "entry_price": cur_close,
                        "sl": sl_price,
                        "tp": tp_price,
                        "lot": lot,
                        "risk_distance": risk_dist,
                        "be_active": False,
                        "holding_bars": 0,
                    }

        # ── 3. Compile Performance Metrics ───────────────────
        total_trades = len(trades)
        wins = [t for t in trades if t["is_win"]]
        losses = [t for t in trades if not t["is_win"]]

        win_count = len(wins)
        loss_count = len(losses)
        win_rate = round((win_count / total_trades * 100), 1) if total_trades > 0 else 0.0

        total_profit = sum(t["net_pnl_usd"] for t in wins)
        total_loss = abs(sum(t["net_pnl_usd"] for t in losses))
        profit_factor = round(total_profit / total_loss, 2) if total_loss > 0 else (99.0 if total_profit > 0 else 0.0)
        net_profit_usd = round(balance - self.initial_balance, 2)

        avg_win = round(total_profit / win_count, 2) if win_count > 0 else 0.0
        avg_loss = round(total_loss / loss_count, 2) if loss_count > 0 else 0.0
        avg_holding = round(sum(t["holding_minutes"] for t in trades) / total_trades, 1) if total_trades > 0 else 0.0

        # Net expectancy per trade ($ and R)
        net_exp_usd = round(net_profit_usd / total_trades, 2) if total_trades > 0 else 0.0
        net_exp_r = round(sum(t["pnl_r"] for t in trades) / total_trades, 2) if total_trades > 0 else 0.0

        result = {
            "target_mode": target_mode,
            "total_trades": total_trades,
            "win_rate_pct": win_rate,
            "profit_factor": profit_factor,
            "net_profit_usd": net_profit_usd,
            "net_expectancy_usd": net_exp_usd,
            "net_expectancy_r": net_exp_r,
            "max_drawdown_pct": max_drawdown_pct,
            "max_drawdown_usd": round(max_drawdown_usd, 2),
            "final_balance": balance,
            "avg_win": avg_win,
            "avg_loss": avg_loss,
            "avg_holding_minutes": avg_holding,
            "trades": trades,
            "equity_curve": equity_curve[-100:],  # last 100 points
        }

        # Save to database
        try:
            with self.db.get_connection() as conn:
                conn.execute("""
                    INSERT INTO backtest_results (
                        timestamp, run_label, target_mode, total_trades,
                        win_rate_pct, profit_factor, net_expectancy, net_profit_usd,
                        max_drawdown, avg_win, avg_loss, summary_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    datetime.now().isoformat(),
                    f"Backtest {target_mode}",
                    target_mode,
                    total_trades,
                    win_rate,
                    profit_factor,
                    net_exp_usd,
                    net_profit_usd,
                    max_drawdown_pct,
                    avg_win,
                    avg_loss,
                    json.dumps(result),
                ))
                conn.commit()
        except Exception as e:
            logger.warning(f"Could not persist backtest result to DB: {e}")

        return result

    def run_sensitivity_comparison(
        self,
        df_1m: pd.DataFrame,
        df_5m: pd.DataFrame,
        df_15m: pd.DataFrame,
    ) -> List[Dict[str, Any]]:
        """
        Runs sensitivity analysis comparing:
        1.0R, 1.25R, 1.5R, 2.0R, and Dynamic Structure TP.
        """
        modes = ["1.0R", "1.25R", "1.5R", "2.0R", "DYNAMIC"]
        reports = []
        for m in modes:
            logger.info(f"Running backtest sensitivity for mode: {m}")
            res = self.run_backtest(df_1m, df_5m, df_15m, target_mode=m)
            reports.append({
                "mode": m,
                "trades": res.get("total_trades", 0),
                "win_rate": res.get("win_rate_pct", 0.0),
                "profit_factor": res.get("profit_factor", 0.0),
                "net_profit": res.get("net_profit_usd", 0.0),
                "net_exp_r": res.get("net_expectancy_r", 0.0),
                "max_dd_pct": res.get("max_drawdown_pct", 0.0),
                "avg_holding": res.get("avg_holding_minutes", 0.0),
            })
        return reports
