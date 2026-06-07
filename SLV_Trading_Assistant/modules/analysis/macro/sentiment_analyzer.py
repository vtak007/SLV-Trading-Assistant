# Rev 1
"""
Market sentiment analysis via VIXY (VIX Short-Term Futures ETF proxy for ^VIX).
Moderate fear (elevated VIXY) drives safe-haven demand, which is bullish for silver.
Panic levels (extreme VIXY) often trigger liquidation -- neutral/negative for silver.
"""
from __future__ import annotations

from datetime import datetime

import pandas as pd

from modules.infrastructure.logger import get_logger
from modules.reporting.models import MacroDriverScore

log = get_logger("sentiment_analyzer")

_TREND_DAYS      = 21   # ~1 month -- sentiment changes faster than macro
_PANIC_THRESHOLD = 40.0  # panic/liquidation regime
_FEAR_THRESHOLD  = 25.0  # elevated fear -- safe-haven demand
_CALM_THRESHOLD  = 15.0  # risk-on complacency -- low demand for safe havens


def _filter(series: pd.Series, analysis_date: datetime) -> pd.Series:
    if series.empty:
        return series
    cutoff = pd.Timestamp(analysis_date.date())
    return series[series.index <= cutoff]


def analyze_sentiment(
    vixy_close: pd.Series,
    analysis_date: datetime,
) -> MacroDriverScore:
    """Score SLV macro outlook from VIXY (VIX proxy) level and trend."""
    series = _filter(vixy_close, analysis_date)

    if series.empty:
        return MacroDriverScore(
            driver_name="Market Sentiment",
            score="unknown",
            value=None,
            evidence="VIXY price data unavailable",
            weight=0.05,
        )

    current = float(series.iloc[-1])
    window  = series.iloc[-_TREND_DAYS:] if len(series) >= _TREND_DAYS else series
    avg     = float(window.mean())
    trend   = (
        "spiking" if current > avg * 1.20 else
        "falling" if current < avg * 0.85 else
        "stable"
    )

    if current >= _PANIC_THRESHOLD:
        score, regime = "neutral", "panic/liquidation (risk-off -- forced selling)"
    elif current >= _FEAR_THRESHOLD:
        score, regime = "bullish", "elevated fear (safe-haven demand)"
    elif current <= _CALM_THRESHOLD:
        score, regime = "neutral", "risk-on/complacency (low safe-haven demand)"
    else:
        score, regime = "neutral", "normal"

    evidence = (
        f"VIXY: {current:.2f} ({regime}); "
        f"1-month avg: {avg:.2f}; trend: {trend}"
    )
    return MacroDriverScore(
        driver_name="Market Sentiment",
        score=score,
        value=current,
        evidence=evidence,
        weight=0.05,
    )
