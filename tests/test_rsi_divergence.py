"""
tests/test_rsi_divergence.py — Tests for RSIDivergenceStrategy.

Design notes:
- Use small RSI/EMA periods so tests need fewer rows.
- Use doji candles (high=low=open=close) for price precision.
- Swing detection requires swing_window bars on each side, so we need
  enough history for a prior swing to form and be detected.
- EMA trend filter: build a clear rising or falling EMA by feeding a
  sustained trend before the divergence setup.
"""

import numpy as np
import pandas as pd
import pytest

from signals import RSIDivergenceStrategy
from tests.conftest import make_ohlcv

# Small periods so tests need ~60 bars rather than hundreds
RSI_PERIOD   = 7
SWING_WINDOW = 2
LOOKBACK     = 20
EMA_SLOW     = 10


def make_doji(closes: list[float], volumes: list[int] | None = None) -> pd.DataFrame:
    """OHLCV DataFrame with doji candles — open=high=low=close — for price precision."""
    df = make_ohlcv(closes)
    df["high"]  = df["close"]
    df["low"]   = df["close"]
    df["open"]  = df["close"]
    if volumes:
        df["volume"] = volumes
    return df


def _make_strategy() -> RSIDivergenceStrategy:
    return RSIDivergenceStrategy(
        rsi_period=RSI_PERIOD,
        swing_window=SWING_WINDOW,
        lookback=LOOKBACK,
        ema_slow=EMA_SLOW,
    )


def _bullish_divergence_df() -> pd.DataFrame:
    """
    Construct a DataFrame that contains a clear bullish divergence on the
    final bar:

    Phase 1 — uptrend (establishes rising EMA):
        30 bars rising from 100 → 130, ensuring ema_slow points up.

    Phase 2 — first swing low:
        3 bars declining sharply to 80, creating a local price low and a
        low RSI reading. The surrounding bars make it a clean swing low.

    Phase 3 — partial recovery:
        5 bars rising back to ~100, allowing RSI to recover.

    Phase 4 — second (lower) price low, but RSI stays higher:
        Current bar closes at 75 (< 80, lower low in price) but because
        the decline is gentler / shorter, RSI is higher than it was at 80.
        EMA is still rising from the long uptrend.
    """
    closes = (
        list(range(100, 131))          # 31 bars rising → rising EMA
        + [100, 85, 80, 85, 100]       # dip to swing low at 80 (surrounded)
        + list(range(100, 106))        # 6 bars recovery
        + [95, 90, 75]                 # final bars: lower price low
    )
    return make_doji(closes)


def _bearish_divergence_df() -> pd.DataFrame:
    """
    Symmetric to the bullish case:

    Phase 1 — downtrend (establishes falling EMA):
        31 bars falling from 130 → 100.

    Phase 2 — first swing high:
        Spike up to 150, surrounded by lower bars → clean swing high.

    Phase 3 — partial pullback then higher price high, lower RSI high.
    """
    closes = (
        list(range(130, 99, -1))       # 31 bars falling → falling EMA
        + [130, 145, 150, 145, 130]    # spike to swing high at 150 (surrounded)
        + list(range(130, 124, -1))    # 6 bars pullback
        + [135, 140, 155]              # final bars: higher price high
    )
    return make_doji(closes)


