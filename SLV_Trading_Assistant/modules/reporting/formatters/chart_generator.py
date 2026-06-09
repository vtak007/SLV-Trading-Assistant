# Rev 1
"""
Chart generator for the SLV Trading Assistant.

Produces a 4-panel interactive Plotly chart:
  Row 1 (50%): Price line + SMA(20/50/200) + support/resistance levels
  Row 2 (15%): Volume bars (green=up day, red=down day)
  Row 3 (17%): RSI(14) with 30/70 reference bands
  Row 4 (18%): MACD histogram + MACD line + signal line

The chart is returned as a self-contained HTML string (plotly.js embedded
inline — no external CDN dependency).  Falls back to a matplotlib static
PNG (base64 data-URI) if plotly raises at runtime.
"""
from __future__ import annotations

import base64
import io
from typing import Optional

import numpy as np
import pandas as pd
import pandas_ta as ta  # noqa: F401 — registers .ta accessor

from modules.infrastructure.logger import get_logger
from modules.reporting.models import ReportBundle

log = get_logger("chart_generator")

_LOOKBACK_BARS = 90   # how many bars to show in the chart


def generate_chart_html(bundle: ReportBundle) -> str:
    """
    Return an HTML string containing the interactive chart.
    Falls back to a static PNG if plotly is unavailable or fails.
    """
    try:
        return _plotly_chart(bundle)
    except Exception as exc:
        log.warning("Plotly chart failed (%s); falling back to matplotlib", exc)
        try:
            return _matplotlib_chart(bundle)
        except Exception as exc2:
            log.warning("Matplotlib chart also failed: %s", exc2)
            return '<p style="color:#999;font-size:0.85rem;">Chart unavailable</p>'


# ---------------------------------------------------------------------------
# Plotly (interactive)
# ---------------------------------------------------------------------------

