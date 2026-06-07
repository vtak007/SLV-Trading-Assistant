# Rev 1
"""Section 2 — Trading Style: active profile and its domain weights."""
from __future__ import annotations

from config.trading_styles import TradingStyle, STYLE_WEIGHTS
from modules.reporting.models import ReportBundle

_STYLE_DESCRIPTIONS = {
    "day":       "Intraday — positions closed same day; 70% technical weight.",
    "swing":     "2-10 day holds; balanced technical + macro weighting.",
    "position":  "Weeks to months; macro fundamentals dominate.",
    "long_term": "Multi-month horizon; macro and news drive decisions.",
}


def render_text(b: ReportBundle) -> str:
    style  = b.trading_style
    try:
        ts_enum  = TradingStyle(style)
        weights  = STYLE_WEIGHTS[ts_enum]
    except (ValueError, KeyError):
        return f"\n[SECTION 2 -- TRADING STYLE]\n\n  Style: {style}  (weights unavailable)\n"

    desc = _STYLE_DESCRIPTIONS.get(style, "")
    lines = [
        "",
        "[SECTION 2 -- TRADING STYLE]",
        "",
        f"  Active Style : {style.upper()}",
        f"  Description  : {desc}",
        "",
        f"  Domain Weights:",
        f"    Technical : {weights.technical*100:.0f}%",
        f"    Macro     : {weights.macro*100:.0f}%",
        f"    News      : {weights.news*100:.0f}%",
    ]
    return "\n".join(lines)


def render_html(b: ReportBundle) -> str:
    style = b.trading_style
    try:
        ts_enum = TradingStyle(style)
        w       = STYLE_WEIGHTS[ts_enum]
    except (ValueError, KeyError):
        return f'<div class="section" id="s02"><h2>2. Trading Style</h2><p>{style}</p></div>'

    desc = _STYLE_DESCRIPTIONS.get(style, "")
    return f"""
<div class="section" id="s02">
  <h2>2. Trading Style</h2>
  <p><strong>{style.upper()}</strong> &mdash; {desc}</p>
  <table class="kv-table">
    <tr><th>Domain</th><th>Weight</th></tr>
    <tr><td>Technical</td><td>{w.technical*100:.0f}%</td></tr>
    <tr><td>Macro</td><td>{w.macro*100:.0f}%</td></tr>
    <tr><td>News</td><td>{w.news*100:.0f}%</td></tr>
  </table>
</div>"""
