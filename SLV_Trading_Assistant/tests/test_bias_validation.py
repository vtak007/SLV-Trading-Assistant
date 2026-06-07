# Rev 1
"""
No-look-ahead bias validation tests.

Core invariant: given a fixed analysis_date T, the result of any analysis
function must be identical whether the input DataFrame contains rows only
up to T or also contains rows past T.  A breach of this invariant means
the model can see the future.

All tests are offline — no network calls, no database reads.
"""
from __future__ import annotations

from datetime import datetime, timezone

import pandas as pd
import pytest

from modules.analysis.technical.indicators import calculate_indicators, _filter_to_date
from modules.analysis.technical.volume_analysis import calculate_volume_metrics
from modules.analysis.technical.vol_regime import classify_vol_regime
from modules.analysis.technical.support_resistance import find_levels
from modules.analysis.technical.technical_analyzer import TechnicalAnalyzer
from modules.engines.signal_engine import SignalEngine
from modules.reporting.models import (
    MacroDriverScore, MacroResult, NewsResult, PriceData,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _append_future_bar(df: pd.DataFrame, *, close_spike: float = 999.0) -> pd.DataFrame:
    """Append one future business-day bar with an extreme close that would skew any indicator."""
    future_date = df.index[-1] + pd.tseries.offsets.BDay(1)
    row = pd.DataFrame(
        {
            "open":      [close_spike * 0.99],
            "high":      [close_spike * 1.02],
            "low":       [close_spike * 0.97],
            "close":     [close_spike],
            "volume":    [500_000_000.0],
            "adj_close": [close_spike],
        },
        index=[future_date],
    )
    return pd.concat([df, row])


def _make_macro(composite: float = 0.3) -> MacroResult:
    drivers = [
        MacroDriverScore("Test", "bullish", 1.0, "evidence", 0.125)
        for _ in range(8)
    ]
    return MacroResult(drivers=drivers, composite_score=composite,
                       analysis_date=datetime.now(timezone.utc))


def _make_news() -> NewsResult:
    return NewsResult(event_risk_level="low", analysis_datetime=datetime.now(timezone.utc))


# ---------------------------------------------------------------------------
# _filter_to_date unit tests
# ---------------------------------------------------------------------------

class TestFilterToDate:

    def test_filter_excludes_future_rows(self, sample_ohlcv, analysis_date):
        extended = _append_future_bar(sample_ohlcv)
        filtered = _filter_to_date(extended, analysis_date)
        assert len(filtered) == len(sample_ohlcv)

    def test_filter_includes_analysis_date_row(self, sample_ohlcv, analysis_date):
        filtered = _filter_to_date(sample_ohlcv, analysis_date)
        assert len(filtered) == len(sample_ohlcv)

    def test_filter_earlier_cutoff_removes_rows(self, sample_ohlcv):
        earlier = datetime(2025, 6, 1, tzinfo=timezone.utc)
        filtered = _filter_to_date(sample_ohlcv, earlier)
        assert len(filtered) < len(sample_ohlcv)
        assert all(d <= earlier.date() for d in filtered.index.date)


# ---------------------------------------------------------------------------
# Indicator-level bias tests
# ---------------------------------------------------------------------------

class TestIndicatorBias:

    def test_indicators_unchanged_after_future_row(self, sample_ohlcv, analysis_date):
        """Adding a future bar must not change any indicator at analysis_date."""
        result_base, _ = calculate_indicators(sample_ohlcv, analysis_date)
        extended = _append_future_bar(sample_ohlcv)
        result_ext, _ = calculate_indicators(extended, analysis_date)

        numeric_keys = [k for k, v in result_base.items()
                        if isinstance(v, (int, float)) and v is not None]
        for key in numeric_keys:
            assert abs(result_base[key] - result_ext[key]) < 1e-9, (
                f"Indicator '{key}' changed when future row was appended"
            )

    def test_volume_metrics_unchanged_after_future_row(self, sample_ohlcv, analysis_date):
        base_vol, _ = calculate_volume_metrics(sample_ohlcv, analysis_date)
        extended = _append_future_bar(sample_ohlcv)
        ext_vol, _ = calculate_volume_metrics(extended, analysis_date)

        for key in base_vol:
            bv = base_vol[key]
            ev = ext_vol[key]
            if isinstance(bv, float) and isinstance(ev, float):
                assert abs(bv - ev) < 1e-9, (
                    f"Volume metric '{key}' changed when future row was appended"
                )

    def test_vol_regime_unchanged_after_future_row(self, sample_ohlcv, analysis_date):
        regime_base, _ = classify_vol_regime(sample_ohlcv, analysis_date)
        extended = _append_future_bar(sample_ohlcv)
        regime_ext, _ = classify_vol_regime(extended, analysis_date)
        assert regime_base == regime_ext

    def test_support_resistance_unchanged_after_future_row(self, sample_ohlcv, analysis_date):
        sup_base, res_base, _ = find_levels(sample_ohlcv, analysis_date)
        extended = _append_future_bar(sample_ohlcv)
        sup_ext, res_ext, _ = find_levels(extended, analysis_date)
        assert sup_base == sup_ext
        assert res_base == res_ext


# ---------------------------------------------------------------------------
# TechnicalAnalyzer bias tests
# ---------------------------------------------------------------------------

class TestTechnicalAnalyzerBias:

    def test_technical_result_unchanged_after_future_row(self, sample_ohlcv, analysis_date):
        price_base = PriceData(ticker="SLV", ohlcv=sample_ohlcv,
                               fetched_at=datetime.now(timezone.utc), is_stale=False)
        price_ext  = PriceData(ticker="SLV", ohlcv=_append_future_bar(sample_ohlcv),
                               fetched_at=datetime.now(timezone.utc), is_stale=False)

        analyzer = TechnicalAnalyzer()
        result_base = analyzer.analyze(price_base, analysis_date=analysis_date)
        result_ext  = analyzer.analyze(price_ext,  analysis_date=analysis_date)

        assert result_base.trend_direction == result_ext.trend_direction
        assert result_base.vol_regime      == result_ext.vol_regime

        for key in result_base.indicators:
            bv = result_base.indicators[key]
            ev = result_ext.indicators[key]
            if isinstance(bv, float) and isinstance(ev, float):
                assert abs(bv - ev) < 1e-9, (
                    f"TechnicalResult indicator '{key}' changed when future row appended"
                )

    def test_advancing_analysis_date_changes_result(self, sample_ohlcv):
        """Proves the filter IS doing work — advancing the date should change results."""
        price_data = PriceData(ticker="SLV", ohlcv=sample_ohlcv,
                               fetched_at=datetime.now(timezone.utc), is_stale=False)
        analyzer = TechnicalAnalyzer()

        # Date at 50 bars from the start
        last   = sample_ohlcv.index[-1]
        date_t = datetime(last.year, last.month, last.day, tzinfo=timezone.utc)

        # 130 bars earlier — short enough that SMA(200) is unavailable
        earlier_ts = sample_ohlcv.index[50]
        date_early = datetime(earlier_ts.year, earlier_ts.month, earlier_ts.day,
                              tzinfo=timezone.utc)

        result_full  = analyzer.analyze(price_data, analysis_date=date_t)
        result_early = analyzer.analyze(price_data, analysis_date=date_early)

        # Close prices must differ (different last bar)
        assert result_full.indicators["close"] != result_early.indicators["close"]


# ---------------------------------------------------------------------------
# Signal-engine bias test (full pipeline)
# ---------------------------------------------------------------------------

class TestSignalEngineBias:

    def test_signal_unchanged_after_future_row(self, sample_ohlcv, analysis_date):
        """
        The signal produced for analysis_date must be identical whether the
        DataFrame has only T-rows or also has a T+1 row with extreme prices.
        """
        def _build_price(df: pd.DataFrame) -> PriceData:
            return PriceData(ticker="SLV", ohlcv=df,
                             fetched_at=datetime.now(timezone.utc), is_stale=False)

        analyzer = TechnicalAnalyzer()
        engine   = SignalEngine()
        macro    = _make_macro(0.3)
        news     = _make_news()

        from config.trading_styles import TradingStyle

        price_base = _build_price(sample_ohlcv)
        price_ext  = _build_price(_append_future_bar(sample_ohlcv))

        tech_base = analyzer.analyze(price_base, analysis_date=analysis_date)
        tech_ext  = analyzer.analyze(price_ext,  analysis_date=analysis_date)

        sig_base = engine.generate(price_base, tech_base, macro, news,
                                   TradingStyle.SWING, analysis_datetime=analysis_date)
        sig_ext  = engine.generate(price_ext,  tech_ext,  macro, news,
                                   TradingStyle.SWING, analysis_datetime=analysis_date)

        assert sig_base.action     == sig_ext.action
        assert sig_base.confidence == sig_ext.confidence
        assert sig_base.regime_label == sig_ext.regime_label
