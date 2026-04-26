"""
alerts/formatter.py — Signal message formatting for Telegram MarkdownV2.

Pure functions only — no Telegram imports, no environment variables, no I/O.
This makes formatting independently testable and easy to extend or adapt
for other delivery channels (email, Slack, etc.).
"""

from datetime import datetime

SIGNAL_EMOJI = {
    "BUY":   "🟢",
    "SELL":  "🔴",
    "HOLD":  "⚪",
    "ERROR": "⚠️",
}


def escape(text: str) -> str:
    """Escape special characters for Telegram MarkdownV2."""
    for ch in r"\_*[]()~`>#+-=|{}.!":
        text = text.replace(ch, f"\\{ch}")
    return text


def _strategy_detail(s: dict) -> str:
    """Return the strategy-specific detail string for a signal dict."""
    # EMA crossover
    gap = s.get("gap_pct")
    if gap is not None:
        return f"  gap {escape(f'{gap:+.2f}%')}"

    # Volume breakout
    if s.get("vol_ratio") is not None:
        vol  = escape(f"{s['vol_ratio']:.2f}x vol")
        high = escape(str(s.get("recent_high", "")))
        low  = escape(str(s.get("recent_low", "")))
        return f"  {vol}  hi={high} lo={low}"

    # RSI divergence
    if s.get("rsi") is not None:
        rsi   = escape(f"RSI {s['rsi']:.1f}")
        trend = "↑" if s.get("ema_rising") else "↓"
        return f"  {rsi}  EMA {trend}"

    # Daily return (cross-sectional)
    if s.get("daily_return") is not None:
        dr_str = f"DR {s['daily_return']:+.3f}%"
        return f"  {escape(dr_str)}"

    return ""


def _fundamental_line(s: dict) -> str | None:
    """Return a caution line if the signal has fundamental flags, else None."""
    if not s.get("fund_caution"):
        return None
    reasons = "  ".join(s.get("fund_reasons", []))
    return f"    ⚠️ _{escape(reasons)}_"


def ticker_line(s: dict) -> str:
    """Format a single ticker signal as a Telegram MarkdownV2 line."""
    emoji  = SIGNAL_EMOJI.get(s["signal"], "❓")
    ticker = escape(s["ticker"])
    close  = s.get("close", "N/A")
    detail = _strategy_detail(s)
    fund   = _fundamental_line(s)

    line = f"{emoji} `{ticker}`  close: {escape(str(close))}{detail}"
    if fund:
        line += f"\n{fund}"
    return line


def format_message(signals: list[dict], strategy_name: str) -> str:
    """
    Build a complete Telegram MarkdownV2 message from a list of signal dicts.
    HOLD signals are excluded — only BUY, SELL, and ERROR are rendered.
    """
    now   = datetime.now().strftime("%d %b %Y, %H:%M SGT")
    lines = ["📊 *Nightly Signal Report*", f"_{escape(now)}_", ""]

    buy = [s for s in signals if s["signal"] == "BUY"]
    sell = [s for s in signals if s["signal"] == "SELL"]
    err  = [s for s in signals if s["signal"] == "ERROR"]

    if buy:
        lines.append("*BUY signals*")
        lines.extend(ticker_line(s) for s in buy)
        lines.append("")
    if sell:
        lines.append("*SELL signals*")
        lines.extend(ticker_line(s) for s in sell)
        lines.append("")
    if err:
        lines.append("*Errors*")
        lines.extend(
            f"⚠️ `{escape(s['ticker'])}` — {escape(s['detail'])}"
            for s in err
        )
        lines.append("")

    lines.append("─────────────────")
    lines.append(f"_{escape(strategy_name)}_")
    return "\n".join(lines)


def strip_markdown(text: str) -> str:
    """Strip MarkdownV2 formatting for plain-text stdout fallback."""
    for ch in r"*_`\\":
        text = text.replace(ch, "")
    return text