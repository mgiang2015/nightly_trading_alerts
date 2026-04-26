"""
alerts/ — Alert delivery package.

Re-exports send_summary so callers can use:
    from alerts import send_summary

Internal structure:
    formatter.py — pure MarkdownV2 message building (no Telegram dependency)
    sender.py    — Telegram delivery, credentials, async wrapper
"""

from alerts.sender import send_summary

__all__ = ["send_summary"]