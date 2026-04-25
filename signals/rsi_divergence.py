"""
signals/rsi_divergence.py — RSI divergence with EMA trend filter strategy.
"""

import pandas as pd
import pandas_ta as ta

from config import EMA_SLOW, RSI_LOOKBACK, RSI_PERIOD, RSI_SWING_WINDOW
from signals.base import BaseStrategy


class RSIDivergenceStrategy(BaseStrategy):
    """
    Detects bullish or bearish RSI divergence, confirmed by the slow EMA
    trend direction.

    Bullish divergence (BUY):
      - Price makes a lower low vs. a prior swing low in the lookback window
      - RSI makes a higher low at the same points  (momentum improving)
      - Slow EMA is sloping upward  (pullback within uptrend, not breakdown)

    Bearish divergence (SELL):
      - Price makes a higher high vs. a prior swing high in the lookback window
      - RSI makes a lower high at the same points  (momentum fading)
      - Slow EMA is sloping downward  (rally within downtrend, not breakout)

    HOLD — no divergence detected, or trend filter not satisfied

    Swing points are identified as local extrema: a bar is a swing low if its
    close is strictly lower than the `swing_window` bars on either side.

    Parameters
    ----------
    rsi_period   : RSI calculation period
    swing_window : neighbourhood half-width for swing point detection
    lookback     : how many bars back to search for a prior swing point
    ema_slow     : slow EMA period used as the trend filter
    """

    def __init__(
        self,
        rsi_period:   int = RSI_PERIOD,
        swing_window: int = RSI_SWING_WINDOW,
        lookback:     int = RSI_LOOKBACK,
        ema_slow:     int = EMA_SLOW,
    ):
        self.rsi_period   = rsi_period
        self.swing_window = swing_window
        self.lookback     = lookback
        self.ema_slow     = ema_slow

    @property
    def name(self) -> str:
        return (
            f"RSI({self.rsi_period}) divergence + "
            f"EMA{self.ema_slow} trend filter"
        )

    # ── Swing point helpers ───────────────────────────────────────────────────

    def _find_prior_swing_low(self, close: pd.Series, rsi: pd.Series) -> int | None:
        """
        Scan backward from bar[-2] (excluding the current bar) up to
        `lookback` bars. Return the integer position of the most recent
        swing low, or None if no swing low is found.

        A swing low is a bar whose close is strictly lower than all
        `swing_window` bars on each side.
        """
        w            = self.swing_window
        search_end   = len(close) - 2
        search_start = max(w, search_end - self.lookback)

        for i in range(search_end, search_start - 1, -1):
            if i - w < 0 or i + w >= len(close):
                continue
            neighbours = list(range(i - w, i + w + 1))
            neighbours.remove(i)
            if all(close.iloc[i] < close.iloc[j] for j in neighbours):
                return i
        return None

    def _find_prior_swing_high(self, close: pd.Series, rsi: pd.Series) -> int | None:
        """
        Scan backward from bar[-2] up to `lookback` bars.
        Return the integer position of the most recent swing high, or None.
        """
        w            = self.swing_window
        search_end   = len(close) - 2
        search_start = max(w, search_end - self.lookback)

        for i in range(search_end, search_start - 1, -1):
            if i - w < 0 or i + w >= len(close):
                continue
            neighbours = list(range(i - w, i + w + 1))
            neighbours.remove(i)
            if all(close.iloc[i] > close.iloc[j] for j in neighbours):
                return i
        return None

    # ── Main compute ──────────────────────────────────────────────────────────

    def compute(self, df: pd.DataFrame) -> dict:
        min_bars = self.ema_slow + self.lookback + self.swing_window + 2
        if len(df) < min_bars:
            return {"signal": "HOLD", "detail": "Insufficient history"}

        df = df.copy()
        df["rsi"]      = ta.rsi(df["close"], length=self.rsi_period)
        df["ema_slow"] = ta.ema(df["close"], length=self.ema_slow)
        df.dropna(inplace=True)

        if len(df) < self.swing_window * 2 + 3:
            return {"signal": "HOLD", "detail": "Insufficient data after indicator calc"}

        close    = df["close"]
        rsi      = df["rsi"]
        ema_slow = df["ema_slow"]
        date     = df.index[-1]

        curr_close  = close.iloc[-1]
        curr_rsi    = rsi.iloc[-1]
        curr_ema    = ema_slow.iloc[-1]
        prev_ema    = ema_slow.iloc[-2]
        ema_rising  = bool(curr_ema > prev_ema)
        ema_falling = bool(curr_ema < prev_ema)

        signal = "HOLD"
        detail_parts = [
            f"RSI={curr_rsi:.1f}",
            f"EMA{self.ema_slow}={'↑' if ema_rising else '↓' if ema_falling else '→'}",
            f"close={curr_close:.3f}",
            f"({date})",
        ]

        # Bullish divergence — only when EMA is rising (uptrend pullback)
        if ema_rising:
            swing_idx = self._find_prior_swing_low(close, rsi)
            if swing_idx is not None:
                prior_close = close.iloc[swing_idx]
                prior_rsi   = rsi.iloc[swing_idx]
                if curr_close < prior_close and curr_rsi > prior_rsi:
                    signal = "BUY"
                    detail_parts += [
                        "bullish divergence",
                        f"price LL ({curr_close:.3f} < {prior_close:.3f})",
                        f"RSI HL ({curr_rsi:.1f} > {prior_rsi:.1f})",
                    ]

        # Bearish divergence — only when EMA is falling (downtrend rally)
        if ema_falling:
            swing_idx = self._find_prior_swing_high(close, rsi)
            if swing_idx is not None:
                prior_close = close.iloc[swing_idx]
                prior_rsi   = rsi.iloc[swing_idx]
                if curr_close > prior_close and curr_rsi < prior_rsi:
                    signal = "SELL"
                    detail_parts += [
                        "bearish divergence",
                        f"price HH ({curr_close:.3f} > {prior_close:.3f})",
                        f"RSI LH ({curr_rsi:.1f} < {prior_rsi:.1f})",
                    ]

        return {
            "signal":     signal,
            "close":      round(curr_close, 4),
            "rsi":        round(curr_rsi, 2),
            "ema_slow":   round(curr_ema, 4),
            "ema_rising": ema_rising,
            "detail":     "  ".join(detail_parts),
        }