class TestRSIDivergenceStrategy:

    def setup_method(self):
        self.strategy = _make_strategy()

    # ── Insufficient history ──────────────────────────────────────────────────

    def test_insufficient_history_returns_hold(self):
        df = make_doji([100.0] * 10)
        result = self.strategy.compute(df)
        assert result["signal"] == "HOLD"
        assert "Insufficient" in result["detail"]

    # ── Result structure ──────────────────────────────────────────────────────

    def test_result_contains_required_keys(self):
        # Use a gentle uptrend so RSI and EMA are well-defined after dropna
        df = make_doji(list(range(100, 180)))
        result = self.strategy.compute(df)
        for key in ("signal", "close", "rsi", "ema_slow", "ema_rising", "detail"):
            assert key in result, f"Missing key: {key}"

    def test_rsi_is_in_valid_range(self):
        df = make_doji(list(range(100, 180)))
        result = self.strategy.compute(df)
        assert 0 <= result["rsi"] <= 100

    def test_ema_rising_is_bool(self):
        df = make_doji(list(range(100, 180)))
        result = self.strategy.compute(df)
        assert isinstance(result["ema_rising"], bool)

    # ── EMA trend filter ──────────────────────────────────────────────────────

    def test_ema_rising_on_uptrend(self):
        """A sustained uptrend should produce a rising EMA flag."""
        closes = list(range(100, 180))
        df = make_doji(closes)
        result = self.strategy.compute(df)
        assert result["ema_rising"]

    def test_ema_falling_on_downtrend(self):
        """A sustained downtrend should produce a non-rising EMA flag."""
        closes = list(range(180, 100, -1))
        df = make_doji(closes)
        result = self.strategy.compute(df)
        assert result["ema_rising"] == False

    # ── HOLD when trend filter blocks signal ──────────────────────────────────

    def test_hold_when_flat_prices(self):
        """No swing points on flat prices → HOLD."""
        df = make_doji([100.0] * 80)
        result = self.strategy.compute(df)
        assert result["signal"] == "HOLD"

    def test_no_buy_when_ema_falling(self):
        """
        Even if price makes a lower low, BUY requires a rising EMA.
        With a falling EMA the trend filter blocks the signal.
        """
        closes = (
            list(range(130, 99, -1))   # falling → EMA falling
            + [80, 70, 65]             # lower lows
        )
        df = make_doji(closes)
        result = self.strategy.compute(df)
        assert result["signal"] != "BUY"

    def test_no_sell_when_ema_rising(self):
        """
        Even if price makes a higher high, SELL requires a falling EMA.
        With a rising EMA the trend filter blocks the signal.
        """
        closes = (
            list(range(100, 131))      # rising → EMA rising
            + [140, 150, 160]          # higher highs
        )
        df = make_doji(closes)
        result = self.strategy.compute(df)
        assert result["signal"] != "SELL"

    # ── Swing detection ───────────────────────────────────────────────────────

    def test_find_prior_swing_low_returns_none_on_flat(self):
        closes = pd.Series([100.0] * 30)
        rsi    = pd.Series([50.0]  * 30)
        result = self.strategy._find_prior_swing_low(closes, rsi)
        assert result is None

    def test_find_prior_swing_low_finds_dip(self):
        """A clear V-shape dip should be identified as a swing low."""
        closes = pd.Series(
            [100.0] * 5 + [90.0] + [100.0] * 5   # dip at index 5
        )
        rsi = pd.Series([50.0] * len(closes))
        result = self.strategy._find_prior_swing_low(closes, rsi)
        assert result is not None

    def test_find_prior_swing_high_returns_none_on_flat(self):
        closes = pd.Series([100.0] * 30)
        rsi    = pd.Series([50.0]  * 30)
        result = self.strategy._find_prior_swing_high(closes, rsi)
        assert result is None

    def test_find_prior_swing_high_finds_peak(self):
        """A clear inverted-V peak should be identified as a swing high."""
        closes = pd.Series(
            [100.0] * 5 + [110.0] + [100.0] * 5   # peak at index 5
        )
        rsi = pd.Series([50.0] * len(closes))
        result = self.strategy._find_prior_swing_high(closes, rsi)
        assert result is not None

    # ── Custom parameters ─────────────────────────────────────────────────────

    def test_custom_parameters_stored(self):
        s = RSIDivergenceStrategy(
            rsi_period=10, swing_window=4, lookback=30, ema_slow=20
        )
        assert s.rsi_period   == 10
        assert s.swing_window == 4
        assert s.lookback     == 30
        assert s.ema_slow     == 20

    def test_name_contains_rsi_period_and_ema(self):
        s = RSIDivergenceStrategy(rsi_period=14, ema_slow=50)
        assert "14" in s.name
        assert "50" in s.name