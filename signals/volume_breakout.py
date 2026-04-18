"""
signals/volume_breakout.py — Volume-confirmed breakout strategy.
"""

import pandas as pd
from config import BREAKOUT_WINDOW, VOLUME_MULTIPLIER
from signals.base import BaseStrategy


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
    window   : lookback period for the high/low and volume average (in bars)
    vol_mult : minimum ratio of current volume to rolling average
    """

    def __init__(
        self,
        window:   int   = BREAKOUT_WINDOW,
        vol_mult: float = VOLUME_MULTIPLIER,
    ):
        self.window   = window
        self.vol_mult = vol_mult

    @property
    def name(self) -> str:
        return f"Volume-confirmed breakout ({self.window}-bar, {self.vol_mult}x vol)"

    def compute(self, df: pd.DataFrame) -> dict:
        # Need window bars for the reference range plus the current bar
        if len(df) < self.window + 1:
            return {"signal": "HOLD", "detail": "Insufficient history"}

        df = df.copy()

        # Reference range excludes the current bar to avoid look-ahead
        ref  = df.iloc[-(self.window + 1):-1]
        curr = df.iloc[-1]

        recent_high      = ref["high"].max()
        recent_low       = ref["low"].min()
        avg_volume       = ref["volume"].mean()
        vol_ratio        = curr["volume"] / avg_volume if avg_volume > 0 else 0
        volume_confirmed = bool(vol_ratio >= self.vol_mult)

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
            "signal":       signal,
            "close":        round(close, 4),
            "recent_high":  round(recent_high, 4),
            "recent_low":   round(recent_low, 4),
            "vol_ratio":    round(vol_ratio, 2),
            "vol_confirmed": volume_confirmed,
            "detail":       detail,
        }