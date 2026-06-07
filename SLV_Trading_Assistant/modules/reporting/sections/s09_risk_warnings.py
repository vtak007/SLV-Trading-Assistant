# Rev 1
"""Section 9 — Risk Warnings: flags, event warnings, stale data, ATR extremes."""
from __future__ import annotations

from modules.reporting.models import ReportBundle


def render_text(b: ReportBundle) -> str:
    s = b.signal_result
    r = b.risk_result
    n = b.news_result
    t = b.tech_result

    warnings: list[str] = []

    if r.no_trade_conditions:
        for cond in r.no_trade_conditions:
            warnings.append(f"NO-TRADE: {cond}")

    if r.major_event_flag:
        warnings.append(f"MAJOR EVENT: event_risk_level={n.event_risk_level.upper()}")

    if r.gap_risk_flag:
        warnings.append("GAP RISK: Last bar range exceeds 1.5x ATR -- stop may be gapped through")

    if b.price_data.is_stale:
        warnings.append("STALE DATA: Price data older than 2 trading days")

    if t.vol_regime in ("high", "extreme"):
        warnings.append(f"HIGH VOLATILITY: vol_regime={t.vol_regime} -- reduce position size")

    if s.conflicts:
        for c in s.conflicts:
            warnings.append(f"CONFLICT: {c}")

    if n.event_risk_level in ("critical", "high"):
        for ev in n.upcoming_events:
            if ev.get("impact_level") in ("critical", "high"):
                sched = ev["scheduled_at"].strftime("%Y-%m-%d %H:%M UTC")
                warnings.append(f"EVENT CAUTION: {ev['event_name']} at {sched}")

    lines = [
        "",
        "[SECTION 9 -- RISK WARNINGS]",
        "",
    ]
    if warnings:
        for w in warnings:
            lines.append(f"  !! {w}")
    else:
        lines.append("  No active risk warnings.")

    return "\n".join(lines)


def render_html(b: ReportBundle) -> str:
    return f'<div class="section" id="s09"><h2>9. Risk Warnings</h2><pre>{render_text(b)}</pre></div>'