def _plotly_chart(bundle: ReportBundle) -> str:
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots

    df     = _prepare_df(bundle)
    s      = bundle.signal_result
    t      = bundle.tech_result
    close  = float(df["close"].iloc[-1])

    # ---- Indicator series ------------------------------------------------
    sma20  = _series(df, "SMA_20")
    sma50  = _series(df, "SMA_50")
    sma200 = _series(df, "SMA_200")
    rsi    = _series(df, "RSI_14")
    macd   = _series(df, "MACD_12_26_9")
    sig    = _series(df, "MACDs_12_26_9")
    hist   = _series(df, "MACDh_12_26_9")
    vol_color = ["#2ecc71" if df["close"].iloc[i] >= df["open"].iloc[i]
                 else "#e74c3c" for i in range(len(df))]

    # ---- Layout ----------------------------------------------------------
    fig = make_subplots(
        rows=4, cols=1,
        shared_xaxes=True,
        row_heights=[0.50, 0.15, 0.175, 0.175],
        vertical_spacing=0.05,
        subplot_titles=(
            f"SLV — Price & Moving Averages (last {_LOOKBACK_BARS} sessions)",
            "Volume",
            "RSI(14)",
            "MACD (12/26/9)",
        ),
    )

    x = df.index

    # ---- Row 1: Price + MAs + S/R ----------------------------------------
    fig.add_trace(go.Scatter(
        x=x, y=df["close"], name="SLV Close",
        line=dict(color="#2c3e50", width=1.5),
        hovertemplate="%{x|%Y-%m-%d}<br>Close: $%{y:.2f}<extra></extra>",
    ), row=1, col=1)

    _add_ma(fig, x, sma20,  "#3498db", "SMA(20)")
    _add_ma(fig, x, sma50,  "#e67e22", "SMA(50)")
    _add_ma(fig, x, sma200, "#9b59b6", "SMA(200)")

    # Support / Resistance horizontal lines
    # Re-classify at draw time: any stored level below close is support, above is resistance.
    all_levels = list(t.support_levels[:3]) + list(t.resistance_levels[:3])
    for lvl in all_levels:
        if lvl < close:
            fig.add_hline(y=lvl, line=dict(color="#27ae60", dash="dot", width=1),
                          annotation_text=f"S ${lvl:.2f}", annotation_position="right",
                          row=1, col=1)
        else:
            fig.add_hline(y=lvl, line=dict(color="#c0392b", dash="dot", width=1),
                          annotation_text=f"R ${lvl:.2f}", annotation_position="top right",
                          row=1, col=1)

    # Current price annotation
    fig.add_hline(y=close, line=dict(color="#2c3e50", dash="dash", width=1),
                  row=1, col=1)

    # Action annotation — centred above the panel title in the top margin
    action_colour = {"BUY": "#1a7a2e", "SELL": "#c0392b",
                     "HOLD": "#d68910", "NO_TRADE": "#7f8c8d"}.get(s.action, "#333")
    fig.add_annotation(
        xref="paper", yref="paper",
        x=0.5, y=1.07,
        text=f"{s.action} ({s.confidence:.0f}%)",
        font=dict(color=action_colour, size=13, family="Arial Black"),
        showarrow=False, xanchor="center",
    )

    # ---- Row 2: Volume ---------------------------------------------------
    fig.add_trace(go.Bar(
        x=x, y=df["volume"], name="Volume",
        marker_color=vol_color, showlegend=False,
        hovertemplate="%{x|%Y-%m-%d}<br>Vol: %{y:,.0f}<extra></extra>",
    ), row=2, col=1)

    # ---- Row 3: RSI ------------------------------------------------------
    if rsi is not None:
        fig.add_trace(go.Scatter(
            x=x, y=rsi, name="RSI(14)",
            line=dict(color="#8e44ad", width=1.2),
            hovertemplate="RSI: %{y:.1f}<extra></extra>",
        ), row=3, col=1)
        fig.add_hrect(y0=70, y1=100, fillcolor="rgba(231,76,60,0.08)",
                      line_width=0, row=3, col=1)
        fig.add_hrect(y0=0, y1=30, fillcolor="rgba(46,204,113,0.08)",
                      line_width=0, row=3, col=1)
        fig.add_hline(y=70, line=dict(color="#e74c3c", dash="dot", width=0.8), row=3, col=1)
        fig.add_hline(y=30, line=dict(color="#2ecc71", dash="dot", width=0.8), row=3, col=1)
        fig.add_hline(y=50, line=dict(color="#bdc3c7", dash="dot", width=0.6), row=3, col=1)

    # ---- Row 4: MACD -----------------------------------------------------
    if hist is not None:
        hist_colors = ["#2ecc71" if v >= 0 else "#e74c3c" for v in hist]
        fig.add_trace(go.Bar(
            x=x, y=hist, name="MACD Hist",
            marker_color=hist_colors, showlegend=True, opacity=0.6,
            hovertemplate="Hist: %{y:+.3f}<extra></extra>",
        ), row=4, col=1)

    if macd is not None:
        fig.add_trace(go.Scatter(
            x=x, y=macd, name="MACD",
            line=dict(color="#2980b9", width=1.2),
            hovertemplate="MACD: %{y:+.3f}<extra></extra>",
        ), row=4, col=1)

    if sig is not None:
        fig.add_trace(go.Scatter(
            x=x, y=sig, name="Signal",
            line=dict(color="#e67e22", width=1.2, dash="dash"),
            hovertemplate="Signal: %{y:+.3f}<extra></extra>",
        ), row=4, col=1)

    # ---- Global layout ---------------------------------------------------
    fig.update_layout(
        height=700,
        paper_bgcolor="#ffffff",
        plot_bgcolor="#fafbfc",
        font=dict(family="Segoe UI, Arial", size=11, color="#333"),
        legend=dict(orientation="h", y=1.12, x=0.5, xanchor="center", font=dict(size=10)),
        margin=dict(l=60, r=80, t=110, b=40),
        hovermode="x unified",
        xaxis=dict(showgrid=True, gridcolor="#ecf0f1"),
        xaxis2=dict(showgrid=True, gridcolor="#ecf0f1"),
        xaxis3=dict(showgrid=True, gridcolor="#ecf0f1"),
        xaxis4=dict(showgrid=True, gridcolor="#ecf0f1"),
    )
    for row in range(1, 5):
        fig.update_yaxes(showgrid=True, gridcolor="#ecf0f1", row=row, col=1)

    # RSI y-axis range
    fig.update_yaxes(range=[0, 100], row=3, col=1)

    # Separator lines between subplot panels
    domains = [
        fig.layout.yaxis.domain,
        fig.layout.yaxis2.domain,
        fig.layout.yaxis3.domain,
        fig.layout.yaxis4.domain,
    ]
    for i in range(len(domains) - 1):
        sep_y = domains[i][0]  # bottom edge of upper panel, above the title in the gap
        fig.add_shape(
            type="line", xref="paper", yref="paper",
            x0=0, x1=1, y0=sep_y, y1=sep_y,
            line=dict(color="#5b7fa6", width=1.5),
        )

    # Embed plotly.js inline (first=True) for full self-containment
    html = fig.to_html(full_html=False, include_plotlyjs=True, config={
        "displayModeBar": True,
        "modeBarButtonsToRemove": ["lasso2d", "select2d"],
        "toImageButtonOptions": {"format": "png", "filename": "slv_chart"},
    })
    return (
        '<div style="border:3px solid #5b7fa6; border-radius:8px; '
        'overflow:hidden; box-shadow:0 2px 8px rgba(0,0,0,0.07); '
        'background:#ffffff; padding:4px;">'
        + html
        + "</div>"
    )


