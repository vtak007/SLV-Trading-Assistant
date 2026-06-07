# Rev 1
"""Section 1 — Executive Summary: action, confidence, and key metrics at a glance."""
from __future__ import annotations

from modules.reporting.models import ReportBundle

_SEP = "=" * 62


def render_text(b: ReportBundle) -> str:
    s  = b.signal_result
    t  = b.tech_result
    ts = b.trading_style.upper()
    dt = b.generated_at.strftime("%Y-%m-%d %H:%M UTC")
    close = t.indicators.get("close") or 0.0
    atr   = t.indicators.get("atr_14") or 0.0
    rsi   = t.indicators.get("rsi_14")

    action_label = f"*** {s.action} ***"
    lines = [
        _SEP,
        f"  SLV TRADING ASSISTANT -- FULL REPORT",
        f"  Style: {ts}  |  {dt}",
        _SEP,
        "",
        "[SECTION 1 -- EXECUTIVE SUMMARY]",
        "",
        f"  ACTION     : {action_label}",
        f"  Confidence : {s.confidence:.0f}%",
        f"  Risk Score : {s.risk_score:.0f}/100",
        f"  Regime     : {s.regime_label}",
        "",
        f"  Current Price : ${close:.2f}",
        f"  ATR(14)       : ${atr:.2f}",
    ]
    if rsi is not None:
        lines.append(f"  RSI(14)       : {rsi:.1f}")
    lines.append(f"  Vol Regime    : {t.vol_regime}")
    lines.append(f"  Trend         : {t.trend_direction.upper()}")

    if s.no_trade_reason:
        lines.append("")
        lines.append(f"  NO-TRADE: {s.no_trade_reason}")

    return "\n".join(lines)


def render_html(b: ReportBundle) -> str:
    s     = b.signal_result
    t     = b.tech_result
    ts    = b.trading_style.upper()
    dt    = b.generated_at.strftime("%Y-%m-%d %H:%M UTC")
    close = t.indicators.get("close") or 0.0
    atr   = t.indicators.get("atr_14") or 0.0
    rsi   = t.indicators.get("rsi_14")

    action_colour = {
        "BUY": "#1a7a2e", "SELL": "#c0392b",
        "HOLD": "#d68910", "NO_TRADE": "#7f8c8d",
    }.get(s.action, "#333")

    rsi_row = f"<tr><td>RSI(14)</td><td>{rsi:.1f}</td></tr>" if rsi is not None else ""
    no_trade_banner = (
        f'<p class="no-trade-banner">NO-TRADE: {s.no_trade_reason}</p>'
        if s.no_trade_reason else ""
    )

    return f"""
<div class="section" id="s01">
  <h2>1. Executive Summary</h2>
  <p class="report-meta">Style: {ts} &nbsp;|&nbsp; {dt}</p>
  <div class="action-box" style="border-color:{action_colour}">
    <span class="action-label" style="color:{action_colour}">{s.action}</span>
    <span class="action-meta">Confidence: {s.confidence:.0f}% &nbsp;|&nbsp; Risk: {s.risk_score:.0f}/100 &nbsp;|&nbsp; Regime: {s.regime_label}</span>
  </div>
  {no_trade_banner}
  <table class="kv-table">
    <tr><td>Current Price</td><td>${close:.2f}</td></tr>
    <tr><td>ATR(14)</td><td>${atr:.2f}</td></tr>
    {rsi_row}
    <tr><td>Vol Regime</td><td>{t.vol_regime}</td></tr>
    <tr><td>Trend</td><td>{t.trend_direction.upper()}</td></tr>
  </table>
</div>"""
