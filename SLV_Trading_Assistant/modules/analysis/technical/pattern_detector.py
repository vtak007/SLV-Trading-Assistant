# Rev 1
"""
Simple rule-based pattern detection: crossovers, breakouts, pullbacks, RSI extremes.
Patterns are returned as short label strings for use in the report.
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

import pandas as pd
import pandas_ta as ta  # noqa: F401 — registers the .ta accessor on DataFrame

from modules.analysis.technical.indicators import _filter_to_date
from modules.infrastructure.logger import get_logger

log = get_logger("pattern_detector")

_CROSS_LOOKBACK  = 5    # bars to look back for a crossover event
_BREAKOUT_PCT    = 0.005  # price must be > level by 0.5% to count as breakout
_PULLBACK_PCT    = 0.015  # price within 1.5% of level counts as pullback/test


def detect_patterns(
    df: pd.DataFrame,
    indicators: dict,
    support_levels: list[float],
    resistance_levels: list[float],
    analysis_date: datetime,
) -> list[str]:
    """
    Detect technical patterns. Returns a list of pattern label strings.
    """
    patterns: list[str] = []
    work = _filter_to_date(df, analysis_date)

    close  = indicators.get("close") or 0.0
    sma_50 = indicators.get("sma_50")
    sma_200 = indicators.get("sma_200")
    rsi    = indicators.get("rsi_14")

    # --- Golden / Death cross (SMA50 vs SMA200, recent crossover) ---
    if sma_50 is not None and sma_200 is not None:
        cross = _check_ma_cross(work, 50, 200, analysis_date)
        if cross:
            patterns.append(cross)

    # --- RSI extremes ---
    if rsi is not None:
        if rsi >= 70:
            patterns.append("rsi_overbought")
        elif rsi <= 30:
            patterns.append("rsi_oversold")

    # --- Breakout above nearest resistance ---
    if resistance_levels:
        nearest_res = resistance_levels[0]
        if close > nearest_res * (1 + _BREAKOUT_PCT):
            patterns.append("resistance_breakout")

    # --- Breakdown below nearest support ---
    if support_levels:
        nearest_sup = support_levels[0]
        if close < nearest_sup * (1 - _BREAKOUT_PCT):
            patterns.append("support_breakdown")

    # --- Pullback to support (potential long entry) ---
    for sup in support_levels[:3]:
        if abs(close - sup) / sup <= _PULLBACK_PCT:
            patterns.append("pullback_to_support")
            break

    # --- Test of resistance from below ---
    for res in resistance_levels[:3]:
        if abs(close - res) / res <= _PULLBACK_PCT:
            patterns.append("testing_resistance")
            break

    return patterns


def _check_ma_cross(
    work: pd.DataFrame,
    fast_len: int,
    slow_len: int,
    analysis_date: datetime,
) -> Optional[str]:
    """
    Return 'golden_cross' or 'death_cross' if a crossover occurred
    within the last _CROSS_LOOKBACK bars, else None.
    """
    min_bars = slow_len + _CROSS_LOOKBACK + 1
    if len(work) < min_bars:
        return None

    try:
        window = work.tail(min_bars).copy()
        window.ta.sma(length=fast_len, append=True)
        window.ta.sma(length=slow_len, append=True)

        fast_col = next((c for c in window.columns if c == f"SMA_{fast_len}"), None)
        slow_col = next((c for c in window.columns if c == f"SMA_{slow_len}"), None)
        if fast_col is None or slow_col is None:
            return None

        fast = window[fast_col].dropna()
        slow = window[slow_col].dropna()
        common = fast.index.intersection(slow.index)
        if len(common) < _CROSS_LOOKBACK + 1:
            return None

        recent_fast = fast.loc[common].tail(_CROSS_LOOKBACK + 1)
        recent_slow = slow.loc[common].tail(_CROSS_LOOKBACK + 1)

        for i in range(1, len(recent_fast)):
            prev_above = recent_fast.iloc[i - 1] > recent_slow.iloc[i - 1]
            curr_above = recent_fast.iloc[i]     > recent_slow.iloc[i]
            if not prev_above and curr_above:
                return "golden_cross"
            if prev_above and not curr_above:
                return "death_cross"
    except Exception as exc:
        log.debug("MA cross check failed: %s", exc)

    return None
