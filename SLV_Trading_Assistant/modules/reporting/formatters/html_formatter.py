# Rev 2  (Session 5: embedded interactive chart via chart_generator)
"""
HTML formatter.
Calls render_html() on each section and wraps the result in a complete,
self-contained HTML document with inline CSS — no external dependencies.
An interactive Plotly chart is embedded after Section 3 (Technical Setup).
"""
from __future__ import annotations

from modules.reporting.formatters import chart_generator
from modules.reporting.models import ReportBundle
from modules.reporting.sections import (
    s01_executive_summary,
    s02_trading_style,
    s03_technical_setup,
    s04_macro_scorecard,
    s05_news_events,
    s06_historical_context,
    s07_signal_decision,
    s08_trade_plan,
    s09_risk_warnings,
    s10_data_quality,
    s11_final_summary,
)

_SECTION_MODULES = [
    s01_executive_summary,
    s02_trading_style,
    s03_technical_setup,
    s04_macro_scorecard,
    s05_news_events,
    s06_historical_context,
    s07_signal_decision,
    s08_trade_plan,
    s09_risk_warnings,
    s10_data_quality,
    s11_final_summary,
]

_CSS = """
  body {
    font-family: 'Segoe UI', Arial, sans-serif;
    max-width: 960px;
    margin: 32px auto;
    padding: 0 16px;
    background: #f8f9fa;
    color: #212529;
    line-height: 1.5;
  }
  h1 { font-size: 1.6rem; color: #1a1a2e; border-bottom: 2px solid #dee2e6; padding-bottom: 8px; }
  h2 { font-size: 1.15rem; color: #1a1a2e; margin-top: 0; }
  h3 { font-size: 1rem; margin: 8px 0 4px; }
  .section {
    background: #fff;
    border-radius: 6px;
    border: 1px solid #dee2e6;
    padding: 20px 24px;
    margin-bottom: 16px;
    box-shadow: 0 1px 3px rgba(0,0,0,.06);
  }
  .report-meta { color: #6c757d; font-size: 0.85rem; margin: -8px 0 12px; }
  .action-box {
    border-left: 5px solid #aaa;
    padding: 12px 16px;
    margin: 12px 0;
    background: #f0f4f8;
    border-radius: 4px;
    display: flex;
    align-items: center;
    gap: 20px;
  }
  .action-label {
    font-size: 2rem;
    font-weight: 800;
    letter-spacing: 2px;
  }
  .action-meta { font-size: 0.9rem; color: #555; }
  .no-trade-banner {
    background: #fff3cd;
    border: 1px solid #ffc107;
    border-radius: 4px;
    padding: 8px 12px;
    font-weight: 600;
    color: #856404;
  }
  table { border-collapse: collapse; width: 100%; margin-top: 8px; }
  th { background: #e9ecef; font-weight: 600; }
  th, td { border: 1px solid #dee2e6; padding: 7px 10px; text-align: left; font-size: 0.88rem; }
  .kv-table td:first-child { font-weight: 600; width: 40%; background: #f8f9fa; }
  .data-table tr:nth-child(even) td { background: #f8f9fa; }
  .evidence-grid { display: flex; gap: 16px; margin-top: 8px; }
  .evidence-col { flex: 1; }
  .evidence-list { padding-left: 18px; margin: 4px 0; }
  .bull-item { color: #1a7a2e; }
  .bear-item { color: #c0392b; }
  .conflict-item { color: #d68910; font-weight: 600; }
  .explanation { background: #f0f4f8; padding: 10px 14px; border-radius: 4px;
                 font-family: monospace; font-size: 0.87rem; white-space: pre-wrap; }
  .warn-box { background: #fff3cd; border: 1px solid #ffc107; border-radius: 4px;
              padding: 8px 12px; margin-top: 8px; }
  .warn-box ul { margin: 0; padding-left: 18px; }
  .warn-inline { color: #856404; font-size: 0.87rem; margin: 6px 0 0; }
  .disclaimer-box {
    background: #e9ecef;
    border-left: 4px solid #6c757d;
    padding: 10px 14px;
    border-radius: 4px;
    font-size: 0.82rem;
    color: #495057;
    margin-top: 12px;
  }
  pre {
    background: #f8f9fa;
    padding: 12px;
    border-radius: 4px;
    font-size: 0.82rem;
    white-space: pre-wrap;
    word-break: break-word;
    overflow-x: auto;
  }
  .toc { margin-bottom: 24px; }
  .toc a { color: #1a1a2e; text-decoration: none; font-size: 0.88rem; }
  .toc a:hover { text-decoration: underline; }
  .toc li { margin: 2px 0; }
"""


def generate(bundle: ReportBundle) -> str:
    """Return a complete single-file HTML document containing all 11 sections."""
    dt    = bundle.generated_at.strftime("%Y-%m-%d %H:%M UTC")
    style = bundle.trading_style.upper()
    title = f"SLV Trading Assistant -- {style} -- {dt}"

    toc_items = "\n".join(
        f'      <li><a href="#s{i:02d}">{i}. {name}</a></li>'
        for i, name in enumerate([
            "Executive Summary", "Trading Style", "Technical Setup",
            "Macro Scorecard", "News & Events", "Historical Context",
            "Signal Decision", "Trade Plan", "Risk Warnings",
            "Data Quality", "Final Summary",
        ], 1)
    )

    # Build sections, injecting the chart div after Section 3 (Technical Setup)
    section_html_parts: list[str] = []
    for idx, mod in enumerate(_SECTION_MODULES):
        try:
            section_html_parts.append(mod.render_html(bundle))
        except Exception as exc:  # noqa: BLE001
            section_html_parts.append(
                f'<div class="section"><p>Section render error: {exc}</p></div>'
            )
        # Inject chart after s03 (index 2)
        if idx == 2:
            chart_html = _build_chart_section(bundle)
            section_html_parts.append(chart_html)

    sections_html = "\n".join(section_html_parts)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{title}</title>
  <style>
{_CSS}
  </style>
</head>
<body>
  <h1>SLV Trading Assistant</h1>
  <p class="report-meta">Style: {style} &nbsp;|&nbsp; Generated: {dt}</p>

  <nav class="section toc">
    <strong>Contents</strong>
    <ol>
{toc_items}
    </ol>
  </nav>

  {sections_html}

</body>
</html>"""


def _build_chart_section(bundle: ReportBundle) -> str:
    """Wrap the generated chart HTML in a styled section div."""
    chart_html = chart_generator.generate_chart_html(bundle)
    return f"""
<div class="section" id="chart">
  <h2>Interactive Price Chart</h2>
  <p class="report-meta">Price, volume, RSI(14) and MACD — last 90 sessions</p>
  {chart_html}
</div>"""
