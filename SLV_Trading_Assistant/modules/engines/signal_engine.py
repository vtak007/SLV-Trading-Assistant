# Rev 1
"""
Master signal aggregation engine.
Combines all domain scores, applies no-trade overrides, and produces SignalResult.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from config.trading_styles import TradingStyle, STYLE_WEIGHTS
from modules.analysis.news.event_detector import EventDetector
from modules.engines.confidence_calc import calculate_confidence
from modules.engines.conflict_resolver import detect_conflict
from modules.engines.regime_classifier import classify_regime
from modules.engines.score_aggregator import aggregate_scores
from modules.infrastructure.logger import get_logger
from modules.reporting.models import (
    MacroResult, NewsResult, PriceData, SignalResult, TechnicalResult,
)

log = get_logger("engines.signal_engine")

_ATR_STOP_MULT    = 2.0
_ATR_TARGET1_MULT = 1.5
_ATR_TARGET2_MULT = 3.0
_ATR_TARGET3_MULT = 5.0
_ATR_ENTRY_WIDE   = 0.30


class SignalEngine:

    def __init__(self) -> None:
        self._event_detector = EventDetector()

    def generate(
        self,
        price_data: PriceData,
        tech: TechnicalResult,
        macro: MacroResult,
        news: NewsResult,
        style: TradingStyle,
        analysis_datetime: Optional[datetime] = None,
    ) -> SignalResult:
        """Produce a SignalResult from all analysis-layer outputs."""
        as_of = analysis_datetime or datetime.now(timezone.utc)

        tech_score, macro_score, news_score, composite = aggregate_scores(
            tech, macro, news, style
        )
        thresholds   = STYLE_WEIGHTS[style]
        buy_thresh   = thresholds.buy_threshold
        sell_thresh  = thresholds.sell_threshold

        has_conflict, conflicts = detect_conflict(tech, macro)
        confidence, penalties   = calculate_confidence(
            tech, macro, news, price_data, has_conflict
        )
        regime = classify_regime(tech, macro, news)

        no_trade_reasons = _check_no_trade(
            tech, price_data, news, as_of, self._event_detector
        )

        bull_ev, bear_ev = _collect_evidence(tech, macro, news)

        close = tech.indicators.get("close") or 0.0
        atr   = tech.indicators.get("atr_14") or 0.0

        if no_trade_reasons:
            action          = "NO_TRADE"
            no_trade_reason = "; ".join(no_trade_reasons)
            entry_zone      = (0.0, 0.0)
            stop_loss       = 0.0
            targets: list[float] = []
            position_pct    = 0.0
        elif composite >= buy_thresh:
            action          = "BUY"
            no_trade_reason = ""
            entry_zone, stop_loss, targets, position_pct = _buy_levels(close, atr)
        elif composite <= sell_thresh:
            action          = "SELL"
            no_trade_reason = ""
            entry_zone, stop_loss, targets, position_pct = _sell_levels(close, atr)
        else:
            action          = "HOLD"
            no_trade_reason = ""
            entry_zone      = (0.0, 0.0)
            stop_loss       = 0.0
            targets         = []
            position_pct    = 0.0

        risk_score  = _compute_risk_score(tech, news, confidence)
        explanation = _build_explanation(
            action, composite, confidence, style,
            tech_score, macro_score, news_score,
            has_conflict, penalties, regime,
            buy_thresh, sell_thresh,
        )

        result = SignalResult(
            action            = action,
            confidence        = round(confidence, 1),
            risk_score        = round(risk_score, 1),
            regime_label      = regime,
            entry_zone        = entry_zone,
            stop_loss         = stop_loss,
            targets           = targets,
            position_size_pct = round(position_pct, 4),
            bullish_evidence  = bull_ev,
            bearish_evidence  = bear_ev,
            conflicts         = conflicts,
            explanation       = explanation,
            no_trade_reason   = no_trade_reason,
            generated_at      = as_of,
            trading_style     = style.value,
        )

        log.info(
            "Signal: action=%s confidence=%.1f composite=%.2f regime=%s",
            action, confidence, composite, regime,
        )
        return result


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

def _check_no_trade(
    tech: TechnicalResult,
    price_data: PriceData,
    news: NewsResult,
    as_of: datetime,
    event_detector: EventDetector,
) -> list[str]:
    reasons: list[str] = []

    if event_detector.has_no_trade_condition(news.upcoming_events, as_of=as_of):
        reasons.append("Major event in no-trade window (FOMC/CPI/NFP)")

    if price_data.is_stale:
        reasons.append("Price data is stale (> 2 trading days old)")

    # ATR extreme regime = ATR exceeds ~3x its normal level
    if tech.vol_regime == "extreme":
        reasons.append("Extreme volatility: ATR far above normal (no-trade condition)")

    return reasons


def _buy_levels(
    close: float, atr: float
) -> tuple[tuple[float, float], float, list[float], float]:
    if atr <= 0 or close <= 0:
        return (0.0, 0.0), 0.0, [], 0.0
    entry_lo  = round(close - _ATR_ENTRY_WIDE * atr, 2)
    entry_hi  = round(close + 0.10 * atr, 2)
    stop      = round(close - _ATR_STOP_MULT * atr, 2)
    targets   = [
        round(close + _ATR_TARGET1_MULT * atr, 2),
        round(close + _ATR_TARGET2_MULT * atr, 2),
        round(close + _ATR_TARGET3_MULT * atr, 2),
    ]
    stop_dist = close - stop
    pos_pct   = min(0.01 / (stop_dist / close), 0.05) if stop_dist > 0 else 0.0
    return (entry_lo, entry_hi), stop, targets, pos_pct


def _sell_levels(
    close: float, atr: float
) -> tuple[tuple[float, float], float, list[float], float]:
    if atr <= 0 or close <= 0:
        return (0.0, 0.0), 0.0, [], 0.0
    entry_lo  = round(close - 0.10 * atr, 2)
    entry_hi  = round(close + _ATR_ENTRY_WIDE * atr, 2)
    stop      = round(close + _ATR_STOP_MULT * atr, 2)
    targets   = [
        round(close - _ATR_TARGET1_MULT * atr, 2),
        round(close - _ATR_TARGET2_MULT * atr, 2),
        round(close - _ATR_TARGET3_MULT * atr, 2),
    ]
    stop_dist = stop - close
    pos_pct   = min(0.01 / (stop_dist / close), 0.05) if stop_dist > 0 else 0.0
    return (entry_lo, entry_hi), stop, targets, pos_pct


def _collect_evidence(
    tech: TechnicalResult,
    macro: MacroResult,
    news: NewsResult,
) -> tuple[list[str], list[str]]:
    bull: list[str] = []
    bear: list[str] = []
    ind   = tech.indicators
    close = ind.get("close") or 0.0

    for ma_key, label in [("sma_200", "200-day SMA"), ("sma_50", "50-day SMA")]:
        ma_val = ind.get(ma_key)
        if ma_val:
            if close > ma_val:
                bull.append(f"Price (${close:.2f}) above {label} (${ma_val:.2f})")
            else:
                bear.append(f"Price (${close:.2f}) below {label} (${ma_val:.2f})")

    rsi = ind.get("rsi_14")
    if rsi is not None:
        if rsi < 35:
            bull.append(f"RSI oversold at {rsi:.1f}")
        elif rsi > 65:
            bear.append(f"RSI overbought at {rsi:.1f}")

    macd_h = ind.get("macd_hist")
    if macd_h is not None:
        if macd_h > 0:
            bull.append(f"MACD histogram positive ({macd_h:+.3f})")
        else:
            bear.append(f"MACD histogram negative ({macd_h:+.3f})")

    bb_pct = ind.get("bb_pct")
    if bb_pct is not None:
        if bb_pct < 0.20:
            bull.append(f"Price near Bollinger lower band (BB%B={bb_pct:.2f})")
        elif bb_pct > 0.80:
            bear.append(f"Price near Bollinger upper band (BB%B={bb_pct:.2f})")

    for p in ind.get("patterns", []):
        pl = p.lower()
        if any(k in pl for k in ("bullish", "breakout", "oversold")):
            bull.append(f"Pattern: {p}")
        elif any(k in pl for k in ("bearish", "breakdown", "overbought")):
            bear.append(f"Pattern: {p}")

    for driver in macro.drivers:
        if driver.score == "bullish":
            bull.append(f"Macro [{driver.driver_name}]: {driver.evidence}")
        elif driver.score == "bearish":
            bear.append(f"Macro [{driver.driver_name}]: {driver.evidence}")

    bull_news = [i for i in news.items if i.classification == "bullish"]
    bear_news = [i for i in news.items if i.classification == "bearish"]
    if bull_news:
        bull.append(f"{len(bull_news)} bullish news item(s)")
    if bear_news:
        bear.append(f"{len(bear_news)} bearish news item(s)")

    return bull, bear


def _compute_risk_score(
    tech: TechnicalResult,
    news: NewsResult,
    confidence: float,
) -> float:
    """Risk score 0-100. Higher confidence lowers risk; high vol / events raise it."""
    score = 100.0 - confidence

    if tech.vol_regime == "extreme":
        score += 15
    elif tech.vol_regime == "high":
        score += 8

    if news.event_risk_level == "critical":
        score += 15
    elif news.event_risk_level == "high":
        score += 8
    elif news.event_risk_level == "medium":
        score += 3

    return min(100.0, score)


def _build_explanation(
    action: str,
    composite: float,
    confidence: float,
    style: TradingStyle,
    tech_score: float,
    macro_score: float,
    news_score: float,
    has_conflict: bool,
    penalties: list[str],
    regime: str,
    buy_thresh: float = 0.30,
    sell_thresh: float = -0.30,
) -> str:
    lines = [
        f"Signal: {action}  |  Composite: {composite:+.2f}  |  Confidence: {confidence:.0f}%",
        f"Style: {style.value.upper()}  |  Regime: {regime}",
        f"Thresholds: BUY > {buy_thresh:+.2f}  |  SELL < {sell_thresh:+.2f}",
        (
            f"Domain scores -- "
            f"Technical: {tech_score:+.2f}  "
            f"Macro: {macro_score:+.2f}  "
            f"News: {news_score:+.2f}"
        ),
    ]
    if has_conflict:
        lines.append("** Technical/macro conflict detected -- confidence reduced **")
    if penalties:
        lines.append("Confidence penalties: " + " | ".join(penalties))
    return "\n".join(lines)
