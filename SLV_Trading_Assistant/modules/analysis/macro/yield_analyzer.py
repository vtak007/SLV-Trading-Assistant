# Rev 1
"""
Real yield and nominal yield pressure analysis.
Silver (and gold) are most sensitive to real yields (DGS10 - T10YIE breakeven).
Negative real yields are the strongest macro tailwind for precious metals.
"""
from __future__ import annotations

from datetime import datetime

import pandas as pd

from modules.infrastructure.logger import get_logger
from modules.reporting.models import MacroDriverScore

log = get_logger("yield_analyzer")

_REAL_YIELD_NEGATIVE   = 0.0   # negative real yield = very bullish
_REAL_YIELD_LOW        = 1.0   # low positive = still bullish
_REAL_YIELD_MODERATE   = 2.0   # moderate = neutral territory

_TREND_DAYS = 63  # ~3 months of trading days


def _filter(series: pd.Series, analysis_date: datetime) -> pd.Series:
    if series.empty:
        return series
    cutoff = pd.Timestamp(analysis_date.date())
    return series[series.index <= cutoff]


def analyze_real_yield(
    dgs10: pd.Series,
    t10yie: pd.Series,
    analysis_date: datetime,
) -> MacroDriverScore:
    """Score SLV macro outlook from real yields (DGS10 minus T10YIE breakeven)."""
    dgs10_f  = _filter(dgs10,  analysis_date)
    t10yie_f = _filter(t10yie, analysis_date)

    if dgs10_f.empty or t10yie_f.empty:
        return MacroDriverScore(
            driver_name="Real Yield",
            score="unknown",
            value=None,
            evidence="Insufficient FRED data for real yield calculation",
            weight=0.25,
        )

    real = (dgs10_f - t10yie_f).dropna()
    if real.empty:
        return MacroDriverScore(
            driver_name="Real Yield",
            score="unknown",
            value=None,
            evidence="DGS10 and T10YIE series could not be aligned on common dates",
            weight=0.25,
        )

    current  = float(real.iloc[-1])
    window   = real.iloc[-_TREND_DAYS:] if len(real) >= _TREND_DAYS else real
    avg_3m   = float(window.mean())
    trend    = (
        "falling" if current < avg_3m - 0.10 else
        "rising"  if current > avg_3m + 0.10 else
        "stable"
    )

    if current < _REAL_YIELD_NEGATIVE:
        score, label = "bullish", "negative"
    elif current < _REAL_YIELD_LOW:
        score, label = "bullish", "low positive"
    elif current < _REAL_YIELD_MODERATE:
        score, label = "neutral", "moderate"
    else:
        score, label = "bearish", "elevated"

    evidence = (
        f"Real yield: {current:.2f}% ({label}); "
        f"3-month avg: {avg_3m:.2f}%; trend: {trend}"
    )
    log.debug("Real yield score: %s | %s", score, evidence)
    return MacroDriverScore(
        driver_name="Real Yield",
        score=score,
        value=current,
        evidence=evidence,
        weight=0.25,
    )


def analyze_nominal_yield(
    dgs10: pd.Series,
    analysis_date: datetime,
) -> MacroDriverScore:
    """Score SLV from the 3-month trend in the 10-year nominal Treasury yield."""
    series = _filter(dgs10, analysis_date)

    if series.empty:
        return MacroDriverScore(
            driver_name="Nominal Yield Trend",
            score="unknown",
            value=None,
            evidence="DGS10 data unavailable",
            weight=0.10,
        )

    current = float(series.iloc[-1])
    window  = series.iloc[-_TREND_DAYS:] if len(series) >= _TREND_DAYS else series
    change  = float(window.iloc[-1]) - float(window.iloc[0]) if len(window) > 1 else 0.0

    if change < -0.30:
        score, direction = "bullish", "falling sharply"
    elif change < 0.0:
        score, direction = "bullish", "falling"
    elif change < 0.30:
        score, direction = "neutral", "stable"
    else:
        score, direction = "bearish", "rising"

    evidence = (
        f"DGS10: {current:.2f}%; "
        f"3-month change: {change:+.2f}pp ({direction})"
    )
    return MacroDriverScore(
        driver_name="Nominal Yield Trend",
        score=score,
        value=current,
        evidence=evidence,
        weight=0.10,
    )
