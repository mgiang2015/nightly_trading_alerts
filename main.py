"""
main.py — Nightly trading signal pipeline.
Run directly or via cron: python main.py

Two data intervals are fetched:
  - 30m : used by intraday strategies (EMA cross, RSI divergence, volume breakout)
  - 1d  : used by cross-sectional daily strategies (Daily Return, KCP, Williams %R)

Add or swap strategies in the STRATEGIES list below.
Each entry is (strategy_instance, interval) — the pipeline will automatically
use the correct dataset for each strategy.
"""

import logging
from datetime import datetime

from data.fetcher import fetch_all
from signals import (
    compute_signals,
    DailyReturnStrategy,
)
from signals.fundamental_filter import annotate_signals
from alerts import send_summary
from tickers import WATCHLIST

logging.basicConfig(
    filename="logs/pipeline.log",
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)
log = logging.getLogger(__name__)


# ── Active strategies ─────────────────────────────────────────────────────────
# Each entry: (strategy_instance, data_interval)
#   interval "30m" → intraday candles (EMA cross, RSI divergence, volume breakout)
#   interval "1d"  → daily candles    (Daily Return, KCP, Williams %R)

STRATEGIES = [
    (DailyReturnStrategy(), "1d"),
]


def run():
    log.info("=== Pipeline started ===")

    # 1. Determine which intervals are needed and fetch once per interval
    needed_intervals = {interval for _, interval in STRATEGIES}

    print(f"[{datetime.now().strftime('%H:%M:%S')}] Fetching data "
          f"({', '.join(sorted(needed_intervals))})...")

    data_by_interval: dict[str, dict] = {}
    for interval in needed_intervals:
        data_by_interval[interval] = fetch_all(WATCHLIST, interval=interval)

    # 2. Run each strategy against the correct dataset
    all_results   = []
    strategy_names = []

    for strategy, interval in STRATEGIES:
        print(f"[{datetime.now().strftime('%H:%M:%S')}] "
              f"Computing signals: {strategy.name}...")
        data = data_by_interval[interval]
        results, name = compute_signals(data, strategy=strategy)
        all_results.append((results, name))
        strategy_names.append(name)

    # 3. Annotate with fundamental quality flags
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Fetching fundamentals...")
    all_results = [
        (annotate_signals(results), name)
        for results, name in all_results
    ]

    # 4. Send one Telegram alert per strategy
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Sending alerts...")
    for results, name in all_results:
        send_summary(results, name)

    log.info("=== Pipeline complete ===")
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Done.")


if __name__ == "__main__":
    run()