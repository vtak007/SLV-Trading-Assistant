# Rev 1
"""Section 7 — Signal Decision: composite score breakdown, evidence, conflicts."""
from __future__ import annotations

from modules.reporting.models import ReportBundle


def render_text(b: ReportBundle) -> str:
    s = b.signal_result

    lines = [
        "",
        "[SECTION 7 -- SIGNAL DECISION]",
        "",
    ]
    for line in s.explanation.splitlines():
        lines.append(f"  {line}")

    if s.bullish_evidence:
        lines.extend(["", "  Bullish Evidence:"])
        for ev in s.bullish_evidence:
            lines.append(f"   + {ev}")

    if s.bearish_evidence:
        lines.extend(["", "  Bearish Evidence:"])
        for ev in s.bearish_evidence:
            lines.append(f"   - {ev}")

    if s.conflicts:
        lines.extend(["", "  Conflicts Detected:"])
        for c in s.conflicts:
            lines.append(f"  !! {c}")

    return "\n".join(lines)


def render_html(b: ReportBundle) -> str:
    s = b.signal_result

    bull_rows = "".join(
        f'<li class="bull-item">{ev}</li>' for ev in s.bullish_evidence
    )
    bear_rows = "".join(
        f'<li class="bear-item">{ev}</li>' for ev in s.bearish_evidence
    )
    conflict_rows = "".join(
        f'<li class="conflict-item">{c}</li>' for c in s.conflicts
    )

    expl_html = "<br>".join(s.explanation.splitlines())
    conflict_section = (
        f'<h3>Conflicts</h3><ul class="evidence-list">{conflict_rows}</ul>'
        if s.conflicts else ""
    )

    return f"""
<div class="section" id="s07">
  <h2>7. Signal Decision</h2>
  <p class="explanation">{expl_html}</p>
  <div class="evidence-grid">
    <div class="evidence-col">
      <h3>Bullish Evidence</h3>
      <ul class="evidence-list">{bull_rows if bull_rows else "<li>None</li>"}</ul>
    </div>
    <div class="evidence-col">
      <h3>Bearish Evidence</h3>
      <ul class="evidence-list">{bear_rows if bear_rows else "<li>None</li>"}</ul>
    </div>
  </div>
  {conflict_section}
</div>"""
