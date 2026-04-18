"""
signals/engine.py — Pipeline runner.

Runs a strategy across all tickers and returns sorted results.
Strategies live in their own modules; import them from signals/ directly.
"""

import logging
import pandas as pd
from signals.base import BaseStrategy
from signals.ema_cross import EMACrossStrategy

log = logging.getLogger(__name__)


def compute_signals(
    data: dict[str, pd.DataFrame],
    strategy: BaseStrategy | None = None,
) -> tuple[list[dict], str]:
    """
    Run the strategy on every ticker.
    Returns (results, strategy_name) where results are sorted by signal
    priority (BUY/SELL first) and strategy_name is used in the alert footer.
    """
    if strategy is None:
        strategy = EMACrossStrategy()

    results = []
    for ticker, df in data.items():
        try:
            result = strategy.compute(df)
            result["ticker"] = ticker
            results.append(result)
            log.info(f"{ticker}: {result['signal']}")
        except Exception as e:
            log.error(f"Signal computation failed for {ticker}: {e}")
            results.append({"ticker": ticker, "signal": "ERROR", "detail": str(e)})

    # Sort: BUY → SELL → HOLD → ERROR
    priority = {"BUY": 0, "SELL": 1, "HOLD": 2, "ERROR": 3}
    results.sort(key=lambda r: priority.get(r["signal"], 9))
    return results, strategy.name