# Rev 1
"""
Unit tests for the signal engine and its helper modules.
All tests are offline — no network calls, no database reads.
"""
from __future__ import annotations

from datetime import datetime, timezone

import pandas as pd
import pytest

from config.trading_styles import TradingStyle
from modules.engines.confidence_calc import calculate_confidence, BASE_CONFIDENCE, CONFIDENCE_FLOOR
from modules.engines.conflict_resolver import detect_conflict
from modules.engines.regime_classifier import classify_regime
from modules.engines.score_aggregator import aggregate_scores
from modules.engines.signal_engine import SignalEngine
from modules.reporting.models import (
    MacroDriverScore, MacroResult, NewsItem, NewsResult, PriceData, TechnicalResult,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def fresh_price_data(sample_ohlcv) -> PriceData:
    return PriceData(
        ticker="SLV",
        ohlcv=sample_ohlcv,
        fetched_at=datetime.now(timezone.utc),
        is_stale=False,
    )


@pytest.fixture
def stale_price_data(sample_ohlcv) -> PriceData:
    return PriceData(
        ticker="SLV",
        ohlcv=sample_ohlcv,
        fetched_at=datetime.now(timezone.utc),
        is_stale=True,
    )


def _make_tech(
    trend="bullish",
    vol_regime="normal",
    rsi=55.0,
    macd_hist=0.05,
    close=30.0,
    atr=0.50,
    bb_pct=0.5,
) -> TechnicalResult:
    return TechnicalResult(
        ticker="SLV",
        analysis_date=datetime.now(timezone.utc),
        indicators={
            "close": close, "atr_14": atr, "rsi_14": rsi,
            "macd_hist": macd_hist, "bb_pct": bb_pct,
            "sma_200": 28.0, "sma_50": 29.0,
        },
        vol_regime=vol_regime,
        trend_direction=trend,
    )


def _make_macro(composite: float = 0.30, unknown_count: int = 0) -> MacroResult:
    drivers = [
        MacroDriverScore("Test Driver", "bullish", 1.0, "test evidence", 0.125)
        for _ in range(8 - unknown_count)
    ] + [
        MacroDriverScore("Unknown Driver", "unknown", None, "no data", 0.125)
        for _ in range(unknown_count)
    ]
    return MacroResult(drivers=drivers, composite_score=composite,
                       analysis_date=datetime.now(timezone.utc))


def _make_news(bull=2, bear=1, event_risk="low") -> NewsResult:
    items: list[NewsItem] = []
    now = datetime.now(timezone.utc)
    for i in range(bull):
        items.append(NewsItem(
            headline=f"Bullish news {i}", source="test", url="",
            published_at=now, fetched_at=now, classification="bullish", confidence=0.8,
        ))
    for i in range(bear):
        items.append(NewsItem(
            headline=f"Bearish news {i}", source="test", url="",
            published_at=now, fetched_at=now, classification="bearish", confidence=0.7,
        ))
    return NewsResult(items=items, event_risk_level=event_risk,
                      analysis_datetime=now)


# ---------------------------------------------------------------------------
# score_aggregator tests
# ---------------------------------------------------------------------------

class TestScoreAggregator:

    def test_bullish_tech_produces_positive_score(self):
        tech  = _make_tech(trend="bullish", macd_hist=0.1, rsi=55, bb_pct=0.5)
        macro = _make_macro(0.0)
        news  = _make_news(0, 0)
        ts, ms, ns, comp = aggregate_scores(tech, macro, news, TradingStyle.SWING)
        assert ts > 0

    def test_bearish_tech_produces_negative_score(self):
        tech  = _make_tech(trend="bearish", macd_hist=-0.1, rsi=55)
        macro = _make_macro(0.0)
        news  = _make_news(0, 0)
        ts, ms, ns, comp = aggregate_scores(tech, macro, news, TradingStyle.SWING)
        assert ts < 0

    def test_composite_within_bounds(self):
        tech  = _make_tech(trend="bullish")
        macro = _make_macro(1.0)
        news  = _make_news(10, 0)
        _, _, _, comp = aggregate_scores(tech, macro, news, TradingStyle.SWING)
        assert -1.0 <= comp <= 1.0

    def test_style_weights_applied(self):
        tech  = _make_tech(trend="bullish")
        macro = _make_macro(-1.0)
        news  = _make_news(0, 0)
        _, _, _, comp_day  = aggregate_scores(tech, macro, news, TradingStyle.DAY)
        _, _, _, comp_long = aggregate_scores(tech, macro, news, TradingStyle.LONG_TERM)
        # DAY is 70% tech; LONG_TERM is 10% tech — bullish tech should score higher in DAY
        assert comp_day > comp_long

    def test_empty_news_returns_zero_news_score(self):
        tech  = _make_tech()
        macro = _make_macro(0.0)
        news  = NewsResult()
        _, _, ns, _ = aggregate_scores(tech, macro, news, TradingStyle.SWING)
        assert ns == 0.0


# ---------------------------------------------------------------------------
# confidence_calc tests
# ---------------------------------------------------------------------------

class TestConfidenceCalc:

    def test_base_confidence_no_penalties(self, fresh_price_data):
        tech  = _make_tech()
        macro = _make_macro(0.0, unknown_count=0)
        news  = _make_news(1, 0, event_risk="low")
        conf, penalties = calculate_confidence(tech, macro, news, fresh_price_data, False)
        assert conf == BASE_CONFIDENCE
        assert penalties == []

    def test_stale_price_penalty(self, stale_price_data):
        tech  = _make_tech()
        macro = _make_macro(0.0, unknown_count=0)
        news  = _make_news(1, 0, event_risk="low")
        conf, penalties = calculate_confidence(tech, macro, news, stale_price_data, False)
        assert conf == BASE_CONFIDENCE - 20
        assert any("stale" in p for p in penalties)

    def test_unknown_driver_penalty(self, fresh_price_data):
        tech  = _make_tech()
        macro = _make_macro(0.0, unknown_count=3)
        news  = _make_news(1, 0, event_risk="low")
        conf, penalties = calculate_confidence(tech, macro, news, fresh_price_data, False)
        assert conf < BASE_CONFIDENCE
        assert any("unknown" in p for p in penalties)

    def test_unknown_driver_cap(self, fresh_price_data):
        tech  = _make_tech()
        macro = _make_macro(0.0, unknown_count=8)   # 8 * 8 = 64 but cap is 25
        news  = _make_news(1, 0)
        conf, _ = calculate_confidence(tech, macro, news, fresh_price_data, False)
        assert conf == BASE_CONFIDENCE - 25

    def test_conflict_penalty(self, fresh_price_data):
        tech  = _make_tech()
        macro = _make_macro(0.0)
        news  = _make_news(1, 0)
        conf_no, _ = calculate_confidence(tech, macro, news, fresh_price_data, False)
        conf_yes, _ = calculate_confidence(tech, macro, news, fresh_price_data, True)
        assert conf_yes == conf_no - 10

    def test_floor_enforced(self, stale_price_data):
        tech  = _make_tech(vol_regime="extreme")
        macro = _make_macro(0.0, unknown_count=8)
        news  = NewsResult(event_risk_level="critical")
        conf, _ = calculate_confidence(tech, macro, news, stale_price_data, True)
        assert conf == CONFIDENCE_FLOOR

    def test_high_event_risk_penalty(self, fresh_price_data):
        tech  = _make_tech()
        macro = _make_macro(0.0)
        news  = _make_news(1, 0, event_risk="high")
        conf, penalties = calculate_confidence(tech, macro, news, fresh_price_data, False)
        assert any("event risk" in p.lower() for p in penalties)
        assert conf == BASE_CONFIDENCE - 15


# ---------------------------------------------------------------------------
# conflict_resolver tests
# ---------------------------------------------------------------------------

class TestConflictResolver:

    def test_no_conflict_when_aligned(self):
        tech  = _make_tech(trend="bullish")
        macro = _make_macro(0.5)
        has_c, _ = detect_conflict(tech, macro)
        assert not has_c

    def test_conflict_tech_bull_macro_bear(self):
        tech  = _make_tech(trend="bullish")
        macro = _make_macro(-0.5)
        has_c, conflicts = detect_conflict(tech, macro)
        assert has_c
        assert len(conflicts) == 1

    def test_conflict_tech_bear_macro_bull(self):
        tech  = _make_tech(trend="bearish")
        macro = _make_macro(0.5)
        has_c, conflicts = detect_conflict(tech, macro)
        assert has_c

    def test_no_conflict_neutral_tech(self):
        tech  = _make_tech(trend="neutral")
        macro = _make_macro(0.5)
        has_c, _ = detect_conflict(tech, macro)
        assert not has_c

    def test_no_conflict_below_threshold(self):
        # Macro at 0.15 — below threshold, should not trigger
        tech  = _make_tech(trend="bearish")
        macro = _make_macro(0.15)
        has_c, _ = detect_conflict(tech, macro)
        assert not has_c


# ---------------------------------------------------------------------------
# regime_classifier tests
# ---------------------------------------------------------------------------

class TestRegimeClassifier:

    def test_trending_bull(self):
        assert classify_regime(_make_tech("bullish"), _make_macro(0.5), _make_news()) == "trending_bull"

    def test_trending_bear(self):
        assert classify_regime(_make_tech("bearish"), _make_macro(-0.5), _make_news()) == "trending_bear"

    def test_high_vol(self):
        assert classify_regime(_make_tech("bullish", vol_regime="high"), _make_macro(0.5), _make_news()) == "high_volatility"

    def test_pre_event(self):
        assert classify_regime(_make_tech(), _make_macro(), _make_news(event_risk="critical")) == "pre_event"

    def test_ranging(self):
        assert classify_regime(_make_tech("neutral"), _make_macro(0.0), _make_news()) == "ranging"


# ---------------------------------------------------------------------------
# signal_engine integration tests
# ---------------------------------------------------------------------------

class TestSignalEngine:

    def _run(self, trend, macro_score, style=TradingStyle.SWING, stale=False, vol_regime="normal"):
        engine     = SignalEngine()
        tech       = _make_tech(trend=trend, vol_regime=vol_regime, close=30.0, atr=0.50)
        macro      = _make_macro(macro_score)
        news       = _make_news(2, 1)
        price_data = PriceData(
            ticker="SLV",
            ohlcv=pd.DataFrame(
                {"open": [29.9], "high": [30.2], "low": [29.8], "close": [30.0],
                 "volume": [5e6], "adj_close": [30.0]},
                index=pd.date_range("2026-05-27", periods=1, freq="B"),
            ),
            fetched_at=datetime.now(timezone.utc),
            is_stale=stale,
        )
        return engine.generate(price_data, tech, macro, news, style)

    def test_buy_signal_strong_bull(self):
        result = self._run("bullish", 0.6)
        assert result.action == "BUY"

    def test_sell_signal_strong_bear(self):
        result = self._run("bearish", -0.6)
        assert result.action == "SELL"

    def test_hold_signal_neutral(self):
        result = self._run("neutral", 0.0)
        assert result.action == "HOLD"

    def test_no_trade_stale_price(self):
        result = self._run("bullish", 0.6, stale=True)
        assert result.action == "NO_TRADE"
        assert "stale" in result.no_trade_reason.lower()

    def test_no_trade_extreme_vol(self):
        result = self._run("bullish", 0.6, vol_regime="extreme")
        assert result.action == "NO_TRADE"

    def test_buy_has_entry_stop_targets(self):
        result = self._run("bullish", 0.6)
        assert result.entry_zone != (0.0, 0.0)
        assert result.stop_loss > 0
        assert len(result.targets) == 3

    def test_confidence_range(self):
        result = self._run("bullish", 0.6)
        assert CONFIDENCE_FLOOR <= result.confidence <= BASE_CONFIDENCE

    def test_signal_result_fields_populated(self):
        result = self._run("bullish", 0.4)
        assert result.trading_style == "swing"
        assert result.generated_at is not None
        assert result.regime_label != ""
        assert result.explanation != ""

    def test_position_size_pct_capped(self):
        result = self._run("bullish", 0.8)
        assert 0.0 <= result.position_size_pct <= 0.05
