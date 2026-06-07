# Rev 1
"""Section 5 — News & Events: recent headlines, upcoming FOMC/CPI/NFP, event risk."""
from __future__ import annotations

from datetime import datetime, timezone

from modules.reporting.models import ReportBundle


def render_text(b: ReportBundle) -> str:
    n     = b.news_result
    now   = n.analysis_datetime or b.generated_at

    lines = [
        "",
        "[SECTION 5 -- NEWS & EVENTS]",
        "",
        f"  Event Risk Level : {n.event_risk_level.upper()}",
        "",
        "  Upcoming Economic Events (next 30 days):",
    ]

    if n.upcoming_events:
        lines.append(f"  {'Event':<8} {'Scheduled (UTC)':<22} {'Impact':<10} Hours Away")
        lines.append(f"  {'-'*7} {'-'*21} {'-'*9} {'-'*10}")
        for ev in n.upcoming_events:
            sched      = ev["scheduled_at"]
            hours_away = (sched - now).total_seconds() / 3600
            fmt        = sched.strftime("%Y-%m-%d %H:%M")
            lines.append(
                f"  {ev['event_name']:<8} {fmt:<22} {ev['impact_level']:<10} {hours_away:.0f}h"
            )
    else:
        lines.append("  No major events in next 30 days")

    # Sentiment summary
    if n.items:
        counts: dict[str, int] = {}
        for item in n.items:
            counts[item.classification] = counts.get(item.classification, 0) + 1
        total = len(n.items)
        lines.extend(["", f"  News Sentiment ({total} items):"])
        for cls in ("bullish", "bearish", "neutral", "unknown"):
            cnt = counts.get(cls, 0)
            if cnt:
                lines.append(f"  {cls.capitalize():<10}: {cnt:>3}  ({cnt/total*100:.0f}%)")

    # Recent headlines
    lines.extend(["", f"  Recent Headlines ({min(10, len(n.items))} of {len(n.items)}):"])
    for item in n.items[:10]:
        cls  = item.classification[:4].upper()
        pub  = item.published_at.strftime("%m-%d %H:%M") if item.published_at else "??-??"
        hl   = item.headline if len(item.headline) <= 50 else item.headline[:47] + "..."
        lines.append(f"  [{cls}] {pub}  {hl}")

    return "\n".join(lines)


def render_html(b: ReportBundle) -> str:
    return f'<div class="section" id="s05"><h2>5. News &amp; Events</h2><pre>{render_text(b)}</pre></div>'
