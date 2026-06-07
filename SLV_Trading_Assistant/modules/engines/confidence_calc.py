# Rev 1
"""
Confidence reduction rules.
Starts from BASE_CONFIDENCE (70) and applies penalties for data quality
issues, signal conflicts, and elevated market risk conditions.
Floor is 5 — a signal is always produced, even if barely confident.
"""
from __future__ import annotations

from modules.infrastructure.logger import get_logger
from modules.reporting.models import MacroResult, NewsResult, PriceData, TechnicalResult

log = get_logger("engines.confidence_calc")

BASE_CONFIDENCE  = 70.0
CONFIDENCE_FLOOR = 5.0


def calculate_confidence(
    tech: TechnicalResult,
    macro: MacroResult,
    news: NewsResult,
    price_data: PriceData,
    has_conflict: bool,
) -> tuple[float, list[str]]:
    """
    Apply penalty rules to BASE_CONFIDENCE.

    Returns
    -------
    final_confidence : float   (clamped to [CONFIDENCE_FLOOR, BASE_CONFIDENCE])
    penalties        : list[str]  human-readable descriptions of each penalty applied
    """
    confidence = BASE_CONFIDENCE
    penalties: list[str] = []

    # Unknown macro drivers: -8 each, total capped at -25
    unknown = [d for d in macro.drivers if d.score == "unknown"]
    if unknown:
        pen = min(len(unknown) * 8, 25)
        confidence -= pen
        penalties.append(f"-{pen:.0f}: {len(unknown)} macro driver(s) unknown")

    # Stale price data: -20
    if price_data.is_stale:
        confidence -= 20
        penalties.append("-20: price data is stale")

    # Stale macro series: -10 per stale series, total capped at -30
    stale_macro = [w for w in macro.missing_data_warnings if "stale" in w.lower()]
    if stale_macro:
        pen = min(len(stale_macro) * 10, 30)
        confidence -= pen
        penalties.append(f"-{pen:.0f}: {len(stale_macro)} stale macro series")

    # No news feeds available: -15
    if not news.items:
        confidence -= 15
        penalties.append("-15: no news items (all feeds unavailable)")

    # High-impact event within risk window: -15
    if news.event_risk_level in ("critical", "high"):
        confidence -= 15
        penalties.append(f"-15: {news.event_risk_level.upper()} event risk")

    # Technical/macro signal conflict: -10
    if has_conflict:
        confidence -= 10
        penalties.append("-10: technical/macro signal conflict")

    # Elevated volatility regime: -10
    if tech.vol_regime in ("high", "extreme"):
        confidence -= 10
        penalties.append(f"-10: {tech.vol_regime} volatility regime")

    final = max(CONFIDENCE_FLOOR, confidence)
    log.debug("confidence base=%.0f -> final=%.0f  penalties=%s", BASE_CONFIDENCE, final, penalties)
    return final, penalties
