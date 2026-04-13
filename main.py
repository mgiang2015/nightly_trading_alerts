"""
main.py — Nightly trading signal pipeline.
Run directly or via cron: python main.py
"""

import logging
from datetime import datetime
from data.fetcher import fetch_all
from signals.engine import compute_signals
from alerts.telegram_bot import send_summary

logging.basicConfig(
    filename="logs/pipeline.log",
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)
log = logging.getLogger(__name__)


TICKERS = [
    "ES3.SI",   # STI ETF
    "D05.SI",   # DBS
    "O39.SI",   # OCBC
    "U11.SI",   # UOB
    # Add more SGX (.SI) or US tickers here
]


def run():
    log.info("=== Pipeline started ===")
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Fetching data...")

    # 1. Fetch & store
    data = fetch_all(TICKERS)

    # 2. Compute signals
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Computing signals...")
    signals = compute_signals(data)

    # 3. Send Telegram alert
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Sending alert...")
    send_summary(signals)

    log.info("=== Pipeline complete ===")
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Done.")


if __name__ == "__main__":
    run()
