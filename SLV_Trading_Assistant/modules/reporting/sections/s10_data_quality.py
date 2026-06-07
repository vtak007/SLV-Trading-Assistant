# Rev 1
"""Section 10 — Data Quality: freshness status for all data sources."""
from __future__ import annotations

from modules.reporting.models import ReportBundle


def render_text(b: ReportBundle) -> str:
    pd_ = b.price_data
    m   = b.macro_result
    n   = b.news_result

    def status(flag: bool) -> str:
        return "STALE" if flag else "FRESH"

    lines = [
        "",
        "[SECTION 10 -- DATA QUALITY]",
        "",
        f"  {'Source':<28} {'Status':<8}  Detail",
        f"  {'-'*28} {'-'*7}  {'-'*30}",
        f"  {'Price (SLV)':<28} {status(pd_.is_stale):<8}  "
        f"{len(pd_.ohlcv)} rows, latest {pd_.ohlcv.index[-1].strftime('%Y-%m-%d') if not pd_.ohlcv.empty else 'N/A'}",
    ]

    # Macro drivers
    unknown_count = sum(1 for d in m.drivers if d.score == "unknown")
    stale_warnings = [w for w in m.missing_data_warnings if "stale" in w.lower()]
    macro_status   = "STALE" if stale_warnings else ("WARN" if unknown_count > 0 else "FRESH")
    lines.append(
        f"  {'Macro (FRED)':<28} {macro_status:<8}  "
        f"{len(m.drivers)} drivers, {unknown_count} unknown"
    )

    # News feeds
    news_status = "NO FEED" if not n.items else "FRESH"
    lines.append(
        f"  {'News (RSS)':<28} {news_status:<8}  "
        f"{len(n.items)} items fetched"
    )

    # Price data warnings
    if pd_.warnings:
        lines.extend(["", "  Price Warnings:"])
        for w in pd_.warnings:
            lines.append(f"   ! {w}")

    # Macro missing data warnings
    if m.missing_data_warnings:
        lines.extend(["", "  Macro Warnings:"])
        for w in m.missing_data_warnings:
            lines.append(f"   ! {w}")

    return "\n".join(lines)


def render_html(b: ReportBundle) -> str:
    return f'<div class="section" id="s10"><h2>10. Data Quality</h2><pre>{render_text(b)}</pre></div>'
