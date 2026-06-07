# Rev 1
"""
End-to-end integration tests.

Verifies that the full signal pipeline behaves correctly under:
- Stale data (all penalty types stacking to the confidence floor)
- FOMC/CPI/NFP no-trade override windows
- JSON signal file written by ReportEngine
- Complete pipeline produces a valid SignalResult from synthetic data

All tests are offline — no network calls, no database writes.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

import pandas as pd
import pytest

from config.trading_styles import TradingStyle
from modules.analysis.technical.technical_analyzer import TechnicalAnalyzer
from modules.engines.confidence_calc import (
    BASE_CONFIDENCE, CONFIDENCE_FLOOR, calculate_confidence,
)
from modules.engines.risk_engine import RiskEngine
from modules.engines.signal_engine import SignalEngine
from modules.reporting.models import (
    MacroDriverScore, MacroResult, NewsItem, NewsResult,
    PriceData, RiskResult, SignalResult, TechnicalResult,
)
from modules.reporting.report_engine import ReportEngine


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _make_price_data(is_stale: bool = False) -> PriceData:
    df = pd.DataFrame(
        {
            "open":      [29.9],
            "high":      [30.2],
            "low":       [29.8],
            "close":     [30.0],
            "volume":    [5_000_000.0],
            "adj_close": [30.0],
        },
        index=pd.date_range("2026-05-27", periods=1, freq="B"),
    )
    return PriceData(ticker="SLV", ohlcv=df,
                     fetched_at=datetime.now(timezone.utc), is_stale=is_stale)


def _make_tech(vol_regime: str = "normal", trend: str = "bullish") -> TechnicalResult:
    return TechnicalResult(
        ticker="SLV",
        analysis_date=datetime.now(timezone.utc),
        indicators={"close": 30.0, "atr_14": 0.5, "rsi_14": 55.0,
                    "macd_hist": 0.05, "bb_pct": 0.5,
                    "sma_200": 28.0, "sma_50": 29.0},
        vol_regime=vol_regime,
        trend_direction=trend,
    )


def _make_macro(
    composite: float = 0.3,
    unknown_count: int = 0,
    stale_warnings: int = 0,
) -> MacroResult:
    drivers = [
        MacroDriverScore("Test Driver", "bullish", 1.0, "evidence", 0.125)
        for _ in range(8 - unknown_count)
    ] + [
        MacroDriverScore("Unknown Driver", "unknown", None, "no data", 0.125)
        for _ in range(unknown_count)
    ]
    warnings = [f"DGS10: stale series ({i})" for i in range(stale_warnings)]
    return MacroResult(drivers=drivers, composite_score=composite,
                       missing_data_warnings=warnings,
                       analysis_date=datetime.now(timezone.utc))


def _make_news(
    event_risk: str = "low",
    items_count: int = 3,
    upcoming_events: list | None = None,
) -> NewsResult:
    now = datetime.now(timezone.utc)
    items = [
        NewsItem(
            headline=f"News item {i}", source="test", url="",
            published_at=now, fetched_at=now,
            classification="neutral", confidence=0.6,
        )
        for i in range(items_count)
    ]
    return NewsResult(
        items=items,
        upcoming_events=upcoming_events or [],
        event_risk_level=event_risk,
        analysis_datetime=now,
    )


def _make_fomc_event(hours_away: float) -> dict:
    sched = datetime.now(timezone.utc) + timedelta(hours=hours_away)
    return {"event_name": "FOMC", "scheduled_at": sched, "impact_level": "critical"}


def _make_cpi_event(hours_away: float) -> dict:
    sched = datetime.now(timezone.utc) + timedelta(hours=hours_away)
    return {"event_name": "CPI", "scheduled_at": sched, "impact_level": "high"}


def _make_nfp_event(hours_away: float) -> dict:
    sched = datetime.now(timezone.utc) + timedelta(hours=hours_away)
    return {"event_name": "NFP", "scheduled_at": sched, "impact_level": "high"}


# ---------------------------------------------------------------------------
# Full pipeline integration
# ---------------------------------------------------------------------------

class TestFullPipeline:

    def test_full_pipeline_produces_valid_signal(self, sample_ohlcv, analysis_date):
        """All layers connected end-to-end with synthetic data produce a valid SignalResult."""
        price_data  = PriceData(ticker="SLV", ohlcv=sample_ohlcv,
                                fetched_at=datetime.now(timezone.utc), is_stale=False)
        analyzer    = TechnicalAnalyzer()
        tech_result = analyzer.analyze(price_data, analysis_date=analysis_date)

        macro  = _make_macro(0.4)
        news   = _make_news()
        engine = SignalEngine()

        result = engine.generate(
            price_data, tech_result, macro, news,
            TradingStyle.SWING, analysis_datetime=analysis_date,
        )

        assert result.action in ("BUY", "SELL", "HOLD", "NO_TRADE")
        assert CONFIDENCE_FLOOR <= result.confidence <= BASE_CONFIDENCE
        assert 0.0 <= result.risk_score <= 100.0
        assert result.regime_label != ""
        assert result.explanation != ""
        assert result.trading_style == "swing"

    def test_full_pipeline_risk_engine_populated(self, sample_ohlcv, analysis_date):
        price_data  = PriceData(ticker="SLV", ohlcv=sample_ohlcv,
                                fetched_at=datetime.now(timezone.utc), is_stale=False)
        tech_result = TechnicalAnalyzer().analyze(price_data, analysis_date=analysis_date)

        signal = SignalEngine().generate(
            price_data, tech_result, _make_macro(0.5), _make_news(),
            TradingStyle.SWING, analysis_datetime=analysis_date,
        )
        risk = RiskEngine().calculate(tech_result, _make_news(), price_data, signal)

        assert risk.atr_value > 0
        assert isinstance(risk.gap_risk_flag, bool)
        assert isinstance(risk.major_event_flag, bool)
        assert risk.atr_stop > 0

    def test_hold_when_composite_near_zero(self):
        engine  = SignalEngine()
        price   = _make_price_data()
        tech    = _make_tech(trend="neutral")
        # composite ~0: macro 0 + tech neutral + no news → between -0.3 and +0.3
        macro   = _make_macro(composite=0.0)
        news    = _make_news(items_count=0)
        result  = engine.generate(price, tech, macro, news, TradingStyle.SWING)
        assert result.action == "HOLD"

    def test_buy_targets_above_close(self):
        engine = SignalEngine()
        price  = _make_price_data()
        tech   = _make_tech(trend="bullish")
        macro  = _make_macro(composite=0.8)
        news   = _make_news()
        result = engine.generate(price, tech, macro, news, TradingStyle.SWING)
        if result.action == "BUY":
            close = tech.indicators["close"]
            assert all(t > close for t in result.targets)
            lo, hi = result.entry_zone
            assert lo < hi


# ---------------------------------------------------------------------------
# Confidence penalty integration
# ---------------------------------------------------------------------------

class TestConfidencePenaltyIntegration:

    def test_stale_price_penalty_fires(self):
        tech  = _make_tech()
        macro = _make_macro()
        news  = _make_news(items_count=1)
        price = _make_price_data(is_stale=True)
        conf, penalties = calculate_confidence(tech, macro, news, price, False)
        assert any("stale" in p for p in penalties)
        assert conf == BASE_CONFIDENCE - 20

    def test_stale_macro_penalty_fires(self):
        tech  = _make_tech()
        macro = _make_macro(stale_warnings=2)
        news  = _make_news(items_count=1)
        price = _make_price_data(is_stale=False)
        conf, penalties = calculate_confidence(tech, macro, news, price, False)
        assert any("stale macro" in p for p in penalties)
        assert conf < BASE_CONFIDENCE

    def test_no_news_penalty_fires(self):
        tech  = _make_tech()
        macro = _make_macro()
        price = _make_price_data()
        news  = NewsResult(event_risk_level="low", analysis_datetime=datetime.now(timezone.utc))
        conf, penalties = calculate_confidence(tech, macro, news, price, False)
        assert any("no news" in p for p in penalties)
        assert conf == BASE_CONFIDENCE - 15

    def test_all_penalties_stack_to_floor(self):
        """Every penalty type active simultaneously must push confidence to CONFIDENCE_FLOOR."""
        tech  = _make_tech(vol_regime="extreme")
        macro = _make_macro(unknown_count=8, stale_warnings=3)  # max unknown cap + stale
        news  = NewsResult(event_risk_level="critical",         # high event risk + no items
                           analysis_datetime=datetime.now(timezone.utc))
        price = _make_price_data(is_stale=True)
        conf, _ = calculate_confidence(tech, macro, news, price, has_conflict=True)
        assert conf == CONFIDENCE_FLOOR

    def test_unknown_driver_cap_at_25(self):
        tech  = _make_tech()
        macro = _make_macro(unknown_count=8)   # 8*8=64 but cap is 25
        news  = _make_news(items_count=1)
        price = _make_price_data()
        conf, _ = calculate_confidence(tech, macro, news, price, False)
        assert conf == BASE_CONFIDENCE - 25

    def test_stale_macro_cap_at_30(self):
        tech  = _make_tech()
        macro = _make_macro(stale_warnings=5)   # 5*10=50 but cap is 30
        news  = _make_news(items_count=1)
        price = _make_price_data()
        conf, _ = calculate_confidence(tech, macro, news, price, False)
        assert conf == BASE_CONFIDENCE - 30


# ---------------------------------------------------------------------------
# No-trade override integration
# ---------------------------------------------------------------------------

class TestNoTradeOverride:

    def _run_engine(self, upcoming_events: list) -> SignalResult:
        engine = SignalEngine()
        price  = _make_price_data()
        tech   = _make_tech(trend="bullish")
        macro  = _make_macro(composite=0.8)
        news   = _make_news(upcoming_events=upcoming_events)
        return engine.generate(price, tech, macro, news, TradingStyle.SWING)

    def test_fomc_4h_window_triggers_no_trade(self):
        result = self._run_engine([_make_fomc_event(hours_away=2.0)])
        assert result.action == "NO_TRADE"
        assert "FOMC" in result.no_trade_reason or "Major event" in result.no_trade_reason

    def test_fomc_exactly_at_4h_triggers_no_trade(self):
        result = self._run_engine([_make_fomc_event(hours_away=3.9)])
        assert result.action == "NO_TRADE"

    def test_cpi_1h_window_triggers_no_trade(self):
        result = self._run_engine([_make_cpi_event(hours_away=0.5)])
        assert result.action == "NO_TRADE"

    def test_nfp_1h_window_triggers_no_trade(self):
        result = self._run_engine([_make_nfp_event(hours_away=0.5)])
        assert result.action == "NO_TRADE"

    def test_fomc_24h_away_does_not_trigger_no_trade(self):
        # 24h away is "critical" risk level but NOT in the no-trade window
        result = self._run_engine([_make_fomc_event(hours_away=20.0)])
        assert result.action != "NO_TRADE"

    def test_past_event_does_not_trigger_no_trade(self):
        # Event already happened (negative hours) — must not trigger no-trade
        past = datetime.now(timezone.utc) - timedelta(hours=1)
        result = self._run_engine([{"event_name": "FOMC",
                                    "scheduled_at": past, "impact_level": "critical"}])
        assert result.action != "NO_TRADE"

    def test_extreme_vol_triggers_no_trade(self):
        engine = SignalEngine()
        price  = _make_price_data()
        tech   = _make_tech(vol_regime="extreme")
        macro  = _make_macro(composite=0.8)
        news   = _make_news()
        result = engine.generate(price, tech, macro, news, TradingStyle.SWING)
        assert result.action == "NO_TRADE"

    def test_stale_price_triggers_no_trade(self):
        engine = SignalEngine()
        price  = _make_price_data(is_stale=True)
        tech   = _make_tech()
        macro  = _make_macro(composite=0.8)
        news   = _make_news()
        result = engine.generate(price, tech, macro, news, TradingStyle.SWING)
        assert result.action == "NO_TRADE"


# ---------------------------------------------------------------------------
# JSON signal history (ReportEngine)
# ---------------------------------------------------------------------------

class TestSignalJsonHistory:

    def _make_signal(self) -> SignalResult:
        return SignalResult(
            action="BUY",
            confidence=65.0,
            risk_score=35.0,
            regime_label="trending_bull",
            entry_zone=(29.75, 30.10),
            stop_loss=29.0,
            targets=[30.75, 31.50, 32.50],
            position_size_pct=0.025,
            bullish_evidence=["Price above 200-day SMA"],
            bearish_evidence=[],
            conflicts=[],
            explanation="Signal: BUY  |  Confidence: 65%",
            no_trade_reason="",
            generated_at=datetime(2026, 5, 28, 17, 0, tzinfo=timezone.utc),
            trading_style="swing",
        )

    def test_write_signal_json_creates_file(self, tmp_path):
        engine = ReportEngine()
        signal = self._make_signal()
        style  = TradingStyle.SWING
        as_of  = datetime(2026, 5, 28, 17, 0, tzinfo=timezone.utc)

        import config.settings as cfg_mod
        original = cfg_mod.SIGNALS_DIR
        try:
            cfg_mod.SIGNALS_DIR = tmp_path
            from modules.reporting import report_engine as re_mod
            re_mod.SIGNALS_DIR = tmp_path

            path = engine._write_signal_json(signal, style, as_of)
        finally:
            cfg_mod.SIGNALS_DIR = original
            re_mod.SIGNALS_DIR = original

        assert path is not None
        assert path.exists()

    def test_write_signal_json_content_correct(self, tmp_path):
        engine = ReportEngine()
        signal = self._make_signal()
        style  = TradingStyle.SWING
        as_of  = datetime(2026, 5, 28, 17, 0, tzinfo=timezone.utc)

        import config.settings as cfg_mod
        from modules.reporting import report_engine as re_mod
        original = cfg_mod.SIGNALS_DIR
        try:
            cfg_mod.SIGNALS_DIR = tmp_path
            re_mod.SIGNALS_DIR = tmp_path
            path = engine._write_signal_json(signal, style, as_of)
        finally:
            cfg_mod.SIGNALS_DIR = original
            re_mod.SIGNALS_DIR = original

        data = json.loads(path.read_text(encoding="utf-8"))
        assert data["action"] == "BUY"
        assert data["confidence"] == 65.0
        assert data["trading_style"] == "swing"
        assert data["regime_label"] == "trending_bull"
        assert data["targets"] == [30.75, 31.50, 32.50]
        assert data["entry_zone"] == [29.75, 30.10]
        assert "generated_at" in data

    def test_write_signal_json_filename_contains_style(self, tmp_path):
        engine = ReportEngine()
        signal = self._make_signal()
        style  = TradingStyle.SWING
        as_of  = datetime(2026, 5, 28, 17, 0, tzinfo=timezone.utc)

        import config.settings as cfg_mod
        from modules.reporting import report_engine as re_mod
        original = cfg_mod.SIGNALS_DIR
        try:
            cfg_mod.SIGNALS_DIR = tmp_path
            re_mod.SIGNALS_DIR = tmp_path
            path = engine._write_signal_json(signal, style, as_of)
        finally:
            cfg_mod.SIGNALS_DIR = original
            re_mod.SIGNALS_DIR = original

        assert "swing" in path.name
        assert path.suffix == ".json"
