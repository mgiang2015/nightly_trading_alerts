"""
alerts/sender.py — Telegram message delivery.

Handles all Telegram-specific concerns: credentials, async Bot instantiation,
chunked sending, and the stdout fallback when Telegram is not configured.
Formatting is delegated entirely to alerts/formatter.py.

To add a new delivery channel (email, Slack, etc.), create a parallel
sender_*.py module that imports from formatter.py and implements its own
send_summary() signature.
"""

import asyncio
import logging
import os

import telegram

from alerts.formatter import format_message, strip_markdown

log = logging.getLogger(__name__)

TELEGRAM_TOKEN   = os.environ.get("TELEGRAM_TOKEN", "")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")

# Telegram MarkdownV2 message size limit
_MAX_CHUNK = 4000


def has_actionable_signals(signals: list[dict]) -> bool:
    """Return True if there is at least one BUY, SELL, or ERROR signal."""
    return any(s["signal"] in ("BUY", "SELL", "ERROR") for s in signals)


def send_summary(signals: list[dict], strategy_name: str):
    """
    Send the formatted signal summary to your Telegram chat.
    Skips sending entirely if there are no actionable signals (all HOLD).
    Falls back to stdout if Telegram credentials are not configured.
    """
    if not has_actionable_signals(signals):
        log.info(f"No actionable signals for {strategy_name} — skipping alert")
        print(f"  — No actionable signals ({strategy_name}), alert skipped")
        return

    msg = format_message(signals, strategy_name)

    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        print("  ⚠️  Telegram not configured — printing report to stdout instead:\n")
        print(strip_markdown(msg))
        return

    async def _send():
        bot = telegram.Bot(token=TELEGRAM_TOKEN)
        for chunk in [msg[i:i + _MAX_CHUNK] for i in range(0, len(msg), _MAX_CHUNK)]:
            await bot.send_message(
                chat_id=TELEGRAM_CHAT_ID,
                text=chunk,
                parse_mode="MarkdownV2",
            )

    try:
        asyncio.run(_send())
        log.info("Telegram message sent")
        print("  ✓ Telegram alert sent")
    except Exception as e:
        log.error(f"Telegram send failed: {e}")
        print(f"  ✗ Telegram error: {e}")