# Rev 1
"""Section 8 — Trade Plan: entry zone, stop loss, targets, position size."""
from __future__ import annotations

from modules.reporting.models import ReportBundle


def render_text(b: ReportBundle) -> str:
    s = b.signal_result
    r = b.risk_result

    lines = [
        "",
        "[SECTION 8 -- TRADE PLAN]",
        "",
        f"  Action         : {s.action}",
    ]

    if s.action == "NO_TRADE":
        lines.append(f"  Reason         : {s.no_trade_reason}")
        return "\n".join(lines)

    if s.action == "HOLD":
        lines.append("  No entry recommended at this time.")
        lines.append("  Monitor for a directional break to trigger a new signal.")
        return "\n".join(lines)

    # BUY or SELL — show full plan
    lo, hi = s.entry_zone
    lines += [
        f"  Entry Zone     : ${lo:.2f} -- ${hi:.2f}",
        f"  Stop Loss      : ${s.stop_loss:.2f}  (ATR-based: {r.atr_value:.2f} x 2)",
    ]

    if s.targets:
        for i, tgt in enumerate(s.targets, 1):
            lines.append(f"  Target {i}        : ${tgt:.2f}")

    lines += [
        "",
        f"  Position Size  : {s.position_size_pct*100:.1f}% of account",
        f"  Shares (per $10k, 1% risk) : {r.position_size_shares}",
        f"  Account Risk   : {r.account_risk_pct*100:.1f}% per trade",
    ]

    if r.gap_risk_flag:
        lines.append("  ! GAP RISK: Last bar range > 1.5x ATR -- consider limit orders")

    return "\n".join(lines)


def render_html(b: ReportBundle) -> str:
    s = b.signal_result
    r = b.risk_result

    if s.action == "NO_TRADE":
        return f"""
<div class="section" id="s08">
  <h2>8. Trade Plan</h2>
  <p class="no-trade-banner">NO TRADE: {s.no_trade_reason}</p>
</div>"""

    if s.action == "HOLD":
        return """
<div class="section" id="s08">
  <h2>8. Trade Plan</h2>
  <p>No entry recommended. Monitor for a directional break.</p>
</div>"""

    lo, hi   = s.entry_zone
    tgt_rows = "".join(
        f"<tr><td>Target {i}</td><td>${t:.2f}</td></tr>"
        for i, t in enumerate(s.targets, 1)
    )
    gap_warn = (
        '<p class="warn-inline">GAP RISK: Last bar range &gt; 1.5x ATR -- consider limit orders</p>'
        if r.gap_risk_flag else ""
    )

    return f"""
<div class="section" id="s08">
  <h2>8. Trade Plan</h2>
  <table class="kv-table">
    <tr><td>Action</td><td><strong>{s.action}</strong></td></tr>
    <tr><td>Entry Zone</td><td>${lo:.2f} &ndash; ${hi:.2f}</td></tr>
    <tr><td>Stop Loss</td><td>${s.stop_loss:.2f} (ATR {r.atr_value:.2f} &times; 2)</td></tr>
    {tgt_rows}
    <tr><td>Position Size</td><td>{s.position_size_pct*100:.1f}% of account</td></tr>
    <tr><td>Shares per $10k (1% risk)</td><td>{r.position_size_shares}</td></tr>
    <tr><td>Account Risk</td><td>{r.account_risk_pct*100:.1f}%</td></tr>
  </table>
  {gap_warn}
</div>"""
