# Rev 1
"""
CPI and PPI inflation analysis.
High/rising inflation is bullish for silver as a real-asset inflation hedge.
FRED data for CPIAUCSL and PPIFIS lags ~1 month -- this is expected, not an error.
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

import pandas as pd

from modules.infrastructure.logger import get_logger
from modules.reporting.models import MacroDriverScore

log = get_logger("inflation_analyzer")


def _filter(series: pd.Series, analysis_date: datetime) -> pd.Series:
    if series.empty:
        return series
    cutoff = pd.Timestamp(analysis_date.date())
    return series[series.index <= cutoff]


def _yoy_pct(series: pd.Series) -> Optional[float]:
    """YoY percentage change of latest observation vs 12 months prior."""
    if len(series) < 13:
        return None
    prior = float(series.iloc[-13])
    if prior == 0:
        return None
    return ((float(series.iloc[-1]) - prior) / abs(prior)) * 100.0


def _mom_pct(series: pd.Series) -> Optional[float]:
    """Month-over-month percentage change of latest observation."""
    if len(series) < 2:
        return None
    prior = float(series.iloc[-2])
    if prior == 0:
        return None
    return ((float(series.iloc[-1]) - prior) / abs(prior)) * 100.0


def analyze_cpi(cpi: pd.Series, analysis_date: datetime) -> MacroDriverScore:
    """Score CPI inflation level. Levels above 2.5% are bullish for silver."""
    series = _filter(cpi, analysis_date)

    if series.empty:
        return MacroDriverScore(
            driver_name="CPI Inflation",
            score="unknown",
            value=None,
            evidence="CPIAUCSL data unavailable",
            weight=0.15,
        )

    yoy = _yoy_pct(series)
    if yoy is None:
        return MacroDriverScore(
            driver_name="CPI Inflation",
            score="unknown",
            value=float(series.iloc[-1]),
            evidence=f"Insufficient history for YoY (latest: {series.index[-1].strftime('%Y-%m')})",
            weight=0.15,
        )

    mom = _mom_pct(series)
    latest_label = series.index[-1].strftime("%Y-%m")
    mom_str = f"; MoM: {mom:+.2f}%" if mom is not None else ""

    if yoy > 4.0:
        score, level = "bullish", "high"
    elif yoy > 2.5:
        score, level = "bullish", "above target"
    elif yoy > 1.5:
        score, level = "neutral", "near target"
    else:
        score, level = "bearish", "below target"

    evidence = (
        f"CPI YoY: {yoy:.1f}% ({level}){mom_str}; "
        f"latest data: {latest_label} (FRED ~1mo lag expected)"
    )
    return MacroDriverScore(
        driver_name="CPI Inflation",
        score=score,
        value=yoy,
        evidence=evidence,
        weight=0.15,
    )


def analyze_ppi(ppi: pd.Series, analysis_date: datetime) -> MacroDriverScore:
    """Score PPI. Rising PPI leads CPI -- a leading indicator for inflationary pressure."""
    series = _filter(ppi, analysis_date)

    if series.empty:
        return MacroDriverScore(
            driver_name="PPI Inflation",
            score="unknown",
            value=None,
            evidence="PPIFIS data unavailable",
            weight=0.08,
        )

    yoy = _yoy_pct(series)
    if yoy is None:
        return MacroDriverScore(
            driver_name="PPI Inflation",
            score="unknown",
            value=float(series.iloc[-1]),
            evidence=f"Insufficient history for YoY (latest: {series.index[-1].strftime('%Y-%m')})",
            weight=0.08,
        )

    mom = _mom_pct(series)
    latest_label = series.index[-1].strftime("%Y-%m")
    mom_str = f"; MoM: {mom:+.2f}%" if mom is not None else ""

    if yoy > 3.0:
        score, level = "bullish", "elevated"
    elif yoy > 1.0:
        score, level = "neutral", "moderate"
    else:
        score, level = "bearish", "subdued"

    evidence = (
        f"PPI YoY: {yoy:.1f}% ({level}){mom_str}; "
        f"latest: {latest_label}"
    )
    return MacroDriverScore(
        driver_name="PPI Inflation",
        score=score,
        value=yoy,
        evidence=evidence,
        weight=0.08,
    )
