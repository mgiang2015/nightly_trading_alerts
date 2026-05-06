"""
signals/trend_filtered_daily_return.py — Daily Return mean reversion with
a trend filter to avoid fighting sustained downtrends.

Problem with plain Daily Return
--------------------------------
The base DailyReturnStrategy bets on mean reversion unconditionally — it
longs yesterday's biggest losers regardless of whether that stock is in a
downtrend. A stock can be the biggest loser for three months in a row and
the strategy will keep trying to buy the dip, resulting in catching falling
knives.

Solution: trend filter via N-day moving average
------------------------------------------------
Only issue a BUY signal if the stock's close is above its N-day simple
moving average at the time of the signal. This ensures we're longing
short-term weakness within a broader uptrend — a genuine mean reversion
setup — rather than trying to bottom-pick a deteriorating stock.

SELL signals are issued for the top-N winners unconditionally (they may
be due for profit-taking regardless of trend direction).

Parameters
----------
top_n        : same as DailyReturnStrategy — how many stocks to flag
trend_window : SMA lookback in days (default 50). A close above the 50-day
               SMA confirms an uptrend. Typical values: 20 (shorter, more
               signals), 50 (balanced), 100 (stricter).
"""

import pandas as pd
from config import CROSS_TOPN
from signals.base_cross import BaseCrossStrategy


class TrendFilteredDailyReturnStrategy(BaseCrossStrategy):
    """
    Cross-sectional Daily Return mean reversion with SMA trend filter.

    BUY  — ticker is in the bottom-N by daily return AND close > SMA(trend_window)
    SELL — ticker is in the top-N by daily return (no trend filter on exits)
    HOLD — all others, or bottom-N tickers that fail the trend filter
    """

    def __init__(self, top_n: int = CROSS_TOPN, trend_window: int = 50):
        self.top_n        = top_n
        self.trend_window = trend_window

    @property
    def name(self) -> str:
        return (
            f"Daily Return mean reversion + SMA{self.trend_window} trend filter "
            f"(top/bottom {self.top_n})"
        )

    def _in_uptrend(self, df: pd.DataFrame) -> bool:
        """
        Return True if the most recent close is above the trend_window SMA.
        Returns False if there is insufficient history for the SMA.
        """
        if len(df) < self.trend_window:
            return False
        sma   = df["close"].iloc[-self.trend_window:].mean()
        close = df["close"].iloc[-1]
        return bool(close > sma)

    def compute_all(self, data: dict[str, pd.DataFrame]) -> list[dict]:
        # ── Daily return scores ───────────────────────────────────────────────
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

        valid   = {t: v for t, v in scores.items() if v is not None}
        invalid = {t for t, v in scores.items() if v is None}

        ranked   = sorted(valid.items(), key=lambda x: x[1])
        sell_set = {t for t, _ in ranked[-self.top_n:]}

        # Bottom-N candidates — only promote to BUY if in uptrend
        buy_candidates = [t for t, _ in ranked[:self.top_n]]
        buy_set = {t for t in buy_candidates if self._in_uptrend(data[t])}
        # Tickers that failed the trend filter are explicitly tracked
        trend_blocked = {t for t in buy_candidates if t not in buy_set}

        results = []
        for ticker, dr in ranked:
            curr_close = data[ticker]["close"].iloc[-1]
            date       = data[ticker].index[-1]

            if ticker in buy_set:
                signal = "BUY"
            elif ticker in sell_set:
                signal = "SELL"
            else:
                signal = "HOLD"

            detail = f"DR={dr*100:+.3f}%  close={curr_close:.3f}  ({date})"
            if ticker in trend_blocked:
                sma = data[ticker]["close"].iloc[-self.trend_window:].mean()
                detail += f"  [trend filter: close {curr_close:.3f} < SMA{self.trend_window} {sma:.3f}]"

            results.append({
                "ticker":       ticker,
                "signal":       signal,
                "close":        round(curr_close, 4),
                "daily_return": round(dr * 100, 4),
                "detail":       detail,
            })

        for ticker in invalid:
            results.append({
                "ticker": ticker,
                "signal": "ERROR",
                "detail": "Insufficient data for daily return calculation",
            })

        return results