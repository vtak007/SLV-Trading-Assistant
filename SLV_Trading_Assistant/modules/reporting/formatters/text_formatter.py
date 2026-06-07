# Rev 1
"""
Plain-text formatter.
Calls render_text() on each of the 11 sections and joins them with a separator.
"""
from __future__ import annotations

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


def generate(bundle: ReportBundle) -> str:
    """Return the full 11-section report as plain text."""
    parts: list[str] = []
    for mod in _SECTION_MODULES:
        try:
            parts.append(mod.render_text(bundle))
        except Exception as exc:  # noqa: BLE001 — section failure must not abort report
            parts.append(f"\n[Section render error: {exc}]\n")
    return "\n".join(parts)
