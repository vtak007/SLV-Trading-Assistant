# Rev 1
"""Section 4 — Macro Scorecard: all 8 drivers with scores, values, and evidence."""
from __future__ import annotations

from modules.reporting.models import ReportBundle

_SCORE_EMOJI = {
    "bullish": "(+)", "bearish": "(-)", "neutral": "( )",
    "mixed": "(~)", "unknown": "(?)",
}


def render_text(b: ReportBundle) -> str:
    m  = b.macro_result
    cs = m.composite_score

    if cs >= 0.50:
        cs_label = "strongly bullish"
    elif cs >= 0.20:
        cs_label = "mildly bullish"
    elif cs > -0.20:
        cs_label = "neutral"
    elif cs > -0.50:
        cs_label = "mildly bearish"
    else:
        cs_label = "strongly bearish"

    lines = [
        "",
        "[SECTION 4 -- MACRO SCORECARD]",
        "",
        f"  Composite Macro Score: {cs:+.2f}  ({cs_label})",
        "",
        f"  {'Driver':<24} {'Score':<10} {'Value':>9}  Evidence",
        f"  {'-'*24} {'-'*9} {'-'*9}  {'-'*38}",
    ]

    for d in m.drivers:
        sym     = _SCORE_EMOJI.get(d.score, "   ")
        val_str = f"{d.value:>8.2f}" if d.value is not None else "       N/A"
        ev      = d.evidence if len(d.evidence) <= 55 else d.evidence[:52] + "..."
        lines.append(f"  {d.driver_name:<24} {sym} {d.score:<7} {val_str}  {ev}")

    if m.missing_data_warnings:
        lines.extend(["", "  Warnings:"])
        for w in m.missing_data_warnings:
            lines.append(f"  ! {w}")

    return "\n".join(lines)


def render_html(b: ReportBundle) -> str:
    m  = b.macro_result
    cs = m.composite_score

    score_colour = {
        "bullish": "#1a7a2e", "bearish": "#c0392b",
        "neutral": "#555", "mixed": "#d68910", "unknown": "#999",
    }

    rows = ""
    for d in m.drivers:
        col  = score_colour.get(d.score, "#333")
        val  = f"{d.value:.2f}" if d.value is not None else "N/A"
        ev   = d.evidence if len(d.evidence) <= 70 else d.evidence[:67] + "..."
        rows += (
            f"<tr>"
            f"<td>{d.driver_name}</td>"
            f'<td style="color:{col};font-weight:bold">{d.score.upper()}</td>'
            f"<td>{val}</td>"
            f"<td>{ev}</td>"
            f"</tr>"
        )

    warn_html = ""
    if m.missing_data_warnings:
        warn_items = "".join(f"<li>{w}</li>" for w in m.missing_data_warnings)
        warn_html = f'<div class="warn-box"><ul>{warn_items}</ul></div>'

    cs_col = "#1a7a2e" if cs >= 0.20 else ("#c0392b" if cs <= -0.20 else "#555")
    return f"""
<div class="section" id="s04">
  <h2>4. Macro Scorecard</h2>
  <p>Composite score: <strong style="color:{cs_col}">{cs:+.2f}</strong></p>
  <table class="data-table">
    <tr><th>Driver</th><th>Score</th><th>Value</th><th>Evidence</th></tr>
    {rows}
  </table>
  {warn_html}
</div>"""
