# Rev 1
"""Section 3 — Technical Setup: indicators, S/R levels, patterns, vol regime."""
from __future__ import annotations

from modules.reporting.models import ReportBundle


def render_text(b: ReportBundle) -> str:
    t   = b.tech_result
    ind = t.indicators

    close     = ind.get("close")
    sma_20    = ind.get("sma_20")
    sma_50    = ind.get("sma_50")
    sma_200   = ind.get("sma_200")
    ema_9     = ind.get("ema_9")
    ema_21    = ind.get("ema_21")
    rsi       = ind.get("rsi_14")
    macd      = ind.get("macd")
    macd_sig  = ind.get("macd_signal")
    macd_hist = ind.get("macd_hist")
    atr       = ind.get("atr_14")
    bb_upper  = ind.get("bb_upper")
    bb_lower  = ind.get("bb_lower")
    bb_pct    = ind.get("bb_pct")
    rel_vol   = ind.get("relative_volume")
    obv       = ind.get("obv_trend", "unknown")
    patterns  = ind.get("patterns", [])

    def _ma_line(label, ma_val):
        if ma_val is None:
            return f"  {label:<14}: N/A"
        rel = "above" if (close or 0) > ma_val else "below"
        return f"  {label:<14}: ${ma_val:.2f}  [{rel}]"

    lines = [
        "",
        "[SECTION 3 -- TECHNICAL SETUP]",
        "",
        f"  Trend Direction : {t.trend_direction.upper()}",
        f"  Vol Regime      : {t.vol_regime}",
        "",
        "  Moving Averages:",
        _ma_line("  SMA(20)", sma_20),
        _ma_line("  SMA(50)", sma_50),
        _ma_line("  SMA(200)", sma_200),
        _ma_line("  EMA(9)", ema_9),
        _ma_line("  EMA(21)", ema_21),
        "",
        "  Momentum:",
    ]

    if rsi is not None:
        lbl = "overbought" if rsi > 70 else ("oversold" if rsi < 30 else "neutral")
        lines.append(f"  {'RSI(14)':<14}: {rsi:.1f}  [{lbl}]")

    if macd is not None and macd_sig is not None and macd_hist is not None:
        bias = "bullish" if macd_hist > 0 else "bearish"
        lines.append(
            f"  {'MACD':<14}: {macd:+.3f}  Sig: {macd_sig:+.3f}  Hist: {macd_hist:+.3f}  [{bias}]"
        )

    lines.extend(["", "  Volatility:"])
    if atr is not None:
        lines.append(f"  {'ATR(14)':<14}: ${atr:.2f}")
    if bb_upper and bb_lower:
        lines.append(f"  {'BB Upper':<14}: ${bb_upper:.2f}")
        lines.append(f"  {'BB Lower':<14}: ${bb_lower:.2f}")
    if bb_pct is not None:
        pos = "near upper" if bb_pct > 0.8 else ("near lower" if bb_pct < 0.2 else "mid-band")
        lines.append(f"  {'BB %B':<14}: {bb_pct:.2f}  [{pos}]")

    lines.extend(["", "  Volume:"])
    if rel_vol is not None:
        flag = " [above avg]" if rel_vol > 1.5 else (" [below avg]" if rel_vol < 0.7 else "")
        lines.append(f"  {'Rel Volume':<14}: {rel_vol:.2f}x{flag}")
    lines.append(f"  {'OBV Trend':<14}: {obv}")

    lines.extend(["", "  Support / Resistance:"])
    if t.resistance_levels:
        lines.append("  Resistance : " + "  ".join(f"${r:.2f}" for r in t.resistance_levels[:5]))
    else:
        lines.append("  Resistance : none identified")
    if t.support_levels:
        lines.append("  Support    : " + "  ".join(f"${s:.2f}" for s in t.support_levels[:5]))
    else:
        lines.append("  Support    : none identified")

    lines.extend(["", "  Patterns:"])
    lines.append(f"  {', '.join(patterns) if patterns else 'none detected'}")

    return "\n".join(lines)


def render_html(b: ReportBundle) -> str:
    return f'<div class="section" id="s03"><h2>3. Technical Setup</h2><pre>{render_text(b)}</pre></div>'
