"""
alerts/telegram_bot.py — Send the nightly signal summary via Telegram.

python-telegram-bot v20+ is fully async. We wrap the send call in
asyncio.run() so the rest of the pipeline stays synchronous.
"""

import os
import asyncio
import logging
from datetime import datetime
import telegram

log = logging.getLogger(__name__)

TELEGRAM_TOKEN   = os.environ.get("TELEGRAM_TOKEN", "")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")

SIGNAL_EMOJI = {
    "BUY":   "🟢",
    "SELL":  "🔴",
    "HOLD":  "⚪",
    "ERROR": "⚠️",
}


def _escape(text: str) -> str:
    """Escape special characters for Telegram MarkdownV2."""
    for ch in r"\_*[]()~`>#+-=|{}.!":
        text = text.replace(ch, f"\\{ch}")
    return text


def _format_message(signals: list[dict], strategy_name: str) -> str:
    now = datetime.now().strftime("%d %b %Y, %H:%M SGT")
    lines = ["📊 *Nightly Signal Report*", f"_{_escape(now)}_", ""]

    buy  = [s for s in signals if s["signal"] == "BUY"]
    sell = [s for s in signals if s["signal"] == "SELL"]
    hold = [s for s in signals if s["signal"] == "HOLD"]
    err  = [s for s in signals if s["signal"] == "ERROR"]

    def ticker_line(s: dict) -> str:
        emoji  = SIGNAL_EMOJI.get(s["signal"], "❓")
        ticker = _escape(s["ticker"])
        close  = s.get("close", "N/A")

        # EMA crossover detail
        gap = s.get("gap_pct")
        if gap is not None:
            extra = f"  gap {_escape(f'{gap:+.2f}%')}"
        # Volume breakout detail
        elif s.get("vol_ratio") is not None:
            vol   = _escape(f"{s['vol_ratio']:.2f}x vol")
            high  = _escape(str(s.get("recent_high", "")))
            low   = _escape(str(s.get("recent_low", "")))
            extra = f"  {vol}  hi={high} lo={low}"
        # RSI divergence detail
        elif s.get("rsi") is not None:
            rsi   = _escape(f"RSI {s['rsi']:.1f}")
            trend = "↑" if s.get("ema_rising") else "↓"
            extra = f"  {rsi}  EMA {trend}"
        # Daily return (cross-sectional) detail
        elif s.get("daily_return") is not None:
            dr    = _escape(f"DR {s['daily_return']:+.3f}%")
            extra = f"  {dr}"
        else:
            extra = ""

        return f"{emoji} `{ticker}`  close: {_escape(str(close))}{extra}"

    if buy:
        lines.append("*BUY signals*")
        lines.extend(ticker_line(s) for s in buy)
        lines.append("")
    if sell:
        lines.append("*SELL signals*")
        lines.extend(ticker_line(s) for s in sell)
        lines.append("")
    if hold:
        lines.append("*No crossover today*")
        lines.extend(f"⚪ `{_escape(s['ticker'])}`" for s in hold)
        lines.append("")
    if err:
        lines.append("*Errors*")
        lines.extend(f"⚠️ `{_escape(s['ticker'])}` — {_escape(s['detail'])}" for s in err)
        lines.append("")

    lines.append("─────────────────")
    lines.append(f"_{_escape(strategy_name)}_")
    return "\n".join(lines)


def send_summary(signals: list[dict], strategy_name: str):
    """Send the formatted signal summary to your Telegram chat."""
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        print("  ⚠️  Telegram not configured — printing report to stdout instead:\n")
        plain = _format_message(signals, strategy_name)
        for ch in r"*_`\\":
            plain = plain.replace(ch, "")
        print(plain)
        return

    async def _send():
        bot = telegram.Bot(token=TELEGRAM_TOKEN)
        msg = _format_message(signals, strategy_name)
        for chunk in [msg[i:i+4000] for i in range(0, len(msg), 4000)]:
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