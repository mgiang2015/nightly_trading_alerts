"""
tests/test_telegram.py — Tests for the Telegram message formatter.

Tests formatter.py directly — pure functions, no mocking needed.
send_summary (sender.py) is excluded: mocking asyncio.run + telegram.Bot
adds complexity for little confidence gain.
"""

import pytest
from alerts.formatter import escape, format_message


# ── _escape ───────────────────────────────────────────────────────────────────

class TestEscape:

    def test_escapes_dot(self):
        assert escape("ES3.SI") == "ES3\\.SI"

    def test_escapes_plus(self):
        assert escape("+1.5%") == "\\+1\\.5%"

    def test_escapes_hyphen(self):
        assert escape("gap -0.5%") == "gap \\-0\\.5%"

    def test_escapes_equals(self):
        assert escape("a=b") == "a\\=b"

    def test_escapes_underscore(self):
        assert escape("ema_slow") == "ema\\_slow"

    def test_escapes_asterisk(self):
        assert escape("a*b") == "a\\*b"

    def test_plain_text_unchanged(self):
        assert escape("hello world") == "hello world"

    def test_empty_string(self):
        assert escape("") == ""


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
        msg = format_message([_hold_signal()], self.STRATEGY_NAME)
        assert "Nightly Signal Report" in msg

    def test_buy_section_present_when_buy_signal(self):
        msg = format_message([_buy_signal()], self.STRATEGY_NAME)
        assert "BUY signals" in msg

    def test_sell_section_present_when_sell_signal(self):
        msg = format_message([_sell_signal()], self.STRATEGY_NAME)
        assert "SELL signals" in msg

    def test_hold_section_absent(self):
        """HOLD signals should never appear in the message."""
        msg = format_message([_hold_signal()], self.STRATEGY_NAME)
        assert "No crossover today" not in msg
        assert "⚪" not in msg

    def test_error_section_present_when_error_signal(self):
        msg = format_message([_error_signal()], self.STRATEGY_NAME)
        assert "Errors" in msg

    def test_buy_section_absent_when_no_buy(self):
        msg = format_message([_hold_signal()], self.STRATEGY_NAME)
        assert "BUY signals" not in msg

    def test_sell_section_absent_when_no_sell(self):
        msg = format_message([_hold_signal()], self.STRATEGY_NAME)
        assert "SELL signals" not in msg

    def test_ticker_appears_in_output(self):
        msg = format_message([_buy_signal("D05\\.SI")], self.STRATEGY_NAME)
        assert "D05" in msg

    def test_close_price_appears_in_output(self):
        msg = format_message([_buy_signal()], self.STRATEGY_NAME)
        assert "1\\.23" in msg

    def test_gap_pct_appears_in_output(self):
        msg = format_message([_buy_signal()], self.STRATEGY_NAME)
        assert "0\\.45" in msg

    def test_strategy_name_appears_in_footer(self):
        msg = format_message([_hold_signal()], "My custom strategy")
        assert "My custom strategy" in msg

    def test_empty_signals_list(self):
        """Empty input should not raise and still produce a header."""
        msg = format_message([], self.STRATEGY_NAME)
        assert "Nightly Signal Report" in msg

    def test_multiple_signals_all_appear(self):
        signals = [_buy_signal("AAA"), _sell_signal("BBB"), _hold_signal("CCC")]
        msg = format_message(signals, self.STRATEGY_NAME)
        assert "AAA" in msg
        assert "BBB" in msg
        assert "CCC" not in msg