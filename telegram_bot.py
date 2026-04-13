"""
alerts/telegram_bot.py — Send the nightly signal summary via Telegram.

Uses the simplest possible approach: a single synchronous Bot.send_message()
call. No webhook, no async server, no polling loop needed.
"""

import logging
from datetime import datetime
import telegram
from config import TELEGRAM_TOKEN, TELEGRAM_CHAT_ID

log = logging.getLogger(__name__)

SIGNAL_EMOJI = {
    "BUY":  "🟢",
    "SELL": "🔴",
    "HOLD": "⚪",
    "ERROR": "⚠️",
}


def _format_message(signals: list[dict]) -> str:
    now = datetime.now().strftime("%d %b %Y, %H:%M SGT")
    lines = [f"📊 *Nightly Signal Report*", f"_{now}_", ""]

    buy  = [s for s in signals if s["signal"] == "BUY"]
    sell = [s for s in signals if s["signal"] == "SELL"]
    hold = [s for s in signals if s["signal"] == "HOLD"]
    err  = [s for s in signals if s["signal"] == "ERROR"]

    def ticker_line(s: dict) -> str:
        emoji = SIGNAL_EMOJI.get(s["signal"], "❓")
        ticker = s["ticker"].replace(".", "\\.")   # escape for MarkdownV2
        close = s.get("close", "N/A")
        gap = s.get("gap_pct")
        gap_str = f"  gap {gap:+.2f}%" if gap is not None else ""
        return f"{emoji} `{ticker}`  close: {close}{gap_str}"

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
        lines.extend(f"⚪ `{s['ticker'].replace('.','\\.')}`" for s in hold)
        lines.append("")
    if err:
        lines.append("*Errors*")
        lines.extend(f"⚠️ `{s['ticker'].replace('.','\\.')}` — {s['detail']}" for s in err)

    lines.append("─────────────────")
    lines.append("_EMA 20/50 crossover strategy_")
    return "\n".join(lines)


def send_summary(signals: list[dict]):
    """Send the formatted signal summary to your Telegram chat."""
    if not TELEGRAM_TOKEN or TELEGRAM_TOKEN == "YOUR_BOT_TOKEN_HERE":
        print("  ⚠️  Telegram not configured — printing report to stdout instead:\n")
        print(_format_message(signals).replace("*", "").replace("`", "").replace("_", ""))
        return

    try:
        bot = telegram.Bot(token=TELEGRAM_TOKEN)
        msg = _format_message(signals)
        # split if very long (Telegram max is 4096 chars)
        for chunk in [msg[i:i+4000] for i in range(0, len(msg), 4000)]:
            bot.send_message(
                chat_id=TELEGRAM_CHAT_ID,
                text=chunk,
                parse_mode="MarkdownV2",
            )
        log.info("Telegram message sent")
        print("  ✓ Telegram alert sent")
    except Exception as e:
        log.error(f"Telegram send failed: {e}")
        print(f"  ✗ Telegram error: {e}")
