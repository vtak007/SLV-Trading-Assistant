# Rev 1
"""Tests for technical indicator calculations."""
from datetime import datetime, timezone

import pytest

from modules.analysis.technical.indicators import calculate_indicators
from modules.analysis.technical.volume_analysis import calculate_volume_metrics
from modules.analysis.technical.vol_regime import classify_vol_regime
from modules.analysis.technical.support_resistance import find_levels
from modules.infrastructure.exceptions import ValidationError


class TestCalculateIndicators:
    def test_returns_expected_keys(self, sample_ohlcv, analysis_date):
        result, warnings = calculate_indicators(sample_ohlcv, analysis_date)
        for key in ("close", "sma_20", "sma_50", "rsi_14", "macd", "atr_14", "bb_upper"):
            assert key in result, f"Missing key: {key}"

    def test_close_is_last_bar(self, sample_ohlcv, analysis_date):
        result, _ = calculate_indicators(sample_ohlcv, analysis_date)
        assert abs(result["close"] - float(sample_ohlcv["close"].iloc[-1])) < 1e-6

    def test_no_nan_in_short_indicators(self, sample_ohlcv, analysis_date):
        result, _ = calculate_indicators(sample_ohlcv, analysis_date)
        for key in ("sma_20", "rsi_14", "macd", "atr_14"):
            assert result[key] is not None, f"{key} should not be None with 260 bars"

    def test_sma200_none_when_insufficient_data(self, sample_ohlcv, analysis_date):
        short_df = sample_ohlcv.tail(100)
        result, warnings = calculate_indicators(short_df, analysis_date)
        assert result.get("sma_200") is None
        assert any("SMA(200)" in w for w in warnings)

    def test_raises_on_too_few_bars(self, sample_ohlcv, analysis_date):
        tiny = sample_ohlcv.tail(10)
        with pytest.raises(ValidationError):
            calculate_indicators(tiny, analysis_date)

    def test_anti_lookahead(self, sample_ohlcv):
        """Signal on T-0 must equal signal on T-0 after appending a future row."""
        from datetime import timedelta
        import pandas as pd
        import numpy as np

        cutoff_date = sample_ohlcv.index[-1]
        ad = datetime(cutoff_date.year, cutoff_date.month, cutoff_date.day, tzinfo=timezone.utc)
        result_before, _ = calculate_indicators(sample_ohlcv, ad)

        # Append one extra future bar
        future_idx = cutoff_date + pd.tseries.offsets.BusinessDay(1)
        future_row = pd.DataFrame(
            {"open": [999], "high": [1000], "low": [990], "close": [999], "volume": [1e7], "adj_close": [999]},
            index=[future_idx],
        )
        extended = pd.concat([sample_ohlcv, future_row])
        result_after, _ = calculate_indicators(extended, ad)

        assert result_before["close"] == result_after["close"]
        assert result_before["sma_20"] == result_after["sma_20"]
        assert result_before["rsi_14"] == result_after["rsi_14"]


class TestVolumeMetrics:
    def test_returns_expected_keys(self, sample_ohlcv, analysis_date):
        result, warnings = calculate_volume_metrics(sample_ohlcv, analysis_date)
        assert "relative_volume" in result
        assert "obv_trend" in result

    def test_relative_volume_positive(self, sample_ohlcv, analysis_date):
        result, _ = calculate_volume_metrics(sample_ohlcv, analysis_date)
        assert result["relative_volume"] is None or result["relative_volume"] > 0


class TestVolRegime:
    def test_returns_valid_label(self, sample_ohlcv, analysis_date):
        regime, warnings = classify_vol_regime(sample_ohlcv, analysis_date)
        assert regime in ("low", "normal", "high", "extreme", "unknown")

    def test_returns_unknown_for_tiny_df(self, sample_ohlcv, analysis_date):
        regime, warnings = classify_vol_regime(sample_ohlcv.tail(5), analysis_date)
        assert regime == "unknown"
        assert warnings


class TestSupportResistance:
    def test_returns_sorted_levels(self, sample_ohlcv, analysis_date):
        support, resistance, _ = find_levels(sample_ohlcv, analysis_date)
        if len(support) >= 2:
            assert support[0] >= support[1], "Support should be descending (nearest first)"
        if len(resistance) >= 2:
            assert resistance[0] <= resistance[1], "Resistance should be ascending"

    def test_support_below_price(self, sample_ohlcv, analysis_date):
        current_price = float(sample_ohlcv["close"].iloc[-1])
        support, _, _ = find_levels(sample_ohlcv, analysis_date)
        for lvl in support:
            assert lvl < current_price * 1.005, f"Support {lvl:.2f} should be below price {current_price:.2f}"

    def test_resistance_above_price(self, sample_ohlcv, analysis_date):
        current_price = float(sample_ohlcv["close"].iloc[-1])
        _, resistance, _ = find_levels(sample_ohlcv, analysis_date)
        for lvl in resistance:
            assert lvl > current_price * 0.995, f"Resistance {lvl:.2f} should be above price {current_price:.2f}"
