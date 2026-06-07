# Rev 2  (pass options_data to classify_vol_regime for IV-based vol regime)
"""
Technical analysis orchestrator.
Combines all technical sub-modules and returns a TechnicalResult.
"""
from __future__ import annotations

from datetime import datetime, timezone

import pandas as pd

from modules.analysis.technical.indicators import calculate_indicators
from modules.analysis.technical.volume_analysis import calculate_volume_metrics
from modules.analysis.technical.vol_regime import classify_vol_regime
from modules.analysis.technical.support_resistance import find_levels
from modules.analysis.technical.pattern_detector import detect_patterns
from modules.infrastructure.exceptions import ValidationError
from modules.infrastructure.logger import get_logger
from modules.reporting.models import OptionsData, PriceData, TechnicalResult

log = get_logger("technical_analyzer")


class TechnicalAnalyzer:

    def analyze(
        self,
        price_data: PriceData,
        analysis_date: datetime | None = None,
        options_data: OptionsData | None = None,
    ) -> TechnicalResult:
        """
        Run full technical analysis on `price_data`.
        If `analysis_date` is None, uses the latest bar date (real-time mode).
        """
        if analysis_date is None:
            analysis_date = datetime.now(timezone.utc)

        ticker = price_data.ticker
        df = price_data.ohlcv
        warnings: list[str] = list(price_data.warnings)   # carry forward fetch warnings

        log.info("Running technical analysis for %s up to %s", ticker, analysis_date.date())

        # --- Indicators ---
        try:
            indicators, ind_warnings = calculate_indicators(df, analysis_date)
            warnings.extend(ind_warnings)
        except ValidationError as exc:
            log.error("Indicator calculation failed: %s", exc)
            return TechnicalResult(
                ticker=ticker,
                analysis_date=analysis_date,
                warnings=[str(exc)],
            )

        # --- Volume metrics (merged into indicators dict) ---
        vol_metrics, vol_warnings = calculate_volume_metrics(df, analysis_date)
        warnings.extend(vol_warnings)
        indicators.update(vol_metrics)

        # --- Volatility regime ---
        vol_regime, regime_warnings = classify_vol_regime(
            df, analysis_date, options_data=options_data
        )
        warnings.extend(regime_warnings)

        # --- Support & Resistance ---
        support, resistance, sr_warnings = find_levels(df, analysis_date)
        warnings.extend(sr_warnings)

        # Store in indicators for pattern detector and downstream consumers
        indicators["support_levels"]    = support
        indicators["resistance_levels"] = resistance

        # --- Patterns ---
        patterns = detect_patterns(df, indicators, support, resistance, analysis_date)
        indicators["patterns"] = patterns

        # --- Trend direction ---
        trend = _determine_trend(indicators)

        result = TechnicalResult(
            ticker=ticker,
            analysis_date=analysis_date,
            indicators=indicators,
            support_levels=support,
            resistance_levels=resistance,
            vol_regime=vol_regime,
            trend_direction=trend,
            warnings=warnings,
        )

        log.info(
            "%s technical result: trend=%s vol_regime=%s patterns=%s",
            ticker, trend, vol_regime, patterns or "none",
        )
        return result


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _determine_trend(indicators: dict) -> str:
    """
    Score bull/bear signals from MA alignment and MACD.
    Returns 'bullish', 'bearish', or 'neutral'.
    """
    close     = indicators.get("close")   or 0.0
    sma_20    = indicators.get("sma_20")
    sma_50    = indicators.get("sma_50")
    sma_200   = indicators.get("sma_200")
    macd_hist = indicators.get("macd_hist")
    ema_9     = indicators.get("ema_9")
    ema_21    = indicators.get("ema_21")

    bull = bear = total = 0

    def _vote(condition: bool) -> None:
        nonlocal bull, bear, total
        total += 1
        if condition:
            bull += 1
        else:
            bear += 1

    if sma_20  is not None: _vote(close > sma_20)
    if sma_20  is not None and sma_50 is not None: _vote(sma_20 > sma_50)
    if sma_50  is not None and sma_200 is not None: _vote(sma_50 > sma_200)
    if ema_9   is not None and ema_21 is not None: _vote(ema_9 > ema_21)
    if macd_hist is not None: _vote(macd_hist > 0)

    if total == 0:
        return "neutral"

    ratio = bull / total
    if ratio >= 0.70:
        return "bullish"
    if ratio <= 0.30:
        return "bearish"
    return "neutral"
