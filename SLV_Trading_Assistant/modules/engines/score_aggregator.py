# Rev 1
"""
Weighted aggregation of technical, macro, and news domain scores
into a single composite score for each trading style.
"""
from __future__ import annotations

from config.trading_styles import TradingStyle, STYLE_WEIGHTS
from modules.infrastructure.logger import get_logger
from modules.reporting.models import MacroResult, NewsResult, TechnicalResult

log = get_logger("engines.score_aggregator")


def aggregate_scores(
    tech: TechnicalResult,
    macro: MacroResult,
    news: NewsResult,
    style: TradingStyle,
) -> tuple[float, float, float, float]:
    """
    Compute per-domain scores and weighted composite.

    Returns
    -------
    tech_score, macro_score, news_score, composite  — all in [-1, +1]
    """
    tech_score  = _technical_score(tech)
    macro_score = macro.composite_score          # already [-1, +1]
    news_score  = _news_score(news)

    weights   = STYLE_WEIGHTS[style]
    composite = (
        weights.technical * tech_score
        + weights.macro   * macro_score
        + weights.news    * news_score
    )
    composite = max(-1.0, min(1.0, composite))

    log.debug(
        "style=%s tech=%.2f macro=%.2f news=%.2f composite=%.2f",
        style.value, tech_score, macro_score, news_score, composite,
    )
    return tech_score, macro_score, news_score, composite


# ---------------------------------------------------------------------------
# Domain score helpers
# ---------------------------------------------------------------------------

def _technical_score(tech: TechnicalResult) -> float:
    """Convert technical indicators to a -1 to +1 directional score."""
    score = 0.0
    ind   = tech.indicators

    # Primary signal: trend direction carries the most weight
    if tech.trend_direction == "bullish":
        score += 0.60
    elif tech.trend_direction == "bearish":
        score -= 0.60

    # RSI extremes — contrarian pressure at boundaries
    rsi = ind.get("rsi_14")
    if rsi is not None:
        if rsi < 30:
            score += 0.15
        elif rsi > 70:
            score -= 0.15

    # MACD histogram direction
    macd_hist = ind.get("macd_hist")
    if macd_hist is not None:
        score += 0.10 if macd_hist > 0 else -0.10

    # Bollinger Band %B position
    bb_pct = ind.get("bb_pct")
    if bb_pct is not None:
        if bb_pct < 0.15:
            score += 0.15
        elif bb_pct > 0.85:
            score -= 0.15

    # Volume — OBV trend direction
    obv = ind.get("obv_trend")
    if obv == "rising":
        score += 0.10
    elif obv == "falling":
        score -= 0.10

    # Volume — high relative volume confirming the price direction vs SMA(20)
    rel_vol = ind.get("relative_volume")
    close   = ind.get("close") or 0.0
    sma_20  = ind.get("sma_20")
    if rel_vol is not None and rel_vol > 1.5 and sma_20 is not None:
        score += 0.05 if close > sma_20 else -0.05

    return max(-1.0, min(1.0, score))


def _news_score(news: NewsResult) -> float:
    """Derive a -1 to +1 sentiment score from classified news items."""
    if not news.items:
        return 0.0

    total     = len(news.items)
    bull      = sum(1 for i in news.items if i.classification == "bullish")
    bear      = sum(1 for i in news.items if i.classification == "bearish")
    bull_conf = sum(i.confidence for i in news.items if i.classification == "bullish")
    bear_conf = sum(i.confidence for i in news.items if i.classification == "bearish")

    ratio          = (bull - bear) / total
    conf_weighted  = (bull_conf - bear_conf) / total

    # Blend: 70% item ratio, 30% confidence-weighted
    return max(-1.0, min(1.0, 0.70 * ratio + 0.30 * conf_weighted))
