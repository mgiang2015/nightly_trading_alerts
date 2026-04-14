"""
signals/engine.py — Strategy base class, EMA crossover, and volume breakout.

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
from config import EMA_FAST, EMA_SLOW, BREAKOUT_WINDOW, VOLUME_MULTIPLIER

log = logging.getLogger(__name__)


# ── Base interface ─────────────────────────────────────────────────────────────

class BaseStrategy(ABC):
    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable strategy name shown in the Telegram footer."""

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

    @property
    def name(self) -> str:
        return f"EMA {self.fast}/{self.slow} crossover"

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


# ── Phase 2: Volume-confirmed breakout ────────────────────────────────────────

class VolumeBreakoutStrategy(BaseStrategy):
    """
    Generates a signal when price breaks out of a recent high or low
    AND volume on that bar is significantly above its recent average.

    BUY  — close breaks above the highest high of the prior N bars,
            with volume > multiplier × rolling average volume
    SELL — close breaks below the lowest low of the prior N bars,
            with volume > multiplier × rolling average volume
    HOLD — no confirmed breakout

    The volume condition filters out the low-conviction moves that are
    common in thinly-traded SGX counters.

    Parameters
    ----------
    window      : lookback period for the high/low and volume average (in bars)
    vol_mult    : minimum ratio of current volume to rolling average
    """

    def __init__(
        self,
        window: int = BREAKOUT_WINDOW,
        vol_mult: float = VOLUME_MULTIPLIER,
    ):
        self.window = window
        self.vol_mult = vol_mult

    @property
    def name(self) -> str:
        return f"Volume-confirmed breakout ({self.window}-bar, {self.vol_mult}x vol)"

    def compute(self, df: pd.DataFrame) -> dict:
        # Need at least window + 1 bars: window bars to form the reference
        # range, plus the current bar being evaluated
        if len(df) < self.window + 1:
            return {"signal": "HOLD", "detail": "Insufficient history"}

        df = df.copy()

        # Reference range excludes the current bar to avoid look-ahead
        ref = df.iloc[-(self.window + 1):-1]
        curr = df.iloc[-1]

        recent_high   = ref["high"].max()
        recent_low    = ref["low"].min()
        avg_volume    = ref["volume"].mean()
        vol_ratio     = curr["volume"] / avg_volume if avg_volume > 0 else 0
        volume_confirmed = vol_ratio >= self.vol_mult

        close = curr["close"]
        date  = df.index[-1]

        if close > recent_high and volume_confirmed:
            signal = "BUY"
        elif close < recent_low and volume_confirmed:
            signal = "SELL"
        else:
            signal = "HOLD"

        detail = (
            f"close={close:.3f}  "
            f"recent_high={recent_high:.3f}  recent_low={recent_low:.3f}  "
            f"vol_ratio={vol_ratio:.2f}x  (threshold {self.vol_mult}x)  ({date})"
        )
        return {
            "signal": signal,
            "close": round(close, 4),
            "recent_high": round(recent_high, 4),
            "recent_low": round(recent_low, 4),
            "vol_ratio": round(vol_ratio, 2),
            "vol_confirmed": volume_confirmed,
            "detail": detail,
        }



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