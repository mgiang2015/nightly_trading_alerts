"""
alerts/telegram_bot.py — Thin shim for backwards compatibility.

Delegates all logic to formatter.py and sender.py.
Kept so existing imports of the form:
    from alerts.telegram_bot import send_summary
continue to work without changes to main.py or tests.
"""

from alerts.formatter import escape, format_message, strip_markdown
from alerts.sender import has_actionable_signals, send_summary

__all__ = [
    "escape",
    "format_message",
    "strip_markdown",
    "send_summary",
    "has_actionable_signals",
]