# Rev 1
"""
Technical indicator calculations via pandas-ta.
All functions accept an explicit analysis_date to enforce anti-look-ahead discipline.
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

import pandas as pd
import pandas_ta as ta  # noqa: F401 — registers the .ta accessor on DataFrame

from modules.infrastructure.exceptions import ValidationError
from modules.infrastructure.logger import get_logger

log = get_logger("indicators")

_MIN_BARS_MACD = 35     # 26 slow + 9 signal
_MIN_BARS_IDEAL = 200   # enough for SMA(200)


def calculate_indicators(
    df: pd.DataFrame,
    analysis_date: datetime,
) -> tuple[dict, list[str]]:
    """
    Calculate all technical indicators on `df` up to and including `analysis_date`.
    Returns (indicators_dict, warnings_list).
    indicator values are float or None (never NaN).
    """
    warnings: list[str] = []

    work = _filter_to_date(df, analysis_date)
    n = len(work)

    if n < _MIN_BARS_MACD:
        raise ValidationError(
            f"Only {n} bars available — need >= {_MIN_BARS_MACD} for MACD"
        )
    if n < _MIN_BARS_IDEAL:
        warnings.append(f"Only {n} bars available — SMA(200) will be unavailable")

    # --- compute all indicators (append to copy) ---
    work = work.copy()
    work.ta.sma(length=20,  append=True)
    work.ta.sma(length=50,  append=True)
    work.ta.sma(length=200, append=True)
    work.ta.ema(length=9,   append=True)
    work.ta.ema(length=21,  append=True)
    work.ta.rsi(length=14,  append=True)
    work.ta.macd(fast=12, slow=26, signal=9, append=True)
    work.ta.bbands(length=20, std=2, append=True)
    work.ta.atr(length=14,  append=True)

    def _get(prefix: str) -> Optional[float]:
        return _get_col(work, prefix)

    indicators = {
        "close":       _cf(work["close"].iloc[-1]),
        "volume":      _cf(work["volume"].iloc[-1]),
        "sma_20":      _get("SMA_20"),
        "sma_50":      _get("SMA_50"),
        "sma_200":     _get("SMA_200"),
        "ema_9":       _get("EMA_9"),
        "ema_21":      _get("EMA_21"),
        "rsi_14":      _get("RSI_14"),
        # MACD_ prefix is exclusive (MACDh_ and MACDs_ don't match "MACD_")
        "macd":        _get("MACD_"),
        "macd_signal": _get("MACDs_"),
        "macd_hist":   _get("MACDh_"),
        "bb_upper":    _get("BBU_"),
        "bb_middle":   _get("BBM_"),
        "bb_lower":    _get("BBL_"),
        "bb_pct":      _get("BBP_"),
        "bb_bw":       _get("BBB_"),
        # ATRr_ = Wilder's RMA (pandas-ta default); fallback to ATR_ (EMA-based)
        "atr_14":      _get("ATRr_") or _get("ATR_"),
    }

    if indicators["sma_200"] is None:
        warnings.append("SMA(200) unavailable — need >= 200 bars")

    return indicators, warnings


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _filter_to_date(df: pd.DataFrame, analysis_date: datetime) -> pd.DataFrame:
    # Always compare on date() to avoid tz-naive vs tz-aware mismatch
    # (yfinance returns tz-naive DatetimeIndex; analysis_date may be tz-aware)
    cutoff_date = pd.Timestamp(analysis_date).date()
    return df[df.index.date <= cutoff_date]


def _get_col(work: pd.DataFrame, prefix: str) -> Optional[float]:
    """Return latest value from the first column whose name starts with `prefix`."""
    matching = [c for c in work.columns if c.startswith(prefix)]
    if not matching:
        return None
    return _cf(work[matching[0]].iloc[-1])


def _cf(val) -> Optional[float]:
    """Convert a possibly-NaN scalar to float or None."""
    if val is None:
        return None
    try:
        f = float(val)
        return None if pd.isna(f) else f
    except (TypeError, ValueError):
        return None
