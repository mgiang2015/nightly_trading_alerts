"""
tests/test_fundamental_filter.py — Tests for the fundamental filter.

We test threshold checks and annotation logic using synthetic fundamental
data — no yfinance network calls, no cache I/O.
"""

from unittest.mock import patch
from signals.fundamental_filter import _check_thresholds, _get_sector, annotate_signals


# ── _get_sector ───────────────────────────────────────────────────────────────

class TestGetSector:

    def test_bank_tickers(self):
        assert _get_sector("D05.SI") == "bank"
        assert _get_sector("O39.SI") == "bank"
        assert _get_sector("U11.SI") == "bank"

    def test_reit_tickers(self):
        assert _get_sector("C38U.SI") == "reit"
        assert _get_sector("A17U.SI") == "reit"
        assert _get_sector("M44U.SI") == "reit"

    def test_industrial_tickers(self):
        assert _get_sector("V03.SI") == "industrial"
        assert _get_sector("Z74.SI") == "industrial"

    def test_unknown_ticker_defaults_to_industrial(self):
        assert _get_sector("UNKNOWN.SI") == "industrial"


# ── _check_thresholds (bank) ──────────────────────────────────────────────────

class TestBankThresholds:

    def test_bank_clean(self):
        assert _check_thresholds("D05.SI", {"pb_ratio": 1.5, "div_yield": 5.0, "de_ratio": 8.0}) == []

    def test_bank_high_pb_flagged(self):
        reasons = _check_thresholds("D05.SI", {"pb_ratio": 2.5, "div_yield": 5.0, "de_ratio": 8.0})
        assert any("P/B" in r for r in reasons)

    def test_bank_de_not_checked(self):
        """D/E should never be flagged for banks regardless of value."""
        reasons = _check_thresholds("D05.SI", {"pb_ratio": 1.5, "div_yield": 5.0, "de_ratio": 99.0})
        assert not any("D/E" in r for r in reasons)

    def test_bank_div_yield_not_checked(self):
        """Dividend yield is not thresholded for banks."""
        reasons = _check_thresholds("D05.SI", {"pb_ratio": 1.5, "div_yield": 0.5, "de_ratio": 1.0})
        assert not any("Div" in r for r in reasons)


# ── _check_thresholds (reit) ──────────────────────────────────────────────────

class TestReitThresholds:

    def test_reit_clean(self):
        assert _check_thresholds("C38U.SI", {"pb_ratio": 5.0, "div_yield": 5.5, "de_ratio": 0.8}) == []

    def test_reit_low_div_yield_flagged(self):
        reasons = _check_thresholds("C38U.SI", {"pb_ratio": 1.0, "div_yield": 2.5, "de_ratio": 0.8})
        assert any("Div" in r for r in reasons)

    def test_reit_high_de_flagged(self):
        reasons = _check_thresholds("C38U.SI", {"pb_ratio": 1.0, "div_yield": 5.5, "de_ratio": 1.2})
        assert any("D/E" in r for r in reasons)

    def test_reit_pb_not_checked(self):
        """P/B should never be flagged for REITs."""
        reasons = _check_thresholds("C38U.SI", {"pb_ratio": 10.0, "div_yield": 5.5, "de_ratio": 0.8})
        assert not any("P/B" in r for r in reasons)


# ── _check_thresholds (industrial) ───────────────────────────────────────────

class TestIndustrialThresholds:

    def test_industrial_clean(self):
        assert _check_thresholds("V03.SI", {"pb_ratio": 2.0, "div_yield": 3.0, "de_ratio": 1.0}) == []

    def test_industrial_high_pb_flagged(self):
        reasons = _check_thresholds("V03.SI", {"pb_ratio": 4.0, "div_yield": 3.0, "de_ratio": 1.0})
        assert any("P/B" in r for r in reasons)

    def test_industrial_high_de_flagged(self):
        reasons = _check_thresholds("V03.SI", {"pb_ratio": 2.0, "div_yield": 3.0, "de_ratio": 2.5})
        assert any("D/E" in r for r in reasons)

    def test_industrial_div_yield_not_checked(self):
        reasons = _check_thresholds("V03.SI", {"pb_ratio": 2.0, "div_yield": 0.5, "de_ratio": 1.0})
        assert not any("Div" in r for r in reasons)

    def test_unknown_ticker_uses_industrial(self):
        reasons = _check_thresholds("UNKNOWN.SI", {"pb_ratio": 4.0, "div_yield": 3.0, "de_ratio": 1.0})
        assert any("P/B" in r for r in reasons)

    def test_none_metrics_not_flagged(self):
        assert _check_thresholds("V03.SI", {"pb_ratio": None, "div_yield": None, "de_ratio": None}) == []


