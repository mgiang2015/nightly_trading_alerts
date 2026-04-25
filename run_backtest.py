"""
run_backtest.py — Entry point for running backtests.

Usage:
    python run_backtest.py

Edit the STRATEGY and TICKERS variables below to test different strategies.
Results are printed to stdout. The equity curve is saved to backtest/results/.
"""

import os
import sys

from backtest.backtester import print_summary, run_backtest
from data.fetcher import fetch_for_backtest
from signals import (
    DailyReturnStrategy,
)

# Load watchlist from env
from tickers import WATCHLIST

# ── Configuration ─────────────────────────────────────────────────────────────

# Strategy to backtest — swap to any strategy instance
STRATEGY = DailyReturnStrategy(top_n=3)

# Tickers — defaults to full STI watchlist from .env
# Override here if you want to test on a subset, e.g.:
# TICKERS = ["D05.SI", "O39.SI", "U11.SI"]
TICKERS = WATCHLIST

# Data period — "5y" for 5 years, "max" for full history
PERIOD = "10y"

# Starting capital in SGD
INITIAL_CAPITAL = 10_000.0

# Warmup bars before first trade (ensures indicators have enough history)
WARMUP_BARS = 60

# ── Run ───────────────────────────────────────────────────────────────────────

def main():
    print(f"\nStrategy : {STRATEGY.name}")
    print(f"Tickers  : {len(TICKERS)} stocks")
    print(f"Period   : {PERIOD}")
    print(f"Capital  : SGD {INITIAL_CAPITAL:,.0f}\n")

    # 1. Fetch historical data
    data = fetch_for_backtest(TICKERS, period=PERIOD)
    if not data:
        print("ERROR: No data fetched. Check your internet connection and tickers.")
        sys.exit(1)

    # 2. Run backtest
    print("\nRunning backtest...")
    result = run_backtest(
        data=data,
        strategy=STRATEGY,
        initial_capital=INITIAL_CAPITAL,
        warmup_bars=WARMUP_BARS,
    )

    # 3. Print summary
    print_summary(result, strategy_name=STRATEGY.name)

    # 4. Save results
    os.makedirs("backtest/results", exist_ok=True)
    safe_name = STRATEGY.name.replace(" ", "_").replace("/", "-").replace("(", "").replace(")", "")

    equity_path = f"backtest/results/{safe_name}_equity.csv"
    result["equity_curve"].to_csv(equity_path, header=True)
    print(f"Equity curve saved → {equity_path}")

    if not result["trades"].empty:
        trades_path = f"backtest/results/{safe_name}_trades.csv"
        result["trades"].to_csv(trades_path, index=False)
        print(f"Trades saved       → {trades_path}")


if __name__ == "__main__":
    main()