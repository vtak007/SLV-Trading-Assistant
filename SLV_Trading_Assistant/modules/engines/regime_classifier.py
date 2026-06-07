# Rev 1
"""
Classifies the current market regime from combined technical, macro, and news inputs.
The regime label contextualises the signal in the report and can inform
position-size adjustments in future phases.
"""
from __future__ import annotations

from modules.infrastructure.logger import get_logger
from modules.reporting.models import MacroResult, NewsResult, TechnicalResult

log = get_logger("engines.regime_classifier")


def classify_regime(
    tech: TechnicalResult,
    macro: MacroResult,
    news: NewsResult,
) -> str:
    """
    Return one of:
      trending_bull | trending_bear | high_volatility | pre_event |
      technical_bull_macro_mixed | technical_bear_macro_mixed | ranging | unknown
    """
    vol        = tech.vol_regime
    trend      = tech.trend_direction
    macro_cs   = macro.composite_score
    event_risk = news.event_risk_level

    # Pre-event window overrides everything else
    if event_risk in ("critical", "high"):
        regime = "pre_event"
    elif vol in ("high", "extreme"):
        regime = "high_volatility"
    elif trend == "bullish" and macro_cs >= 0.20:
        regime = "trending_bull"
    elif trend == "bearish" and macro_cs <= -0.20:
        regime = "trending_bear"
    elif trend == "bullish":
        regime = "technical_bull_macro_mixed"
    elif trend == "bearish":
        regime = "technical_bear_macro_mixed"
    else:
        regime = "ranging"

    log.debug(
        "regime=%s (vol=%s trend=%s macro=%.2f event=%s)",
        regime, vol, trend, macro_cs, event_risk,
    )
    return regime
