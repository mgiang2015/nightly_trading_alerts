"""
tests/test_volume_breakout.py — Tests for VolumeBreakoutStrategy.
"""

import pytest
import pandas as pd
import numpy as np
from tests.conftest import make_ohlcv
from signals import VolumeBreakoutStrategy

WINDOW   = 5
VOL_MULT = 1.5


def make_ohlcv_with_volume(closes: list[float], volumes: list[int]) -> pd.DataFrame:
    """
    Build OHLCV DataFrame with explicit volume values.
    Uses doji candles (open=high=low=close) so the breakout conditions are
    precise — no derived high/low band can accidentally trigger false signals.
    """
    df = make_ohlcv(closes)
    df["high"]   = df["close"]
    df["low"]    = df["close"]
    df["open"]   = df["close"]
    df["volume"] = volumes
    return df


class TestVolumeBreakoutStrategy:

    def setup_method(self):
        self.strategy = VolumeBreakoutStrategy(window=WINDOW, vol_mult=VOL_MULT)

    # ── Insufficient history ──────────────────────────────────────────────────

    def test_insufficient_history_returns_hold(self):
        df = make_ohlcv([100.0] * WINDOW)   # need window + 1
        result = self.strategy.compute(df)
        assert result["signal"] == "HOLD"
        assert "Insufficient" in result["detail"]

    # ── BUY signal ────────────────────────────────────────────────────────────

    def test_buy_on_high_breakout_with_volume(self):
        """Close above recent high + volume spike → BUY."""
        # 5 reference bars at 100, then one bar breaking above with high volume
        closes  = [100.0] * WINDOW + [110.0]
        volumes = [1000]  * WINDOW + [2000]   # 2x average → above 1.5x threshold
        df = make_ohlcv_with_volume(closes, volumes)
        result = self.strategy.compute(df)
        assert result["signal"] == "BUY"

    def test_no_buy_when_volume_insufficient(self):
        """Price breaks above recent high but volume is too low → HOLD."""
        closes  = [100.0] * WINDOW + [110.0]
        volumes = [1000]  * WINDOW + [1100]   # 1.1x average → below 1.5x threshold
        df = make_ohlcv_with_volume(closes, volumes)
        result = self.strategy.compute(df)
        assert result["signal"] == "HOLD"

    def test_no_buy_when_price_does_not_break_high(self):
        """Volume spike but price stays within range → HOLD."""
        closes  = [100.0] * WINDOW + [99.0]   # below recent high
        volumes = [1000]  * WINDOW + [3000]
        df = make_ohlcv_with_volume(closes, volumes)
        result = self.strategy.compute(df)
        assert result["signal"] == "HOLD"

    # ── SELL signal ───────────────────────────────────────────────────────────

    def test_sell_on_low_breakout_with_volume(self):
        """Close below recent low + volume spike → SELL."""
        closes  = [100.0] * WINDOW + [90.0]
        volumes = [1000]  * WINDOW + [2000]
        df = make_ohlcv_with_volume(closes, volumes)
        result = self.strategy.compute(df)
        assert result["signal"] == "SELL"

    def test_no_sell_when_volume_insufficient(self):
        """Price breaks below recent low but volume is too low → HOLD."""
        closes  = [100.0] * WINDOW + [90.0]
        volumes = [1000]  * WINDOW + [1100]
        df = make_ohlcv_with_volume(closes, volumes)
        result = self.strategy.compute(df)
        assert result["signal"] == "HOLD"

    def test_no_sell_when_price_does_not_break_low(self):
        """Volume spike but price stays within range → HOLD."""
        closes  = [100.0] * WINDOW + [101.0]
        volumes = [1000]  * WINDOW + [3000]
        df = make_ohlcv_with_volume(closes, volumes)
        result = self.strategy.compute(df)
        assert result["signal"] == "HOLD"

    # ── Result structure ──────────────────────────────────────────────────────

    def test_result_contains_required_keys(self):
        closes  = [100.0] * WINDOW + [99.0]
        volumes = [1000]  * (WINDOW + 1)
        df = make_ohlcv_with_volume(closes, volumes)
        result = self.strategy.compute(df)
        for key in ("signal", "close", "recent_high", "recent_low",
                    "vol_ratio", "vol_confirmed", "detail"):
            assert key in result, f"Missing key: {key}"

    def test_vol_ratio_calculated_correctly(self):
        """vol_ratio should be current volume / mean of reference window."""
        closes  = [100.0] * WINDOW + [99.0]
        volumes = [1000]  * WINDOW + [2000]
        df = make_ohlcv_with_volume(closes, volumes)
        result = self.strategy.compute(df)
        assert result["vol_ratio"] == pytest.approx(2.0, rel=1e-2)

    def test_vol_confirmed_false_when_below_threshold(self):
        closes  = [100.0] * WINDOW + [110.0]
        volumes = [1000]  * WINDOW + [1100]
        df = make_ohlcv_with_volume(closes, volumes)
        result = self.strategy.compute(df)
        assert result["vol_confirmed"] == False

    def test_vol_confirmed_true_when_above_threshold(self):
        closes  = [100.0] * WINDOW + [110.0]
        volumes = [1000]  * WINDOW + [2000]
        df = make_ohlcv_with_volume(closes, volumes)
        result = self.strategy.compute(df)
        assert result["vol_confirmed"] == True

    def test_reference_window_excludes_current_bar(self):
        """
        The current bar's volume must not be included in the average —
        otherwise a volume spike would inflate its own threshold.
        With the current bar excluded, avg = 1000, threshold = 1500.
        If included: avg = (5×1000 + 2000)/6 ≈ 1167, threshold ≈ 1750.
        We use 1600 volume — passes only if current bar is excluded.
        """
        closes  = [100.0] * WINDOW + [110.0]
        volumes = [1000]  * WINDOW + [1600]   # 1.6x of 1000 = confirmed
        df = make_ohlcv_with_volume(closes, volumes)
        result = self.strategy.compute(df)
        assert result["vol_confirmed"] == True

    def test_custom_window_and_multiplier(self):
        strategy = VolumeBreakoutStrategy(window=3, vol_mult=2.0)
        assert strategy.window == 3
        assert strategy.vol_mult == 2.0

    def test_flat_prices_hold(self):
        """No breakout on flat prices regardless of volume."""
        closes  = [100.0] * (WINDOW + 1)
        volumes = [1000]  * WINDOW + [9999]
        df = make_ohlcv_with_volume(closes, volumes)
        result = self.strategy.compute(df)
        assert result["signal"] == "HOLD"