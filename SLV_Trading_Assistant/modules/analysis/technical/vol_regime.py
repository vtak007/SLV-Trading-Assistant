# Rev 2  (Schwab IV percentile as primary; ATR percentile as fallback)
"""
Volatility regime classification.
Primary: IV percentile from Schwab options chain (when available).
Fallback: ATR percentile from price history.
Regime labels: low / normal / high / extreme.
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional, TYPE_CHECKING

import pandas as pd
import pandas_ta as ta  # noqa: F401 — registers the .ta accessor on DataFrame

from modules.analysis.technical.indicators import _filter_to_date
from modules.infrastructure.logger import get_logger

if TYPE_CHECKING:
    from modules.reporting.models import OptionsData

log = get_logger("vol_regime")

_ATR_LENGTH = 14
_LOOKBACK = 252     # ~1 trading year for percentile window

# Shared percentile thresholds (used for both IV- and ATR-based classification)
_LOW_THRESHOLD    = 25.0
_NORMAL_THRESHOLD = 75.0
_HIGH_THRESHOLD   = 90.0


def classify_vol_regime(
    df: pd.DataFrame,
    analysis_date: datetime,
    lookback: int = _LOOKBACK,
    options_data: Optional["OptionsData"] = None,
) -> tuple[str, list[str]]:
    """
    Classify volatility regime and return (label, warnings).
    Uses IV percentile from Schwab options when available; falls back to ATR percentile.
    """
    # --- IV-based classification (preferred when Schwab options are available) ---
    if (
        options_data is not None
        and options_data.is_available
        and options_data.iv_percentile >= 0
    ):
        pct = options_data.iv_percentile
        regime = _label_from_percentile(pct)
        log.debug(
            "Vol regime (IV): %s  ATM_IV=%.1f%%  iv_pct=%.1f",
            regime, options_data.atm_iv * 100, pct,
        )
        warnings = list(options_data.warnings)
        return regime, warnings

    # --- ATR-based fallback ---
    return _classify_via_atr(df, analysis_date, lookback)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _label_from_percentile(percentile: float) -> str:
    if percentile < _LOW_THRESHOLD:
        return "low"
    if percentile < _NORMAL_THRESHOLD:
        return "normal"
    if percentile < _HIGH_THRESHOLD:
        return "high"
    return "extreme"


def _classify_via_atr(
    df: pd.DataFrame, analysis_date: datetime, lookback: int
) -> tuple[str, list[str]]:
    """ATR-percentile vol regime (original implementation)."""
    warnings: list[str] = []
    work = _filter_to_date(df, analysis_date)

    if len(work) < _ATR_LENGTH + 5:
        return "unknown", ["Insufficient data for vol regime (need >= 19 bars)"]

    atr_series = work.ta.atr(length=_ATR_LENGTH)
    if atr_series is None:
        return "unknown", ["ATR calculation returned None"]

    if isinstance(atr_series, pd.DataFrame):
        atr_series = atr_series[atr_series.columns[0]]

    atr_clean = atr_series.dropna()
    if atr_clean.empty:
        return "unknown", ["ATR series contains no valid values"]

    window = atr_clean.tail(lookback)
    current_atr = float(atr_clean.iloc[-1])
    percentile = float((window < current_atr).mean() * 100)

    if len(work) < lookback:
        warnings.append(
            f"Vol regime uses {len(work)} bars (ideal is {lookback}); percentile may be less reliable"
        )

    regime = _label_from_percentile(percentile)
    log.debug(
        "Vol regime (ATR): %s  ATR=%.3f  pct=%.1f  window=%d bars",
        regime, current_atr, percentile, len(window),
    )
    return regime, warnings
