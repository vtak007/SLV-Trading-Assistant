# Rev 1
"""
Unit tests for the risk engine.
All tests are offline — no network calls.
"""
from __future__ import annotations

from datetime import datetime, timezone

import pandas as pd
import pytest

from modules.engines.risk_engine import RiskEngine
from modules.reporting.models import (
    NewsResult, PriceData, RiskResult, SignalResult, TechnicalResult,
)


def _make_tech(close=30.0, atr=0.50, vol_regime="normal") -> TechnicalResult:
    return TechnicalResult(
        ticker="SLV",
        analysis_date=datetime.now(timezone.utc),
        indicators={"close": close, "atr_14": atr},
        vol_regime=vol_regime,
        trend_direction="bullish",
    )


def _make_price_data(bar_range_mult=1.0, atr=0.50, is_stale=False) -> PriceData:
    bar_range = bar_range_mult * atr
    df = pd.DataFrame(
        {
            "open":  [29.9],
            "high":  [30.0 + bar_range / 2],
            "low":   [30.0 - bar_range / 2],
            "close": [30.0],
            "volume": [5e6],
            "adj_close": [30.0],
        },
        index=pd.date_range("2026-05-27", periods=1, freq="B"),
    )
    return PriceData(
        ticker="SLV", ohlcv=df,
        fetched_at=datetime.now(timezone.utc),
        is_stale=is_stale,
    )


def _make_signal(action="BUY", no_trade_reason="") -> SignalResult:
    return SignalResult(
        action=action, confidence=65.0, risk_score=35.0,
        no_trade_reason=no_trade_reason,
    )


def _make_news(event_risk="low") -> NewsResult:
    return NewsResult(event_risk_level=event_risk)


class TestRiskEngine:

    def test_atr_stop_calculated(self):
        engine = RiskEngine()
        result = engine.calculate(
            _make_tech(close=30.0, atr=0.50),
            _make_news(),
            _make_price_data(),
            _make_signal(),
        )
        # stop = 30.0 - 2 * 0.5 = 29.0
        assert abs(result.atr_stop - 29.0) < 0.01

    def test_position_shares_calculated_for_buy(self):
        engine = RiskEngine()
        result = engine.calculate(
            _make_tech(close=30.0, atr=0.50),
            _make_news(),
            _make_price_data(),
            _make_signal(action="BUY"),
            account_size=10_000.0,
            account_risk_pct=0.01,
        )
        # dollar_risk = 100; stop_dist = 1.0; shares = 100
        assert result.position_size_shares == 100

    def test_no_shares_for_hold(self):
        engine = RiskEngine()
        result = engine.calculate(
            _make_tech(close=30.0, atr=0.50),
            _make_news(),
            _make_price_data(),
            _make_signal(action="HOLD"),
        )
        assert result.position_size_shares == 0

    def test_no_shares_for_no_trade(self):
        engine = RiskEngine()
        result = engine.calculate(
            _make_tech(),
            _make_news(),
            _make_price_data(),
            _make_signal(action="NO_TRADE", no_trade_reason="stale data"),
        )
        assert result.position_size_shares == 0

    def test_gap_risk_flag_large_bar(self):
        engine = RiskEngine()
        # bar_range = 2x ATR (> 1.5x threshold)
        result = engine.calculate(
            _make_tech(atr=0.50),
            _make_news(),
            _make_price_data(bar_range_mult=2.0, atr=0.50),
            _make_signal(),
        )
        assert result.gap_risk_flag is True

    def test_no_gap_risk_normal_bar(self):
        engine = RiskEngine()
        result = engine.calculate(
            _make_tech(atr=0.50),
            _make_news(),
            _make_price_data(bar_range_mult=1.0, atr=0.50),
            _make_signal(),
        )
        assert result.gap_risk_flag is False

    def test_major_event_flag_high(self):
        engine = RiskEngine()
        result = engine.calculate(
            _make_tech(),
            _make_news(event_risk="high"),
            _make_price_data(),
            _make_signal(),
        )
        assert result.major_event_flag is True

    def test_major_event_flag_low(self):
        engine = RiskEngine()
        result = engine.calculate(
            _make_tech(),
            _make_news(event_risk="low"),
            _make_price_data(),
            _make_signal(),
        )
        assert result.major_event_flag is False

    def test_no_trade_conditions_propagated(self):
        engine = RiskEngine()
        result = engine.calculate(
            _make_tech(),
            _make_news(),
            _make_price_data(),
            _make_signal(action="NO_TRADE", no_trade_reason="stale data; extreme volatility"),
        )
        assert len(result.no_trade_conditions) == 2

    def test_atr_value_stored(self):
        engine = RiskEngine()
        result = engine.calculate(
            _make_tech(atr=0.75),
            _make_news(),
            _make_price_data(atr=0.75),
            _make_signal(),
        )
        assert abs(result.atr_value - 0.75) < 0.001

    def test_zero_atr_returns_zero_stop(self):
        engine = RiskEngine()
        result = engine.calculate(
            _make_tech(atr=0.0),
            _make_news(),
            _make_price_data(atr=0.0),
            _make_signal(),
        )
        assert result.atr_stop == 0.0
        assert result.position_size_shares == 0
