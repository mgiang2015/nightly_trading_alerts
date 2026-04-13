"""
signals/engine.py — Strategy base class + EMA crossover implementation.

To add a new strategy later (e.g. ML model):
    class MyMLStrategy(BaseStrategy):
        def compute(self, df: pd.DataFrame) -> dict:
            ...

Then swap it in compute_signals() below.
"""

from abc import ABC, abstractmethod
import logging
import pandas as pd
import pandas_ta as ta
from config import EMA_FAST, EMA_SLOW

log = logging.getLogger(__name__)


# ── Base interface ─────────────────────────────────────────────────────────────

class BaseStrategy(ABC):
    @abstractmethod
    def compute(self, df: pd.DataFrame) -> dict:
        """
        Accept a DataFrame with columns [open, high, low, close, volume].
        Return a dict with at minimum:
            signal      : "BUY" | "SELL" | "HOLD"
            detail      : human-readable explanation string
        """


# ── Phase 1: Dual EMA crossover ───────────────────────────────────────────────

class EMACrossStrategy(BaseStrategy):
    """
    Generates a signal based on EMA fast/slow crossover.

    BUY  — fast EMA crossed above slow EMA today
    SELL — fast EMA crossed below slow EMA today
    HOLD — no crossover today
    """

    def __init__(self, fast: int = EMA_FAST, slow: int = EMA_SLOW):
        self.fast = fast
        self.slow = slow

    def compute(self, df: pd.DataFrame) -> dict:
        if len(df) < self.slow + 2:
            return {"signal": "HOLD", "detail": "Insufficient history"}

        df = df.copy()
        df["ema_fast"] = ta.ema(df["close"], length=self.fast)
        df["ema_slow"] = ta.ema(df["close"], length=self.slow)
        df.dropna(inplace=True)

        if len(df) < 2:
            return {"signal": "HOLD", "detail": "Insufficient data after EMA calc"}

        prev_fast, prev_slow = df["ema_fast"].iloc[-2], df["ema_slow"].iloc[-2]
        curr_fast, curr_slow = df["ema_fast"].iloc[-1], df["ema_slow"].iloc[-1]
        close = df["close"].iloc[-1]
        date = df.index[-1]

        if prev_fast <= prev_slow and curr_fast > curr_slow:
            signal = "BUY"
        elif prev_fast >= prev_slow and curr_fast < curr_slow:
            signal = "SELL"
        else:
            signal = "HOLD"

        gap_pct = ((curr_fast - curr_slow) / curr_slow) * 100
        detail = (
            f"EMA{self.fast}={curr_fast:.3f}  EMA{self.slow}={curr_slow:.3f}  "
            f"gap={gap_pct:+.2f}%  close={close:.3f}  ({date})"
        )
        return {
            "signal": signal,
            "close": round(close, 4),
            "ema_fast": round(curr_fast, 4),
            "ema_slow": round(curr_slow, 4),
            "gap_pct": round(gap_pct, 2),
            "detail": detail,
        }


# ── Runner ─────────────────────────────────────────────────────────────────────

def compute_signals(
    data: dict[str, pd.DataFrame],
    strategy: BaseStrategy | None = None,
) -> list[dict]:
    """
    Run the strategy on every ticker.
    Returns a list of result dicts, sorted by signal priority (BUY/SELL first).
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
    return results
