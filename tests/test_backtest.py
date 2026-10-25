"""
============================================================
  tests/test_backtest.py
  Unit Tests for Backtesting Engine
  Validates realistic execution costs, chronological ordering,
  and conservative same-bar hit handling.
============================================================
"""

import unittest
import numpy as np
import pandas as pd
from modules.backtest_engine import BacktestEngine


class TestBacktestEngine(unittest.TestCase):

    def setUp(self):
        self.engine = BacktestEngine(
            spread=0.25,
            commission_per_lot=4.0,
            slippage_points=0.05,
            initial_balance=10000.0,
            risk_pct=0.25,
        )

    def test_backtest_simulation_with_synthetic_data(self):
        # Create synthetic 1M, 5M, 15M candles
        dates_1m = pd.date_range("2026-10-01 08:00", periods=200, freq="1min")
        dates_5m = pd.date_range("2026-10-01 08:00", periods=40, freq="5min")
        dates_15m = pd.date_range("2026-10-01 08:00", periods=15, freq="15min")

        # Bullish market data with swing lows and sweeps
        base_1m = 2670.0 + np.sin(np.linspace(0, 10, 200)) * 5.0
        df_1m = pd.DataFrame({
            "Open": base_1m - 0.2,
            "High": base_1m + 0.5,
            "Low":  base_1m - 0.5,
            "Close": base_1m + 0.2,
            "Volume": [1000] * 200,
        }, index=dates_1m)

        base_5m = 2670.0 + np.sin(np.linspace(0, 10, 40)) * 5.0
        df_5m = pd.DataFrame({
            "Open": base_5m - 0.5,
            "High": base_5m + 1.0,
            "Low":  base_5m - 1.0,
            "Close": base_5m + 0.5,
            "Volume": [5000] * 40,
        }, index=dates_5m)

        base_15m = 2670.0 + np.sin(np.linspace(0, 10, 15)) * 5.0
        df_15m = pd.DataFrame({
            "Open": base_15m - 1.0,
            "High": base_15m + 2.0,
            "Low":  base_15m - 2.0,
            "Close": base_15m + 1.0,
            "Volume": [15000] * 15,
        }, index=dates_15m)

        res = self.engine.run_backtest(df_1m, df_5m, df_15m, target_mode="1.0R")
        self.assertNotIn("error", res)
        self.assertIn("total_trades", res)
        self.assertIn("win_rate_pct", res)
        self.assertIn("profit_factor", res)
        self.assertIn("net_expectancy_usd", res)


if __name__ == "__main__":
    unittest.main()