# ---------------------------------------------------------------------------
# Matplotlib fallback (static PNG as base64 data-URI)
# ---------------------------------------------------------------------------

def _matplotlib_chart(bundle: ReportBundle) -> str:
    import matplotlib
    matplotlib.use("Agg")   # non-interactive backend; safe for server/script use
    import matplotlib.pyplot as plt
    import matplotlib.gridspec as gridspec

    df     = _prepare_df(bundle)
    sma20  = _series(df, "SMA_20")
    sma50  = _series(df, "SMA_50")
    sma200 = _series(df, "SMA_200")
    rsi    = _series(df, "RSI_14")
    macd   = _series(df, "MACD_12_26_9")
    sig    = _series(df, "MACDs_12_26_9")
    hist   = _series(df, "MACDh_12_26_9")

    fig = plt.figure(figsize=(12, 8), facecolor="#ffffff")
    gs  = gridspec.GridSpec(4, 1, height_ratios=[4, 1.2, 1.4, 1.4],
                            hspace=0.08, figure=fig)

    ax1 = fig.add_subplot(gs[0])
    ax2 = fig.add_subplot(gs[1], sharex=ax1)
    ax3 = fig.add_subplot(gs[2], sharex=ax1)
    ax4 = fig.add_subplot(gs[3], sharex=ax1)

    x = range(len(df))

    # Price
    ax1.plot(x, df["close"], color="#2c3e50", linewidth=1.2, label="Close")
    if sma20  is not None: ax1.plot(x, sma20,  color="#3498db", linewidth=0.9, label="SMA20")
    if sma50  is not None: ax1.plot(x, sma50,  color="#e67e22", linewidth=0.9, label="SMA50")
    if sma200 is not None: ax1.plot(x, sma200, color="#9b59b6", linewidth=0.9, label="SMA200")
    for lvl in bundle.tech_result.support_levels[:2]:
        ax1.axhline(lvl, color="#27ae60", linestyle=":", linewidth=0.8)
    for lvl in bundle.tech_result.resistance_levels[:2]:
        ax1.axhline(lvl, color="#c0392b", linestyle=":", linewidth=0.8)
    ax1.set_ylabel("Price ($)")
    ax1.legend(fontsize=8, loc="upper left")
    ax1.grid(True, alpha=0.3)
    ax1.set_facecolor("#fafbfc")

    # Volume
    up   = [df["close"].iloc[i] >= df["open"].iloc[i] for i in range(len(df))]
    cols = ["#2ecc71" if u else "#e74c3c" for u in up]
    ax2.bar(x, df["volume"], color=cols, width=0.8)
    ax2.set_ylabel("Vol", fontsize=8)
    ax2.grid(True, alpha=0.2)
    ax2.set_facecolor("#fafbfc")

    # RSI
    if rsi is not None:
        ax3.plot(x, rsi, color="#8e44ad", linewidth=1.0)
        ax3.axhline(70, color="#e74c3c", linestyle=":", linewidth=0.8)
        ax3.axhline(30, color="#2ecc71", linestyle=":", linewidth=0.8)
        ax3.axhline(50, color="#bdc3c7", linestyle=":", linewidth=0.5)
        ax3.fill_between(x, 70, 100, alpha=0.06, color="#e74c3c")
        ax3.fill_between(x, 0, 30, alpha=0.06, color="#2ecc71")
        ax3.set_ylim(0, 100)
    ax3.set_ylabel("RSI", fontsize=8)
    ax3.grid(True, alpha=0.2)
    ax3.set_facecolor("#fafbfc")

    # MACD
    if hist is not None:
        hist_arr = list(hist)
        cols_m = ["#2ecc71" if v >= 0 else "#e74c3c" for v in hist_arr]
        ax4.bar(x, hist_arr, color=cols_m, width=0.8, alpha=0.6)
    if macd is not None: ax4.plot(x, list(macd), color="#2980b9", linewidth=0.9, label="MACD")
    if sig  is not None: ax4.plot(x, list(sig),  color="#e67e22", linewidth=0.9,
                                  linestyle="--", label="Signal")
    ax4.axhline(0, color="#7f8c8d", linewidth=0.5)
    ax4.set_ylabel("MACD", fontsize=8)
    ax4.grid(True, alpha=0.2)
    ax4.set_facecolor("#fafbfc")

    plt.setp(ax1.get_xticklabels(), visible=False)
    plt.setp(ax2.get_xticklabels(), visible=False)
    plt.setp(ax3.get_xticklabels(), visible=False)

    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=120, bbox_inches="tight",
                facecolor="#ffffff")
    plt.close(fig)
    buf.seek(0)
    b64 = base64.b64encode(buf.read()).decode("ascii")
    return f'<img src="data:image/png;base64,{b64}" style="width:100%;max-width:900px">'


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _prepare_df(bundle: ReportBundle) -> pd.DataFrame:
    """Return the last _LOOKBACK_BARS rows with indicator columns appended."""
    df = bundle.price_data.ohlcv.tail(_LOOKBACK_BARS).copy()
    df.ta.sma(length=20,  append=True)
    df.ta.sma(length=50,  append=True)
    df.ta.sma(length=200, append=True)
    df.ta.ema(length=9,   append=True)
    df.ta.rsi(length=14,  append=True)
    df.ta.macd(fast=12, slow=26, signal=9, append=True)
    return df


def _series(df: pd.DataFrame, col: str) -> Optional[list]:
    """Return a column as a plain Python list, or None if absent / all-NaN."""
    if col not in df.columns:
        return None
    s = df[col]
    if s.isna().all():
        return None
    return s.tolist()


def _add_ma(fig, x, values, colour: str, name: str) -> None:
    """Add a moving-average line trace to row 1 of `fig`."""
    if values is None:
        return
    import plotly.graph_objects as go
    fig.add_trace(go.Scatter(
        x=x, y=values, name=name,
        line=dict(color=colour, width=1.0, dash="solid"),
        hovertemplate=f"{name}: $%{{y:.2f}}<extra></extra>",
    ), row=1, col=1)
