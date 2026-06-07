# Rev 1
"""
Volume metric calculations: relative volume, VROC, OBV trend.
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

import pandas as pd
import pandas_ta as ta  # noqa: F401 — registers the .ta accessor on DataFrame

from modules.analysis.technical.indicators import _filter_to_date, _cf
from modules.infrastructure.logger import get_logger

log = get_logger("volume_analysis")

_AVG_WINDOW = 20    # bars for average volume baseline
_VROC_PERIOD = 14   # bars for Volume Rate of Change


def calculate_volume_metrics(
    df: pd.DataFrame,
    analysis_date: datetime,
) -> tuple[dict, list[str]]:
    """
    Calculate volume-based metrics up to `analysis_date`.
    Returns (metrics_dict, warnings_list).
    """
    warnings: list[str] = []
    work = _filter_to_date(df, analysis_date)

    if len(work) < _AVG_WINDOW + 1:
        return {}, [f"Insufficient data for volume analysis (need >= {_AVG_WINDOW + 1} bars)"]

    vol = work["volume"]

    current_vol = _cf(vol.iloc[-1])
    avg_vol = _cf(vol.tail(_AVG_WINDOW + 1).iloc[:-1].mean())    # average of prior N bars

    # Relative volume: how does today compare to recent average?
    relative_volume: Optional[float] = None
    if current_vol and avg_vol and avg_vol > 0:
        relative_volume = current_vol / avg_vol

    # Volume Rate of Change
    vroc: Optional[float] = None
    if len(work) > _VROC_PERIOD:
        vol_now = vol.iloc[-1]
        vol_then = vol.iloc[-1 - _VROC_PERIOD]
        if vol_then and vol_then > 0:
            vroc = float((vol_now - vol_then) / vol_then * 100)

    # OBV and its short-term trend direction
    obv_trend = _obv_trend(work)

    metrics = {
        "current_volume":   current_vol,
        "avg_volume":       avg_vol,
        "relative_volume":  relative_volume,
        "vroc":             vroc,
        "obv_trend":        obv_trend,
    }

    if relative_volume is None:
        warnings.append("Relative volume could not be computed")

    return metrics, warnings


def _obv_trend(work: pd.DataFrame, lookback: int = 10) -> str:
    """
    Classify OBV direction over the last `lookback` bars.
    Returns 'rising', 'falling', or 'flat'.
    """
    try:
        obv = work.ta.obv()
        if obv is None or obv.dropna().empty:
            return "unknown"
        recent = obv.dropna().tail(lookback)
        if len(recent) < 2:
            return "unknown"
        # Linear regression slope sign
        slope = (recent.iloc[-1] - recent.iloc[0]) / len(recent)
        if slope > 0:
            return "rising"
        if slope < 0:
            return "falling"
        return "flat"
    except Exception as exc:
        log.debug("OBV trend calculation failed: %s", exc)
        return "unknown"
