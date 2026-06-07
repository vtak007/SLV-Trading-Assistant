# Rev 1
"""
Gold-silver ratio analysis.
High ratio = silver cheap relative to gold; mean-reversion argument favours silver.
Uses GLD and SLV close prices from the price fetcher (already in Layer 1).
"""
from __future__ import annotations

from datetime import datetime

import pandas as pd

from modules.infrastructure.logger import get_logger
from modules.reporting.models import MacroDriverScore

log = get_logger("gs_ratio_analyzer")

_TREND_DAYS      = 63    # ~3 months

# Thresholds are for the GLD/SLV ETF price ratio (not the spot G/S metal ratio).
# GLD holds ~0.0968 oz gold/share; SLV holds ~0.84 oz silver/share (after expense drag).
# ETF ratio = spot_G/S_ratio * (GLD_oz_per_share / SLV_oz_per_share) ~= spot_ratio * 0.115
# Spot averages: avg ~70 -> ETF ~8.0; extreme high ~100 -> ETF ~11.5; extreme low ~45 -> ETF ~5.2
_HISTORICAL_HIGH = 11.5   # ETF ratio -- silver very cheap vs gold (spot G/S ~100+)
_HISTORICAL_AVG  = 8.0    # ETF ratio -- near long-run average (spot G/S ~70)
_HISTORICAL_LOW  = 5.2    # ETF ratio -- silver relatively expensive (spot G/S ~45)


def _filter(series: pd.Series, analysis_date: datetime) -> pd.Series:
    if series.empty:
        return series
    cutoff = pd.Timestamp(analysis_date.date())
    return series[series.index <= cutoff]


def analyze_gs_ratio(
    gld_close: pd.Series,
    slv_close: pd.Series,
    analysis_date: datetime,
) -> MacroDriverScore:
    """Score silver macro outlook from the gold-silver price ratio."""
    gld = _filter(gld_close, analysis_date)
    slv = _filter(slv_close, analysis_date)

    if gld.empty or slv.empty:
        return MacroDriverScore(
            driver_name="Gold-Silver Ratio",
            score="unknown",
            value=None,
            evidence="GLD or SLV price data unavailable",
            weight=0.07,
        )

    ratio = (gld / slv).dropna()
    if ratio.empty:
        return MacroDriverScore(
            driver_name="Gold-Silver Ratio",
            score="unknown",
            value=None,
            evidence="G/S ratio could not be computed (no overlapping dates)",
            weight=0.07,
        )

    current = float(ratio.iloc[-1])
    avg_1y  = float(ratio.iloc[-252:].mean()) if len(ratio) >= 252 else float(ratio.mean())
    window  = ratio.iloc[-_TREND_DAYS:] if len(ratio) >= _TREND_DAYS else ratio
    trend_delta = float(window.iloc[-1]) - float(window.iloc[0]) if len(window) > 1 else 0.0
    trend = (
        "rising"  if trend_delta > 2.0  else
        "falling" if trend_delta < -2.0 else
        "stable"
    )

    if current > _HISTORICAL_HIGH:
        score, label = "bullish", "extreme (silver very cheap)"
    elif current > _HISTORICAL_AVG:
        score, label = "bullish", "elevated (silver undervalued)"
    elif current > _HISTORICAL_LOW:
        score, label = "neutral", "near historical average"
    else:
        score, label = "bearish", "low (silver relatively expensive)"

    evidence = (
        f"G/S Ratio: {current:.1f} ({label}); "
        f"1-year avg: {avg_1y:.1f}; 3-month trend: {trend}"
    )
    return MacroDriverScore(
        driver_name="Gold-Silver Ratio",
        score=score,
        value=current,
        evidence=evidence,
        weight=0.07,
    )
