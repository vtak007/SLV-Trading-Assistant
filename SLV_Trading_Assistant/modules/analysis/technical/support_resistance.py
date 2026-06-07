# Rev 1
"""
Support and resistance level identification via rolling pivot points.
"""
from __future__ import annotations

from datetime import datetime

import pandas as pd

from modules.analysis.technical.indicators import _filter_to_date
from modules.infrastructure.logger import get_logger

log = get_logger("support_resistance")

_LOOKBACK = 120         # bars to scan for pivots
_PIVOT_WINDOW = 5       # bars each side to confirm a local extreme
_MAX_LEVELS = 5         # maximum levels to return per side
_PROXIMITY_PCT = 0.005  # merge levels within 0.5% of each other


def find_levels(
    df: pd.DataFrame,
    analysis_date: datetime,
    lookback: int = _LOOKBACK,
) -> tuple[list[float], list[float], list[str]]:
    """
    Find pivot-based support and resistance levels up to `analysis_date`.
    Returns (support_levels, resistance_levels, warnings).
    Both lists are sorted: support descending (nearest first), resistance ascending.
    """
    warnings: list[str] = []
    work = _filter_to_date(df, analysis_date).tail(lookback)

    if len(work) < _PIVOT_WINDOW * 2 + 1:
        return [], [], ["Insufficient data for support/resistance identification"]

    current_price = float(work["close"].iloc[-1])
    highs = work["high"].values
    lows  = work["low"].values
    n     = len(work)
    pw    = _PIVOT_WINDOW

    pivot_highs: list[float] = []
    pivot_lows:  list[float] = []

    for i in range(pw, n - pw):
        if highs[i] == max(highs[i - pw : i + pw + 1]):
            pivot_highs.append(float(highs[i]))
        if lows[i] == min(lows[i - pw : i + pw + 1]):
            pivot_lows.append(float(lows[i]))

    # Filter: resistance above current price, support below
    resistance = _cluster(
        [h for h in pivot_highs if h > current_price * 1.002]
    )
    support = _cluster(
        [l for l in pivot_lows  if l < current_price * 0.998]
    )

    resistance = sorted(resistance)[:_MAX_LEVELS]
    support    = sorted(support, reverse=True)[:_MAX_LEVELS]

    log.debug(
        "S/R at %.2f: support=%s resistance=%s",
        current_price,
        [f"{s:.2f}" for s in support],
        [f"{r:.2f}" for r in resistance],
    )
    return support, resistance, warnings


def _cluster(levels: list[float]) -> list[float]:
    """Merge levels that are within _PROXIMITY_PCT of each other (keep the average)."""
    if not levels:
        return []
    sorted_levels = sorted(set(levels))
    clusters: list[list[float]] = [[sorted_levels[0]]]
    for lvl in sorted_levels[1:]:
        if (lvl - clusters[-1][-1]) / clusters[-1][-1] <= _PROXIMITY_PCT:
            clusters[-1].append(lvl)
        else:
            clusters.append([lvl])
    return [sum(c) / len(c) for c in clusters]
