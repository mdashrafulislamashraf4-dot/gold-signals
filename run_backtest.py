"""
============================================================
  run_backtest.py
  CLI Backtesting Runner & Performance Evaluation for XAUUSD
  Commander A Specification:
    - Multi-timeframe M15/M5/M1 historical testing
    - Realistic spread ($0.25), commission ($4/lot), slippage ($0.05)
    - Expectancy, profit factor, drawdown, consecutive losses
    - Rigorous evaluation of 10 wins vs 4 losses under actual costs
  Usage: python run_backtest.py
============================================================
"""

import sys
import logging
from modules.market_data import MarketDataFetcher
from modules.backtest_engine import BacktestEngine

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("backtest")


def main():
    print("=" * 80)
    print("  🏆 GOLD QUICKSCALP AI — PERFORMANCE EVALUATION & EXPECTANCY ANALYSIS")
    print("=" * 80)

    md = MarketDataFetcher()
    logger.info("Ingesting multi-timeframe historical data (M15, M5, M1) for XAUUSD...")

    df_15m = md.get_ohlcv("15m", bars=250)
    df_5m  = md.get_ohlcv("5m", bars=500)
    df_1m  = md.get_ohlcv("1m", bars=1500)

    if df_1m is None or len(df_1m) < 60:
        logger.error("Could not fetch sufficient historical data. Verify network connectivity.")
        sys.exit(1)

    logger.info(f"Historical Data Loaded: M15 ({len(df_15m)} bars), M5 ({len(df_5m)} bars), M1 ({len(df_1m)} bars)")

    engine = BacktestEngine(
        spread=0.25,
        commission_per_lot=4.0,
        slippage_points=0.05,
        initial_balance=10000.0,
        risk_pct=0.25,
    )

    print("\nRunning Dynamic Structural Target Backtest...")
    dynamic_report = engine.run_backtest(df_1m, df_5m, df_15m, target_mode="DYNAMIC")

    print("\n" + "=" * 80)
    print("  📊 BACKTEST PERFORMANCE SUMMARY (DYNAMIC ADAPTIVE TARGETS)")
    print("=" * 80)
    trades = dynamic_report.get("trades", [])
    total_trades = len(trades)
    win_rate = dynamic_report.get("win_rate_pct", 0.0)
    pf = dynamic_report.get("profit_factor", 0.0)
    net_profit = dynamic_report.get("net_profit_usd", 0.0)
    max_dd_pct = dynamic_report.get("max_drawdown_pct", 0.0)
    avg_win = dynamic_report.get("avg_win", 0.0)
    avg_loss = dynamic_report.get("avg_loss", 0.0)
    net_exp_usd = dynamic_report.get("net_expectancy_usd", 0.0)
    net_exp_r = dynamic_report.get("net_expectancy_r", 0.0)

    # Compute consecutive loss distribution
    max_consec_losses = 0
    cur_consec_losses = 0
    for t in trades:
        if not t.get("is_win"):
            cur_consec_losses += 1
            max_consec_losses = max(max_consec_losses, cur_consec_losses)
        else:
            cur_consec_losses = 0

    print(f"Total Trades Analyzed:      {total_trades}")
    print(f"Win Rate:                   {win_rate}%")
    print(f"Profit Factor:              {pf}")
    print(f"Net Profit:                 ${net_profit:+.2f}")
    print(f"Average Net Win:            ${avg_win:.2f}")
    print(f"Average Net Loss:           ${avg_loss:.2f}")
    print(f"Net Expectancy per Trade:   ${net_exp_usd:+.2f} ({net_exp_r:+.2f}R)")
    print(f"Maximum Drawdown:           {max_dd_pct:.2f}%")
    print(f"Max Consecutive Losses:     {max_consec_losses}")

    # ─────────────────────────────────────────────────────────
    # Mathematical Evaluation: 10 Wins vs 4 Losses Scenario
    # ─────────────────────────────────────────────────────────
    print("\n" + "-" * 80)
    print("  ⚖️ EXPECTANCY EVALUATION: 10 WINS vs 4 LOSSES SCENARIO")
    print("-" * 80)
    if avg_win > 0 or avg_loss > 0:
        sim_wins_gross = 10 * avg_win
        sim_losses_gross = 4 * avg_loss
        sim_net = sim_wins_gross - sim_losses_gross
        is_profitable = sim_net > 0

        print(f"10 Winning Trades Net Gain:  +${sim_wins_gross:.2f}")
        print(f" 4 Losing Trades Net Loss:   -${sim_losses_gross:.2f}")
        print(f"Net Expected Balance Delta:  {'+$' if is_profitable else '-$'}{abs(sim_net):.2f}")
        print(f"Outcome Evaluation:          {'✅ PROFITABLE' if is_profitable else '❌ UNPROFITABLE'}")
        if is_profitable:
            print(f"Conclusion: Net expectancy remains positive after real spread, commission, and slippage.")
        else:
            print(f"Conclusion: Loss magnitude or friction exceeds gains; risk-to-reward adjustment recommended.")
    else:
        print("Insufficient historical trades in test window to compute 10W / 4L simulation.")

    # ─────────────────────────────────────────────────────────
    # Sensitivity Comparison across Target Modes
    # ─────────────────────────────────────────────────────────
    print("\n" + "=" * 80)
    print("  🔍 SENSITIVITY COMPARISON (FIXED R:R vs DYNAMIC STRUCTURAL)")
    print("=" * 80)
    comparison = engine.run_sensitivity_comparison(df_1m, df_5m, df_15m)

    print(f"{'Target Mode':<12} | {'Trades':<8} | {'Win Rate':<10} | {'Profit Factor':<14} | {'Net PnL ($)':<12} | {'Max DD':<10}")
    print("-" * 80)
    for row in comparison:
        print(
            f"{row['mode']:<12} | {row['trades']:<8} | {row['win_rate']:<9}% | "
            f"{row['profit_factor']:<14.2f} | ${row['net_profit']:<+11.2f} | {row['max_dd_pct']:<9.2f}%"
        )
    print("=" * 80)
    print("DISCLAIMER: Backtested performance includes $0.25 spread, $4/lot commission, and $0.05 slippage.")
    print("No system guarantees future profits. Trade strictly within permitted risk parameters.\n")


if __name__ == "__main__":
    main()
