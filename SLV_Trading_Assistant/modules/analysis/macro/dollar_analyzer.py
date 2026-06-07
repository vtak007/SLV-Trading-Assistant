# Rev 1
"""
Dollar strength analysis using the DTWEXBGS broad nominal USD index.
Rising dollar is bearish for silver (priced in USD, inverse relationship holds strongly).
"""
from __future__ import annotations

from datetime import datetime

import pandas as pd

from modules.infrastructure.logger import get_logger
from modules.reporting.models import MacroDriverScore

log = get_logger("dollar_analyzer")

_TREND_DAYS = 63  # ~3 months


def _filter(series: pd.Series, analysis_date: datetime) -> pd.Series:
    if series.empty:
        return series
    cutoff = pd.Timestamp(analysis_date.date())
    return series[series.index <= cutoff]


def analyze_dollar(
    dtwexbgs: pd.Series,
    analysis_date: datetime,
) -> MacroDriverScore:
    """Score SLV macro outlook from USD broad index trend."""
    series = _filter(dtwexbgs, analysis_date)

    if series.empty:
        return MacroDriverScore(
            driver_name="US Dollar",
            score="unknown",
            value=None,
            evidence="DTWEXBGS data unavailable",
            weight=0.20,
        )

    current   = float(series.iloc[-1])
    window    = series.iloc[-_TREND_DAYS:] if len(series) >= _TREND_DAYS else series
    start_val = float(window.iloc[0])
    chg_pct   = ((current - start_val) / start_val) * 100 if start_val != 0 else 0.0

    if chg_pct < -2.0:
        score, direction = "bullish", "weakening"
    elif chg_pct < 0.0:
        score, direction = "bullish", "slightly weakening"
    elif chg_pct < 2.0:
        score, direction = "neutral", "stable"
    else:
        score, direction = "bearish", "strengthening"

    evidence = (
        f"USD Index (DTWEXBGS): {current:.2f}; "
        f"3-month change: {chg_pct:+.1f}% ({direction})"
    )
    return MacroDriverScore(
        driver_name="US Dollar",
        score=score,
        value=current,
        evidence=evidence,
        weight=0.20,
    )
