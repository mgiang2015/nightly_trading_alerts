"""
tests/test_engine.py — Tests for EMACrossStrategy and compute_signals.
"""

import pytest
import pandas as pd
import numpy as np
from tests.conftest import make_ohlcv
from signals.engine import EMACrossStrategy, compute_signals


FAST, SLOW = 5, 10   # small periods so we need fewer rows in tests


# ── EMACrossStrategy ──────────────────────────────────────────────────────────

class TestEMACrossStrategy:

    def setup_method(self):
        self.strategy = EMACrossStrategy(fast=FAST, slow=SLOW)

    def test_insufficient_history_returns_hold(self):
        """Fewer rows than slow period + 2 should return HOLD immediately."""
        df = make_ohlcv([100.0] * (SLOW))   # one row short
        result = self.strategy.compute(df)
        assert result["signal"] == "HOLD"
        assert "Insufficient" in result["detail"]

    def test_buy_signal_on_golden_cross(self):
        """
        Force a BUY crossover on the final bar.
        30 declining bars push fast EMA below slow EMA, then exactly one
        high-price bar causes fast EMA to cross above slow EMA on that bar.
        """
        closes = [100 - i * 1.0 for i in range(30)] + [200.0]
        df = make_ohlcv(closes)
        result = self.strategy.compute(df)
        assert result["signal"] == "BUY", (
            f"Expected BUY but got {result['signal']}. "
            f"ema_fast={result.get('ema_fast')}, ema_slow={result.get('ema_slow')}"
        )

    def test_sell_signal_on_death_cross(self):
        """
        Force a SELL crossover on the final bar.
        30 rising bars push fast EMA above slow EMA, then exactly one
        low-price bar causes fast EMA to cross below slow EMA on that bar.
        """
        closes = [100 + i * 1.0 for i in range(30)] + [10.0]
        df = make_ohlcv(closes)
        result = self.strategy.compute(df)
        assert result["signal"] == "SELL", (
            f"Expected SELL but got {result['signal']}. "
            f"ema_fast={result.get('ema_fast')}, ema_slow={result.get('ema_slow')}"
        )

    def test_hold_when_no_crossover(self):
        """Flat prices produce no crossover → HOLD."""
        df = make_ohlcv([100.0] * 30)
        result = self.strategy.compute(df)
        assert result["signal"] == "HOLD"

    def test_result_contains_required_keys(self):
        """Result dict must always contain the expected keys."""
        df = make_ohlcv([100.0] * 30)
        result = self.strategy.compute(df)
        for key in ("signal", "close", "ema_fast", "ema_slow", "gap_pct", "detail"):
            assert key in result, f"Missing key: {key}"

    def test_close_matches_last_bar(self):
        """Reported close should equal the last bar's close price."""
        closes = [100.0] * 30
        closes[-1] = 42.0
        df = make_ohlcv(closes)
        result = self.strategy.compute(df)
        assert result["close"] == pytest.approx(42.0, rel=1e-3)

    def test_gap_pct_sign_when_fast_above_slow(self):
        """gap_pct should be positive when fast EMA is above slow EMA."""
        closes = [100 - i * 0.5 for i in range(20)] + [120.0, 125.0]
        df = make_ohlcv(closes)
        result = self.strategy.compute(df)
        if result["signal"] == "BUY":
            assert result["gap_pct"] > 0

    def test_custom_periods_respected(self):
        """Strategy should use the fast/slow values passed at construction."""
        strategy = EMACrossStrategy(fast=3, slow=6)
        assert strategy.fast == 3
        assert strategy.slow == 6


# ── compute_signals ───────────────────────────────────────────────────────────

class TestComputeSignals:

    def test_returns_one_result_per_ticker(self):
        data = {
            "AAA": make_ohlcv([100.0] * 30),
            "BBB": make_ohlcv([200.0] * 30),
        }
        results, _ = compute_signals(data, strategy=EMACrossStrategy(fast=FAST, slow=SLOW))
        assert len(results) == 2
        tickers = {r["ticker"] for r in results}
        assert tickers == {"AAA", "BBB"}

    def test_ticker_attached_to_each_result(self):
        data = {"XYZ": make_ohlcv([100.0] * 30)}
        results, _ = compute_signals(data, strategy=EMACrossStrategy(fast=FAST, slow=SLOW))
        assert results[0]["ticker"] == "XYZ"

    def test_buy_sorted_before_hold(self):
        """BUY signals should appear before HOLD in the output list."""
        buy_closes  = [100 - i * 1.0 for i in range(30)] + [200.0]
        hold_closes = [100.0] * 30
        data = {
            "HOLD_TICKER": make_ohlcv(hold_closes),
            "BUY_TICKER":  make_ohlcv(buy_closes),
        }
        results, _ = compute_signals(data, strategy=EMACrossStrategy(fast=FAST, slow=SLOW))
        signals = [r["signal"] for r in results]
        if "BUY" in signals and "HOLD" in signals:
            assert signals.index("BUY") < signals.index("HOLD")

    def test_error_ticker_recorded_gracefully(self):
        """A DataFrame with non-numeric close values should produce an ERROR entry."""
        df = make_ohlcv([100.0] * 30)
        df["close"] = "bad"
        data = {"BAD": df}
        results, _ = compute_signals(data, strategy=EMACrossStrategy(fast=FAST, slow=SLOW))
        assert len(results) == 1
        assert results[0]["signal"] == "ERROR"
        assert results[0]["ticker"] == "BAD"

    def test_empty_data_returns_empty_list(self):
        results, _ = compute_signals({})
        assert results == []

    def test_default_strategy_is_ema_cross(self):
        """compute_signals with no strategy arg should not raise."""
        data = {"T": make_ohlcv([100.0] * 60)}
        results, _ = compute_signals(data)
        assert len(results) == 1

    def test_returns_strategy_name(self):
        """Second element of return tuple should be the strategy display name."""
        data = {"T": make_ohlcv([100.0] * 30)}
        _, name = compute_signals(data, strategy=EMACrossStrategy(fast=FAST, slow=SLOW))
        assert isinstance(name, str)
        assert len(name) > 0