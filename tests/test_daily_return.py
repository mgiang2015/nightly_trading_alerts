"""
tests/test_daily_return.py — Tests for DailyReturnStrategy and
cross-sectional routing in compute_signals.
"""

import numpy as np
import pandas as pd
import pytest

from signals import DailyReturnStrategy, compute_signals
from tests.conftest import make_ohlcv


def make_ticker_data(tickers_returns: dict[str, float]) -> dict[str, pd.DataFrame]:
    """
    Build a minimal data dict from {ticker: daily_return_pct}.
    Each DataFrame has 2 bars: yesterday (100.0) and today (100 * (1 + return)).
    """
    data = {}
    for ticker, ret in tickers_returns.items():
        closes = [100.0, 100.0 * (1 + ret)]
        data[ticker] = make_ohlcv(closes)
    return data


class TestDailyReturnStrategy:

    def setup_method(self):
        self.strategy = DailyReturnStrategy(top_n=2)

    # ── Signal assignment ─────────────────────────────────────────────────────

    def test_biggest_losers_get_buy(self):
        """Bottom-N tickers by daily return should be BUY."""
        data = make_ticker_data({
            "AAA": -0.05,   # worst → BUY
            "BBB": -0.03,   # second worst → BUY
            "CCC":  0.00,
            "DDD":  0.02,
            "EEE":  0.04,
        })
        results = self.strategy.compute_all(data)
        signal_map = {r["ticker"]: r["signal"] for r in results}
        assert signal_map["AAA"] == "BUY"
        assert signal_map["BBB"] == "BUY"

    def test_biggest_winners_get_sell(self):
        """Top-N tickers by daily return should be SELL."""
        data = make_ticker_data({
            "AAA": -0.05,
            "BBB": -0.03,
            "CCC":  0.00,
            "DDD":  0.03,   # second best → SELL
            "EEE":  0.05,   # best → SELL
        })
        results = self.strategy.compute_all(data)
        signal_map = {r["ticker"]: r["signal"] for r in results}
        assert signal_map["EEE"] == "SELL"
        assert signal_map["DDD"] == "SELL"

    def test_middle_tickers_get_hold(self):
        """Tickers between top and bottom N should be HOLD."""
        data = make_ticker_data({
            "AAA": -0.05,
            "BBB": -0.03,
            "CCC":  0.00,   # middle → HOLD
            "DDD":  0.03,
            "EEE":  0.05,
        })
        results = self.strategy.compute_all(data)
        signal_map = {r["ticker"]: r["signal"] for r in results}
        assert signal_map["CCC"] == "HOLD"

    def test_all_tickers_assigned(self):
        """Every ticker in data should appear in results."""
        data = make_ticker_data({"A": 0.01, "B": -0.01, "C": 0.02})
        results = self.strategy.compute_all(data)
        result_tickers = {r["ticker"] for r in results}
        assert result_tickers == {"A", "B", "C"}

    # ── Result structure ──────────────────────────────────────────────────────

    def test_result_contains_required_keys(self):
        data = make_ticker_data({"A": 0.01, "B": -0.01, "C": 0.02, "D": -0.02, "E": 0.0})
        results = self.strategy.compute_all(data)
        for r in results:
            if r["signal"] != "ERROR":
                for key in ("ticker", "signal", "close", "daily_return", "detail"):
                    assert key in r, f"Missing key '{key}' in result for {r['ticker']}"

    def test_daily_return_calculated_correctly(self):
        """daily_return should be (close_today - close_prev) / close_prev * 100."""
        data = make_ticker_data({"A": 0.05, "B": -0.05, "C": 0.0})
        results = self.strategy.compute_all(data)
        dr_map = {r["ticker"]: r["daily_return"] for r in results if r["signal"] != "ERROR"}
        assert dr_map["A"] == pytest.approx(5.0, rel=1e-3)
        assert dr_map["B"] == pytest.approx(-5.0, rel=1e-3)

    def test_insufficient_data_returns_error(self):
        """A single-bar DataFrame (no previous close) should produce ERROR."""
        data = {"BAD": make_ohlcv([100.0])}
        results = self.strategy.compute_all(data)
        assert results[0]["signal"] == "ERROR"
        assert results[0]["ticker"] == "BAD"

    def test_custom_top_n(self):
        """top_n=1 should flag exactly 1 BUY and 1 SELL."""
        strategy = DailyReturnStrategy(top_n=1)
        data = make_ticker_data({"A": -0.05, "B": 0.0, "C": 0.05})
        results = strategy.compute_all(data)
        signal_map = {r["ticker"]: r["signal"] for r in results}
        assert signal_map["A"] == "BUY"
        assert signal_map["C"] == "SELL"
        assert signal_map["B"] == "HOLD"

    def test_name_contains_top_n(self):
        s = DailyReturnStrategy(top_n=5)
        assert "5" in s.name


class TestCrossSectionalRouting:
    """Verify compute_signals correctly routes BaseCrossStrategy subclasses."""

    def test_cross_strategy_routed_correctly(self):
        """compute_signals should call compute_all, not compute, for cross strategies."""
        data = make_ticker_data({"A": -0.05, "B": 0.0, "C": 0.05})
        results, name = compute_signals(data, strategy=DailyReturnStrategy(top_n=1))
        assert len(results) == 3
        assert any(r["signal"] == "BUY" for r in results)
        assert any(r["signal"] == "SELL" for r in results)

    def test_strategy_name_returned(self):
        data = make_ticker_data({"A": 0.01, "B": -0.01, "C": 0.02})
        _, name = compute_signals(data, strategy=DailyReturnStrategy())
        assert isinstance(name, str)
        assert len(name) > 0

    def test_results_sorted_buy_before_sell_before_hold(self):
        data = make_ticker_data({
            "A": -0.05,
            "B":  0.00,
            "C":  0.05,
        })
        results, _ = compute_signals(data, strategy=DailyReturnStrategy(top_n=1))
        signals = [r["signal"] for r in results]
        priority = {"BUY": 0, "SELL": 1, "HOLD": 2, "ERROR": 3}
        assert signals == sorted(signals, key=lambda s: priority.get(s, 9))
