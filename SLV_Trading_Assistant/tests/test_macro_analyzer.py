# Rev 1
"""
Unit tests for the macro analysis pipeline.
All tests use synthetic fixtures -- no network calls required.
"""
from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from modules.analysis.macro.yield_analyzer import analyze_real_yield, analyze_nominal_yield
from modules.analysis.macro.dollar_analyzer import analyze_dollar
from modules.analysis.macro.inflation_analyzer import analyze_cpi, analyze_ppi
from modules.analysis.macro.fed_policy_analyzer import analyze_fed_policy
from modules.analysis.macro.gs_ratio_analyzer import analyze_gs_ratio
from modules.analysis.macro.sentiment_analyzer import analyze_sentiment


# ===========================================================================
# Helpers
# ===========================================================================

def _flat(dates, value: float, name: str) -> pd.Series:
    return pd.Series(value, index=dates, name=name)


def _ramp(dates, start: float, end: float, name: str) -> pd.Series:
    return pd.Series(np.linspace(start, end, len(dates)), index=dates, name=name)


def _compound_monthly(dates, start: float, annual_rate: float, name: str) -> pd.Series:
    """Monthly compounding from `start` at `annual_rate`."""
    vals = [start * (1 + annual_rate / 12) ** i for i in range(len(dates))]
    return pd.Series(vals, index=dates, name=name)


# ===========================================================================
# Real Yield
# ===========================================================================

class TestRealYield:

    def test_negative_real_yield_is_bullish(self, fred_monthly_dates, macro_analysis_date):
        dgs10  = _flat(fred_monthly_dates, 2.0, "DGS10")
        t10yie = _flat(fred_monthly_dates, 3.0, "T10YIE")  # real = -1%
        r = analyze_real_yield(dgs10, t10yie, macro_analysis_date)
        assert r.score == "bullish"
        assert r.value is not None and r.value < 0

    def test_low_positive_real_yield_is_bullish(self, fred_monthly_dates, macro_analysis_date):
        dgs10  = _flat(fred_monthly_dates, 4.0, "DGS10")
        t10yie = _flat(fred_monthly_dates, 3.5, "T10YIE")  # real = 0.5%
        r = analyze_real_yield(dgs10, t10yie, macro_analysis_date)
        assert r.score == "bullish"

    def test_elevated_real_yield_is_bearish(self, fred_monthly_dates, macro_analysis_date):
        dgs10  = _flat(fred_monthly_dates, 5.0, "DGS10")
        t10yie = _flat(fred_monthly_dates, 2.0, "T10YIE")  # real = +3%
        r = analyze_real_yield(dgs10, t10yie, macro_analysis_date)
        assert r.score == "bearish"

    def test_empty_series_returns_unknown(self, macro_analysis_date):
        r = analyze_real_yield(pd.Series(dtype=float), pd.Series(dtype=float), macro_analysis_date)
        assert r.score == "unknown"
        assert r.value is None

    def test_weight_is_correct(self, fred_monthly_dates, macro_analysis_date):
        dgs10  = _flat(fred_monthly_dates, 4.0, "DGS10")
        t10yie = _flat(fred_monthly_dates, 3.0, "T10YIE")
        r = analyze_real_yield(dgs10, t10yie, macro_analysis_date)
        assert r.weight == pytest.approx(0.25)


# ===========================================================================
# Nominal Yield
# ===========================================================================

class TestNominalYield:

    def test_falling_yield_is_bullish(self, fred_monthly_dates, macro_analysis_date):
        dgs10 = _ramp(fred_monthly_dates, 5.0, 3.0, "DGS10")
        r = analyze_nominal_yield(dgs10, macro_analysis_date)
        assert r.score == "bullish"

    def test_rising_yield_is_bearish(self, fred_monthly_dates, macro_analysis_date):
        dgs10 = _ramp(fred_monthly_dates, 3.0, 5.5, "DGS10")
        r = analyze_nominal_yield(dgs10, macro_analysis_date)
        assert r.score == "bearish"

    def test_stable_yield_is_neutral(self, fred_monthly_dates, macro_analysis_date):
        dgs10 = _flat(fred_monthly_dates, 4.5, "DGS10")
        r = analyze_nominal_yield(dgs10, macro_analysis_date)
        assert r.score == "neutral"

    def test_empty_returns_unknown(self, macro_analysis_date):
        r = analyze_nominal_yield(pd.Series(dtype=float), macro_analysis_date)
        assert r.score == "unknown"


