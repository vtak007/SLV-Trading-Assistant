# Rev 1
"""Section 6 — Historical Context: 52-week range, price location, key percentile."""
from __future__ import annotations

import pandas as pd

from modules.reporting.models import ReportBundle


def render_text(b: ReportBundle) -> str:
    df    = b.price_data.ohlcv
    t     = b.tech_result
    close = t.indicators.get("close") or 0.0

    lines = [
        "",
        "[SECTION 6 -- HISTORICAL CONTEXT]",
        "",
    ]

    if df.empty or len(df) < 5:
        lines.append("  Insufficient price history for context.")
        return "\n".join(lines)

    # Use up to 252 trading days (1 year)
    lookback = df.tail(252)
    high_52w = float(lookback["high"].max())
    low_52w  = float(lookback["low"].min())
    rng      = high_52w - low_52w

    pct_range = (close - low_52w) / rng * 100 if rng > 0 else 50.0
    avg_close = float(lookback["close"].mean())
    avg_vol   = float(lookback["volume"].mean())
    last_vol  = float(df.iloc[-1]["volume"])

    lines += [
        f"  52-Week High    : ${high_52w:.2f}",
        f"  52-Week Low     : ${low_52w:.2f}",
        f"  Current Price   : ${close:.2f}  ({pct_range:.0f}% of 52-week range)",
        f"  1-Year Avg Close: ${avg_close:.2f}",
        f"  vs. 1-Year Avg  : {'above' if close > avg_close else 'below'}  "
        f"(${abs(close - avg_close):.2f} {'above' if close > avg_close else 'below'})",
        "",
        f"  Avg Daily Volume (1yr) : {avg_vol/1_000_000:.1f}M",
        f"  Last Session Volume    : {last_vol/1_000_000:.1f}M  "
        f"({'above' if last_vol > avg_vol else 'below'} avg)",
    ]

    # 20-day drawdown from recent high
    recent = df.tail(20)
    recent_high = float(recent["high"].max())
    drawdown    = (close - recent_high) / recent_high * 100
    lines.append(f"  20-Day Drawdown        : {drawdown:.1f}% from recent high (${recent_high:.2f})")

    return "\n".join(lines)


def render_html(b: ReportBundle) -> str:
    return f'<div class="section" id="s06"><h2>6. Historical Context</h2><pre>{render_text(b)}</pre></div>'
