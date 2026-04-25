"""
tests/test_telegram.py — Tests for the Telegram message formatter.

We test _format_message and _escape directly. send_summary is excluded:
mocking asyncio.run + telegram.Bot adds complexity for little confidence gain.
"""

import pytest

from alerts.telegram_bot import _escape, _format_message

# ── _escape ───────────────────────────────────────────────────────────────────

class TestEscape:

    def test_escapes_dot(self):
        assert _escape("ES3.SI") == "ES3\\.SI"

    def test_escapes_plus(self):
        assert _escape("+1.5%") == "\\+1\\.5%"

    def test_escapes_hyphen(self):
        assert _escape("gap -0.5%") == "gap \\-0\\.5%"

    def test_escapes_equals(self):
        assert _escape("a=b") == "a\\=b"

    def test_escapes_underscore(self):
        assert _escape("ema_slow") == "ema\\_slow"

    def test_escapes_asterisk(self):
        assert _escape("a*b") == "a\\*b"

    def test_plain_text_unchanged(self):
        assert _escape("hello world") == "hello world"

    def test_empty_string(self):
        assert _escape("") == ""


# ── _format_message ───────────────────────────────────────────────────────────

def _buy_signal(ticker="AAA"):
    return {"ticker": ticker, "signal": "BUY", "close": 1.23, "gap_pct": 0.45}

def _sell_signal(ticker="BBB"):
    return {"ticker": ticker, "signal": "SELL", "close": 2.34, "gap_pct": -0.67}

def _hold_signal(ticker="CCC"):
    return {"ticker": ticker, "signal": "HOLD", "close": 3.45, "gap_pct": 0.01}

def _error_signal(ticker="DDD"):
    return {"ticker": ticker, "signal": "ERROR", "detail": "something broke"}


class TestFormatMessage:

    STRATEGY_NAME = "Test strategy"

    def test_header_present(self):
        msg = _format_message([_hold_signal()], self.STRATEGY_NAME)
        assert "Nightly Signal Report" in msg

    def test_buy_section_present_when_buy_signal(self):
        msg = _format_message([_buy_signal()], self.STRATEGY_NAME)
        assert "BUY signals" in msg

    def test_sell_section_present_when_sell_signal(self):
        msg = _format_message([_sell_signal()], self.STRATEGY_NAME)
        assert "SELL signals" in msg

    def test_hold_section_present_when_hold_signal(self):
        msg = _format_message([_hold_signal()], self.STRATEGY_NAME)
        assert "No crossover today" in msg

    def test_error_section_present_when_error_signal(self):
        msg = _format_message([_error_signal()], self.STRATEGY_NAME)
        assert "Errors" in msg

    def test_buy_section_absent_when_no_buy(self):
        msg = _format_message([_hold_signal()], self.STRATEGY_NAME)
        assert "BUY signals" not in msg

    def test_sell_section_absent_when_no_sell(self):
        msg = _format_message([_hold_signal()], self.STRATEGY_NAME)
        assert "SELL signals" not in msg

    def test_ticker_appears_in_output(self):
        msg = _format_message([_buy_signal("D05\\.SI")], self.STRATEGY_NAME)
        assert "D05" in msg

    def test_close_price_appears_in_output(self):
        msg = _format_message([_buy_signal()], self.STRATEGY_NAME)
        assert "1\\.23" in msg

    def test_gap_pct_appears_in_output(self):
        msg = _format_message([_buy_signal()], self.STRATEGY_NAME)
        assert "0\\.45" in msg

    def test_strategy_name_appears_in_footer(self):
        msg = _format_message([_hold_signal()], "My custom strategy")
        assert "My custom strategy" in msg

    def test_empty_signals_list(self):
        """Empty input should not raise and still produce a header."""
        msg = _format_message([], self.STRATEGY_NAME)
        assert "Nightly Signal Report" in msg

    def test_multiple_signals_all_appear(self):
        signals = [_buy_signal("AAA"), _sell_signal("BBB"), _hold_signal("CCC")]
        msg = _format_message(signals, self.STRATEGY_NAME)
        assert "AAA" in msg
        assert "BBB" in msg
        assert "CCC" in msg