# ===========================================================================
# Dollar
# ===========================================================================

class TestDollar:

    def test_weakening_dollar_is_bullish(self, fred_monthly_dates, macro_analysis_date):
        dtwex = _ramp(fred_monthly_dates, 130.0, 120.0, "DTWEXBGS")
        r = analyze_dollar(dtwex, macro_analysis_date)
        assert r.score == "bullish"

    def test_strengthening_dollar_is_bearish(self, fred_monthly_dates, macro_analysis_date):
        dtwex = _ramp(fred_monthly_dates, 120.0, 130.0, "DTWEXBGS")
        r = analyze_dollar(dtwex, macro_analysis_date)
        assert r.score == "bearish"

    def test_stable_dollar_is_neutral(self, fred_monthly_dates, macro_analysis_date):
        dtwex = _flat(fred_monthly_dates, 125.0, "DTWEXBGS")
        r = analyze_dollar(dtwex, macro_analysis_date)
        assert r.score == "neutral"

    def test_empty_returns_unknown(self, macro_analysis_date):
        r = analyze_dollar(pd.Series(dtype=float), macro_analysis_date)
        assert r.score == "unknown"

    def test_weight_is_correct(self, fred_monthly_dates, macro_analysis_date):
        dtwex = _flat(fred_monthly_dates, 125.0, "DTWEXBGS")
        r = analyze_dollar(dtwex, macro_analysis_date)
        assert r.weight == pytest.approx(0.20)


# ===========================================================================
# CPI
# ===========================================================================

class TestCPI:

    def test_high_yoy_is_bullish(self, fred_monthly_dates, macro_analysis_date):
        # ~5% annual growth
        cpi = _compound_monthly(fred_monthly_dates, 300.0, 0.05, "CPIAUCSL")
        r = analyze_cpi(cpi, macro_analysis_date)
        assert r.score == "bullish"
        assert r.value is not None and r.value > 4.0

    def test_low_yoy_is_bearish(self, fred_monthly_dates, macro_analysis_date):
        # ~0.5% annual growth
        cpi = _compound_monthly(fred_monthly_dates, 300.0, 0.005, "CPIAUCSL")
        r = analyze_cpi(cpi, macro_analysis_date)
        assert r.score == "bearish"

    def test_moderate_yoy_is_neutral(self, fred_monthly_dates, macro_analysis_date):
        # ~2% annual growth
        cpi = _compound_monthly(fred_monthly_dates, 300.0, 0.02, "CPIAUCSL")
        r = analyze_cpi(cpi, macro_analysis_date)
        assert r.score == "neutral"

    def test_empty_returns_unknown(self, macro_analysis_date):
        r = analyze_cpi(pd.Series(dtype=float), macro_analysis_date)
        assert r.score == "unknown"

    def test_short_history_returns_unknown(self, macro_analysis_date):
        dates = pd.date_range("2025-12-01", periods=5, freq="MS")
        cpi = _flat(dates, 310.0, "CPIAUCSL")
        r = analyze_cpi(cpi, macro_analysis_date)
        assert r.score == "unknown"


# ===========================================================================
# PPI
# ===========================================================================

class TestPPI:

    def test_elevated_ppi_is_bullish(self, fred_monthly_dates, macro_analysis_date):
        ppi = _compound_monthly(fred_monthly_dates, 120.0, 0.04, "PPIFIS")
        r = analyze_ppi(ppi, macro_analysis_date)
        assert r.score == "bullish"

    def test_subdued_ppi_is_bearish(self, fred_monthly_dates, macro_analysis_date):
        ppi = _compound_monthly(fred_monthly_dates, 120.0, 0.005, "PPIFIS")
        r = analyze_ppi(ppi, macro_analysis_date)
        assert r.score == "bearish"

    def test_empty_returns_unknown(self, macro_analysis_date):
        r = analyze_ppi(pd.Series(dtype=float), macro_analysis_date)
        assert r.score == "unknown"


