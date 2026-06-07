# Rev 1
"""
Fed policy stance classifier from the FEDFUNDS effective rate.
Cutting cycles are bullish for silver; hiking/restrictive cycles are bearish.
"""
from __future__ import annotations

from datetime import datetime

import pandas as pd

from modules.infrastructure.logger import get_logger
from modules.reporting.models import MacroDriverScore

log = get_logger("fed_policy_analyzer")

_TREND_DAYS    = 63    # ~3 months
_CUT_THRESHOLD = -0.10  # 10bp fall over 3 months = cutting cycle underway
_HIKE_THRESHOLD = 0.10  # 10bp rise over 3 months = hiking cycle underway
_RESTRICTIVE_FLOOR = 4.5  # Fed Funds >= 4.5% = restrictive even if pausing


def _filter(series: pd.Series, analysis_date: datetime) -> pd.Series:
    if series.empty:
        return series
    cutoff = pd.Timestamp(analysis_date.date())
    return series[series.index <= cutoff]


def analyze_fed_policy(
    fedfunds: pd.Series,
    analysis_date: datetime,
) -> MacroDriverScore:
    """Classify Fed stance and score its impact on silver."""
    series = _filter(fedfunds, analysis_date)

    if series.empty:
        return MacroDriverScore(
            driver_name="Fed Policy",
            score="unknown",
            value=None,
            evidence="FEDFUNDS data unavailable",
            weight=0.10,
        )

    current = float(series.iloc[-1])
    # Use a calendar-based 3-month window so monthly and daily series are treated equally.
    three_months_ago = series.index[-1] - pd.DateOffset(months=3)
    window = series[series.index >= three_months_ago]
    if len(window) < 2:
        window = series.iloc[-3:] if len(series) >= 3 else series
    change  = float(window.iloc[-1]) - float(window.iloc[0]) if len(window) > 1 else 0.0

    if change < _CUT_THRESHOLD:
        score, stance = "bullish", "cutting cycle"
    elif change > _HIKE_THRESHOLD:
        score, stance = "bearish", "hiking cycle"
    elif current >= _RESTRICTIVE_FLOOR:
        score, stance = "bearish", "elevated/restrictive (pausing)"
    elif current >= 2.0:
        score, stance = "neutral", "neutral/pausing"
    else:
        score, stance = "bullish", "accommodative"

    evidence = (
        f"Fed Funds: {current:.2f}%; "
        f"3-month change: {change:+.2f}pp; stance: {stance}"
    )
    return MacroDriverScore(
        driver_name="Fed Policy",
        score=score,
        value=current,
        evidence=evidence,
        weight=0.10,
    )
