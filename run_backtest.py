"""
run_backtest.py — Entry point for running backtests.

Usage:
    python run_backtest.py

Edit the configuration block below to test different strategies and settings.
Run twice with commission_fsmone and commission_zero to see the fee impact.
"""

import os
import sys

from tickers import WATCHLIST

from data.fetcher import fetch_for_backtest
from signals import (
    DailyReturnStrategy,
    EMACrossStrategy,
    VolumeBreakoutStrategy,
    RSIDivergenceStrategy,
)
from backtest.backtester import (
    run_backtest,
    print_summary,
    commission_fsmone,
    commission_zero,
)

# ── Configuration ─────────────────────────────────────────────────────────────

# Strategy to backtest
STRATEGY = DailyReturnStrategy(top_n=3)

# Tickers — defaults to full STI watchlist from .env
TICKERS = WATCHLIST

# Data period — "5y" for 5 years, "max" for full history
PERIOD = "1y"

# Starting capital in SGD
INITIAL_CAPITAL = 10_000.0

# Warmup bars before first trade
WARMUP_BARS = 60

# Commission function
COMMISSION = commission_fsmone

# Rebalance frequency:
#   1 = daily   — re-evaluate signals every trading day
#   5 = weekly  — re-evaluate every 5 trading days (~Monday)
#  21 = monthly — re-evaluate every ~21 trading days
REBALANCE_EVERY = 1

# ── Run ───────────────────────────────────────────────────────────────────────

def main():
    print(f"\nStrategy   : {STRATEGY.name}")
    print(f"Tickers    : {len(TICKERS)} stocks")
    print(f"Period     : {PERIOD}")
    print(f"Capital    : SGD {INITIAL_CAPITAL:,.0f}")
    print(f"Commission : {'FSMOne (0.08%, min SGD 8.80)' if COMMISSION is commission_fsmone else 'None'}")
    print(f"Rebalance  : every {REBALANCE_EVERY} trading day(s)\n")

    data = fetch_for_backtest(TICKERS, period=PERIOD)
    if not data:
        print("ERROR: No data fetched. Check your internet connection and tickers.")
        sys.exit(1)

    print(f"\nRunning backtest...")
    result = run_backtest(
        data=data,
        strategy=STRATEGY,
        initial_capital=INITIAL_CAPITAL,
        warmup_bars=WARMUP_BARS,
        commission_fn=COMMISSION,
        rebalance_every=REBALANCE_EVERY,
    )

    print_summary(result, strategy_name=STRATEGY.name)

    os.makedirs("backtest/results", exist_ok=True)
    safe_name = (
        STRATEGY.name
        .replace(" ", "_").replace("/", "-")
        .replace("(", "").replace(")", "")
    )
    freq_tag = f"_rebal{REBALANCE_EVERY}d"

    equity_path = f"backtest/results/{safe_name}{freq_tag}_equity.csv"
    result["equity_curve"].to_csv(equity_path, header=True)
    print(f"Equity curve saved → {equity_path}")

    if not result["trades"].empty:
        trades_path = f"backtest/results/{safe_name}{freq_tag}_trades.csv"
        result["trades"].to_csv(trades_path, index=False)
        print(f"Trades saved       → {trades_path}")


if __name__ == "__main__":
    main()