# ===========================================================================
# Fed Policy
# ===========================================================================

class TestFedPolicy:

    def test_cutting_cycle_is_bullish(self, fred_monthly_dates, macro_analysis_date):
        fedfunds = _ramp(fred_monthly_dates, 5.5, 3.5, "FEDFUNDS")
        r = analyze_fed_policy(fedfunds, macro_analysis_date)
        assert r.score == "bullish"

    def test_hiking_cycle_is_bearish(self, fred_monthly_dates, macro_analysis_date):
        fedfunds = _ramp(fred_monthly_dates, 0.25, 5.5, "FEDFUNDS")
        r = analyze_fed_policy(fedfunds, macro_analysis_date)
        assert r.score == "bearish"

    def test_elevated_stable_is_bearish(self, fred_monthly_dates, macro_analysis_date):
        fedfunds = _flat(fred_monthly_dates, 5.25, "FEDFUNDS")
        r = analyze_fed_policy(fedfunds, macro_analysis_date)
        assert r.score == "bearish"

    def test_accommodative_is_bullish(self, fred_monthly_dates, macro_analysis_date):
        fedfunds = _flat(fred_monthly_dates, 0.25, "FEDFUNDS")
        r = analyze_fed_policy(fedfunds, macro_analysis_date)
        assert r.score == "bullish"

    def test_empty_returns_unknown(self, macro_analysis_date):
        r = analyze_fed_policy(pd.Series(dtype=float), macro_analysis_date)
        assert r.score == "unknown"


# ===========================================================================
# Gold-Silver Ratio
# ===========================================================================

class TestGSRatio:

    def test_high_ratio_is_bullish(self, fred_daily_dates, macro_analysis_date):
        gld = _flat(fred_daily_dates, 200.0, "GLD")
        slv = _flat(fred_daily_dates, 1.5, "SLV")    # ratio ~133
        r = analyze_gs_ratio(gld, slv, macro_analysis_date)
        assert r.score == "bullish"
        assert r.value is not None and r.value > 100

    def test_average_ratio_is_neutral(self, fred_daily_dates, macro_analysis_date):
        # ETF ratio ~8.0 = near historical average (thresholds use ETF-scale, not spot G/S)
        gld = _flat(fred_daily_dates, 200.0, "GLD")
        slv = _flat(fred_daily_dates, 25.0, "SLV")   # ratio = 8.0 -> neutral
        r = analyze_gs_ratio(gld, slv, macro_analysis_date)
        assert r.score == "neutral"

    def test_low_ratio_is_bearish(self, fred_daily_dates, macro_analysis_date):
        # ETF ratio ~4.6 < _HISTORICAL_LOW (5.2) -> silver relatively expensive -> bearish
        gld = _flat(fred_daily_dates, 200.0, "GLD")
        slv = _flat(fred_daily_dates, 43.0, "SLV")   # ratio = 4.65 -> bearish
        r = analyze_gs_ratio(gld, slv, macro_analysis_date)
        assert r.score == "bearish"

    def test_empty_gld_returns_unknown(self, fred_daily_dates, macro_analysis_date):
        slv = _flat(fred_daily_dates, 30.0, "SLV")
        r = analyze_gs_ratio(pd.Series(dtype=float), slv, macro_analysis_date)
        assert r.score == "unknown"

    def test_empty_slv_returns_unknown(self, fred_daily_dates, macro_analysis_date):
        gld = _flat(fred_daily_dates, 200.0, "GLD")
        r = analyze_gs_ratio(gld, pd.Series(dtype=float), macro_analysis_date)
        assert r.score == "unknown"


# ===========================================================================
# Sentiment
# ===========================================================================

