# Rev 1
"""Shared pytest fixtures — synthetic OHLCV data, no network calls."""
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

# Ensure project root is importable when running pytest from any cwd
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


@pytest.fixture
def sample_ohlcv() -> pd.DataFrame:
    """
    260 bars of synthetic SLV-like OHLCV data.
    Seeded for reproducibility; suitable for all indicator tests.
    """
    rng = np.random.default_rng(42)
    n = 260
    dates = pd.date_range("2025-01-02", periods=n, freq="B")

    returns = rng.normal(0.0003, 0.012, n)
    close = 28.0 * np.exp(np.cumsum(returns))

    spread = rng.uniform(0.008, 0.025, n)
    high   = close * (1 + spread)
    low    = close * (1 - spread)
    open_  = close * (1 + rng.normal(0, 0.004, n))
    volume = rng.uniform(4e6, 14e6, n)

    return pd.DataFrame(
        {
            "open":      open_,
            "high":      high,
            "low":       low,
            "close":     close,
            "volume":    volume,
            "adj_close": close,
        },
        index=dates,
    )


@pytest.fixture
def analysis_date(sample_ohlcv) -> "datetime":
    from datetime import datetime, timezone
    last = sample_ohlcv.index[-1]
    return datetime(last.year, last.month, last.day, tzinfo=timezone.utc)


# ---------------------------------------------------------------------------
# Session 2 — Macro fixtures (synthetic FRED-like series, no network)
# ---------------------------------------------------------------------------

@pytest.fixture
def macro_analysis_date():
    from datetime import datetime, timezone
    return datetime(2026, 5, 27, tzinfo=timezone.utc)


@pytest.fixture
def fred_monthly_dates():
    """60 monthly dates starting 2021-01-01 (all before macro_analysis_date)."""
    return pd.date_range("2021-01-01", periods=60, freq="MS")


@pytest.fixture
def fred_daily_dates():
    """365 business-day dates starting 2025-01-02."""
    return pd.date_range("2025-01-02", periods=365, freq="B")
