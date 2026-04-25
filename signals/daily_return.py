"""
signals/daily_return.py — Cross-sectional Daily Return (DR) mean reversion.

Based on: "Systematic Multi-Factor Trading Strategy Based on SGX Market"
          Cen Yu, NTU FYP 2023 — best Sharpe 4.675 with hedge + vol targeting.

Rationale
---------
SGX behaves as a mean-reverting market. Stocks that underperformed yesterday
(low daily return) tend to recover; stocks that outperformed tend to revert.
This strategy ranks all tickers by their most recent 1-day return and:
  - Flags the bottom-N (biggest losers)  → BUY  (mean reversion long)
  - Flags the top-N    (biggest winners) → SELL  (mean reversion short / avoid)
  - All others                           → HOLD

Note: since this is a long-only personal account, SELL signals indicate
stocks to reduce exposure to or avoid, not to short.
"""

import pandas as pd

from config import CROSS_TOPN
from signals.base_cross import BaseCrossStrategy


class DailyReturnStrategy(BaseCrossStrategy):
    """
    Cross-sectional mean reversion on 1-day return.

    Parameters
    ----------
    top_n : number of top and bottom ranked tickers to flag (default: CROSS_TOPN)
    """

    def __init__(self, top_n: int = CROSS_TOPN):
        self.top_n = top_n

    @property
    def name(self) -> str:
        return f"Daily Return mean reversion (top/bottom {self.top_n})"

    def compute_all(self, data: dict[str, pd.DataFrame]) -> list[dict]:
        scores = {}
        for ticker, df in data.items():
            if len(df) < 2:
                scores[ticker] = None
                continue
            prev_close = df["close"].iloc[-2]
            curr_close = df["close"].iloc[-1]
            if prev_close <= 0:
                scores[ticker] = None
                continue
            scores[ticker] = (curr_close - prev_close) / prev_close

        # Separate valid and invalid tickers
        valid   = {t: v for t, v in scores.items() if v is not None}
        invalid = {t for t, v in scores.items() if v is None}

        # Rank by daily return (ascending: lowest return = rank 1 = BUY candidate)
        ranked = sorted(valid.items(), key=lambda x: x[1])

        buy_set  = {t for t, _ in ranked[:self.top_n]}
        sell_set = {t for t, _ in ranked[-self.top_n:]}

        results = []

        for ticker, dr in ranked:
            if ticker in buy_set:
                signal = "BUY"
            elif ticker in sell_set:
                signal = "SELL"
            else:
                signal = "HOLD"

            curr_close = data[ticker]["close"].iloc[-1]
            date       = data[ticker].index[-1]
            results.append({
                "ticker":       ticker,
                "signal":       signal,
                "close":        round(curr_close, 4),
                "daily_return": round(dr * 100, 4),   # store as %
                "detail": (
                    f"DR={dr*100:+.3f}%  "
                    f"close={curr_close:.3f}  ({date})"
                ),
            })

        # Tickers with insufficient data
        for ticker in invalid:
            results.append({
                "ticker": ticker,
                "signal": "ERROR",
                "detail": "Insufficient data for daily return calculation",
            })

        return results