class TestSentiment:

    def test_fear_regime_is_bullish(self, fred_daily_dates, macro_analysis_date):
        vixy = _flat(fred_daily_dates, 30.0, "VIXY")
        r = analyze_sentiment(vixy, macro_analysis_date)
        assert r.score == "bullish"

    def test_panic_regime_is_neutral(self, fred_daily_dates, macro_analysis_date):
        vixy = _flat(fred_daily_dates, 50.0, "VIXY")
        r = analyze_sentiment(vixy, macro_analysis_date)
        assert r.score == "neutral"

    def test_calm_regime_is_neutral(self, fred_daily_dates, macro_analysis_date):
        vixy = _flat(fred_daily_dates, 12.0, "VIXY")
        r = analyze_sentiment(vixy, macro_analysis_date)
        assert r.score == "neutral"

    def test_empty_returns_unknown(self, macro_analysis_date):
        r = analyze_sentiment(pd.Series(dtype=float), macro_analysis_date)
        assert r.score == "unknown"


# ===========================================================================
# Anti-look-ahead: all analyzers must respect analysis_date
# ===========================================================================

class TestAntiLookAhead:

    def test_nominal_yield_respects_cutoff(self):
        """
        Data before cutoff shows a falling trend (bullish).
        Data after cutoff includes a sharp spike (bearish).
        Score at cutoff must be bullish; score after the spike must be bearish.
        """
        dates = pd.date_range("2024-01-01", periods=24, freq="MS")
        # months 0-17: linspace(5.5, 3.5) — falling; months 18-23: spike to 7+
        vals = list(np.linspace(5.5, 3.5, 18)) + [5.5, 6.0, 6.5, 7.0, 7.5, 8.0]
        dgs10 = pd.Series(vals, index=dates, name="DGS10")

        cutoff = datetime(2025, 6, 30, tzinfo=timezone.utc)
        future = datetime(2026, 5, 27, tzinfo=timezone.utc)

        assert analyze_nominal_yield(dgs10, cutoff).score == "bullish"
        assert analyze_nominal_yield(dgs10, future).score == "bearish"

    def test_real_yield_respects_cutoff(self):
        """Negative real yield at cutoff (bullish), positive after (bearish)."""
        dates = pd.date_range("2024-01-01", periods=24, freq="MS")
        dgs10_vals  = list(np.linspace(2.0, 2.5, 18)) + [3.5, 4.0, 4.5, 5.0, 5.5, 6.0]
        t10yie_vals = [3.0] * 24  # constant breakeven
        dgs10  = pd.Series(dgs10_vals,  index=dates, name="DGS10")
        t10yie = pd.Series(t10yie_vals, index=dates, name="T10YIE")

        cutoff = datetime(2025, 6, 30, tzinfo=timezone.utc)
        future = datetime(2026, 5, 27, tzinfo=timezone.utc)

        # At cutoff: real yield = ~2.5 - 3.0 = -0.5% (bullish)
        assert analyze_real_yield(dgs10, t10yie, cutoff).score == "bullish"
        # At future: real yield = ~6.0 - 3.0 = +3% (bearish)
        assert analyze_real_yield(dgs10, t10yie, future).score == "bearish"

    def test_dollar_respects_cutoff(self):
        """Falling dollar at cutoff (bullish), rising dollar after (bearish)."""
        dates = pd.date_range("2024-01-01", periods=24, freq="MS")
        vals  = list(np.linspace(130.0, 120.0, 18)) + [122, 125, 128, 131, 135, 140]
        dtwex = pd.Series(vals, index=dates, name="DTWEXBGS")

        cutoff = datetime(2025, 6, 30, tzinfo=timezone.utc)
        future = datetime(2026, 5, 27, tzinfo=timezone.utc)

        assert analyze_dollar(dtwex, cutoff).score == "bullish"
        assert analyze_dollar(dtwex, future).score == "bearish"

    def test_fed_policy_respects_cutoff(self):
        """Cutting cycle at cutoff (bullish), hiking cycle after (bearish)."""
        dates = pd.date_range("2024-01-01", periods=24, freq="MS")
        vals  = list(np.linspace(5.5, 3.0, 18)) + [3.5, 4.0, 4.5, 5.0, 5.5, 6.0]
        fedfunds = pd.Series(vals, index=dates, name="FEDFUNDS")

        cutoff = datetime(2025, 6, 30, tzinfo=timezone.utc)
        future = datetime(2026, 5, 27, tzinfo=timezone.utc)

        assert analyze_fed_policy(fedfunds, cutoff).score == "bullish"
        assert analyze_fed_policy(fedfunds, future).score == "bearish"
