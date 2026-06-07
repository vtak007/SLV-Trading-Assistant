# Rev 1
"""Section 11 — Final Summary: one-paragraph narrative + disclaimer."""
from __future__ import annotations

from modules.reporting.models import ReportBundle

DISCLAIMER = (
    "DISCLAIMER: This system is research and decision support only, "
    "not personalized financial advice. All signals are generated "
    "algorithmically from public data and should not be acted upon "
    "without independent verification and appropriate risk management."
)

_SEP = "=" * 62


def render_text(b: ReportBundle) -> str:
    s  = b.signal_result
    t  = b.tech_result
    m  = b.macro_result
    n  = b.news_result
    ts = b.trading_style.upper()

    close = t.indicators.get("close") or 0.0

    # Build a concise narrative paragraph
    trend_phrase = f"The technical trend is {t.trend_direction}"
    macro_phrase = (
        "macro conditions are supportive" if m.composite_score >= 0.20
        else "macro conditions are headwinds" if m.composite_score <= -0.20
        else "macro conditions are neutral"
    )
    news_phrase = (
        f"news sentiment is {n.event_risk_level} risk"
        if n.event_risk_level in ("high", "critical")
        else "no imminent event risk"
    )
    conf_phrase = (
        f"confidence is {'high' if s.confidence >= 65 else 'moderate' if s.confidence >= 40 else 'low'}"
        f" at {s.confidence:.0f}%"
    )

    narrative = (
        f"SLV is currently trading at ${close:.2f}. "
        f"{trend_phrase}, {macro_phrase}, and {news_phrase}. "
        f"The {ts} model produces a {s.action} signal; {conf_phrase}. "
        f"Regime: {s.regime_label}."
    )
    if s.no_trade_reason:
        narrative += f" NOTE: {s.no_trade_reason}."

    lines = [
        "",
        "[SECTION 11 -- FINAL SUMMARY]",
        "",
        f"  {narrative}",
        "",
        _SEP,
        f"  {DISCLAIMER}",
        _SEP,
    ]
    return "\n".join(lines)


def render_html(b: ReportBundle) -> str:
    s  = b.signal_result
    t  = b.tech_result
    m  = b.macro_result
    n  = b.news_result
    ts = b.trading_style.upper()
    close = t.indicators.get("close") or 0.0

    trend_phrase = f"The technical trend is <strong>{t.trend_direction}</strong>"
    macro_phrase = (
        "macro conditions are supportive"
        if m.composite_score >= 0.20
        else "macro conditions are headwinds"
        if m.composite_score <= -0.20
        else "macro conditions are neutral"
    )
    news_phrase = (
        f"news sentiment is <strong>{n.event_risk_level} risk</strong>"
        if n.event_risk_level in ("high", "critical")
        else "no imminent event risk"
    )
    conf_qual = (
        "high" if s.confidence >= 65 else "moderate" if s.confidence >= 40 else "low"
    )

    narrative = (
        f"SLV is currently trading at <strong>${close:.2f}</strong>. "
        f"{trend_phrase}, {macro_phrase}, and {news_phrase}. "
        f"The {ts} model produces a <strong>{s.action}</strong> signal; "
        f"confidence is {conf_qual} at <strong>{s.confidence:.0f}%</strong>. "
        f"Regime: {s.regime_label}."
    )
    if s.no_trade_reason:
        narrative += f" <strong>NOTE:</strong> {s.no_trade_reason}."

    return f"""
<div class="section" id="s11">
  <h2>11. Final Summary</h2>
  <p>{narrative}</p>
  <div class="disclaimer-box">
    <p>{DISCLAIMER}</p>
  </div>
</div>"""