# ── annotate_signals ──────────────────────────────────────────────────────────

CLEAN_FUND  = {"pb_ratio": 1.5, "div_yield": 5.0, "de_ratio": 0.8}
RISKY_FUND  = {"pb_ratio": 5.0, "div_yield": 1.0, "de_ratio": 3.0}


def _mock_annotate(signals, fund_data):
    def fake_fetch(ticker):
        return fund_data.get(ticker, CLEAN_FUND)

    with patch("signals.fundamental_filter._load_cache", return_value=None), \
         patch("signals.fundamental_filter._save_cache"), \
         patch("signals.fundamental_filter._get_conn"), \
         patch("signals.fundamental_filter._fetch_fundamentals", side_effect=fake_fetch):
        return annotate_signals(signals)


class TestAnnotateSignals:

    def test_buy_annotated(self):
        result = _mock_annotate(
            [{"ticker": "V03.SI", "signal": "BUY", "close": 1.0}],
            {"V03.SI": CLEAN_FUND},
        )
        assert "fund_caution" in result[0]

    def test_sell_annotated(self):
        result = _mock_annotate(
            [{"ticker": "V03.SI", "signal": "SELL", "close": 1.0}],
            {"V03.SI": CLEAN_FUND},
        )
        assert "fund_caution" in result[0]

    def test_hold_not_annotated(self):
        result = _mock_annotate(
            [{"ticker": "V03.SI", "signal": "HOLD", "close": 1.0}],
            {"V03.SI": CLEAN_FUND},
        )
        assert "fund_caution" not in result[0]

    def test_error_not_annotated(self):
        result = _mock_annotate(
            [{"ticker": "V03.SI", "signal": "ERROR", "detail": "bad"}],
            {"V03.SI": CLEAN_FUND},
        )
        assert "fund_caution" not in result[0]

    def test_clean_stock_no_caution(self):
        result = _mock_annotate(
            [{"ticker": "V03.SI", "signal": "BUY", "close": 1.0}],
            {"V03.SI": CLEAN_FUND},
        )
        assert result[0]["fund_caution"] is False
        assert result[0]["fund_reasons"] == []

    def test_risky_industrial_flagged(self):
        result = _mock_annotate(
            [{"ticker": "V03.SI", "signal": "BUY", "close": 1.0}],
            {"V03.SI": RISKY_FUND},
        )
        assert result[0]["fund_caution"] is True

    def test_sector_attached_to_result(self):
        result = _mock_annotate(
            [{"ticker": "D05.SI", "signal": "BUY", "close": 36.0}],
            {"D05.SI": CLEAN_FUND},
        )
        assert result[0]["fund_sector"] == "bank"

    def test_bank_high_de_not_flagged(self):
        """High D/E on a bank should not produce caution — D/E is irrelevant for banks."""
        bank_high_de = {"pb_ratio": 1.5, "div_yield": 5.0, "de_ratio": 99.0}
        result = _mock_annotate(
            [{"ticker": "D05.SI", "signal": "BUY", "close": 36.0}],
            {"D05.SI": bank_high_de},
        )
        assert result[0]["fund_caution"] is False

    def test_reit_low_div_flagged(self):
        reit_low_div = {"pb_ratio": 1.0, "div_yield": 2.0, "de_ratio": 0.8}
        result = _mock_annotate(
            [{"ticker": "C38U.SI", "signal": "BUY", "close": 2.0}],
            {"C38U.SI": reit_low_div},
        )
        assert result[0]["fund_caution"] is True

    def test_original_keys_preserved(self):
        result = _mock_annotate(
            [{"ticker": "V03.SI", "signal": "BUY", "close": 1.23, "gap_pct": 0.5}],
            {"V03.SI": CLEAN_FUND},
        )
        assert result[0]["close"] == 1.23
        assert result[0]["gap_pct"] == 0.5

    def test_mixed_signals(self):
        signals = [
            {"ticker": "D05.SI",  "signal": "BUY",  "close": 36.0},
            {"ticker": "C38U.SI", "signal": "SELL", "close": 2.0},
            {"ticker": "V03.SI",  "signal": "HOLD", "close": 3.0},
        ]
        result = _mock_annotate(signals, {
            "D05.SI":  CLEAN_FUND,
            "C38U.SI": CLEAN_FUND,
            "V03.SI":  CLEAN_FUND,
        })
        by_ticker = {r["ticker"]: r for r in result}
        assert "fund_caution" in by_ticker["D05.SI"]
        assert "fund_caution" in by_ticker["C38U.SI"]
        assert "fund_caution" not in by_ticker["V03.SI"]