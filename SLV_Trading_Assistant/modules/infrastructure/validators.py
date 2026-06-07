# Rev 1
"""OHLCV DataFrame validation: shape, column presence, type, and range checks."""
from __future__ import annotations

import pandas as pd

from modules.infrastructure.exceptions import ValidationError
from modules.infrastructure.logger import get_logger

log = get_logger("validators")

_REQUIRED_COLUMNS = {"open", "high", "low", "close", "volume"}
_MAX_NAN_RATIO = 0.10   # reject if >10% of any required column is NaN


def validate_ohlcv(df: pd.DataFrame, ticker: str = "") -> None:
    """
    Raise ValidationError if df fails any OHLCV sanity check.
    Normalises column names to lowercase before checking.
    """
    label = f"[{ticker}] " if ticker else ""

    if df is None or df.empty:
        raise ValidationError(f"{label}DataFrame is empty or None")

    cols_lower = set(df.columns.str.lower())
    missing = _REQUIRED_COLUMNS - cols_lower
    if missing:
        raise ValidationError(f"{label}Missing required columns: {missing}")

    # Work on a lowercase-column copy to avoid mutating caller's df
    work = df.copy()
    work.columns = work.columns.str.lower()

    for col in _REQUIRED_COLUMNS:
        nan_ratio = work[col].isna().mean()
        if nan_ratio > _MAX_NAN_RATIO:
            raise ValidationError(
                f"{label}'{col}' has {nan_ratio:.1%} NaN values (max allowed {_MAX_NAN_RATIO:.0%})"
            )

    for col in ("open", "high", "low", "close"):
        if (work[col].dropna() <= 0).any():
            raise ValidationError(f"{label}'{col}' contains non-positive prices")

    bad_hl = work["high"] < work["low"]
    if bad_hl.any():
        raise ValidationError(f"{label}{bad_hl.sum()} rows where high < low")

    log.debug("%sOHLCV validation passed (%d rows)", label, len(df))
