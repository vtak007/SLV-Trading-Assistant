# Rev 1
"""Tests for PriceFetcher — uses mocked yfinance to avoid network calls."""
import pickle
import time
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import numpy as np
import pandas as pd
import pytest

from modules.collection.price_fetcher import PriceFetcher, _normalize_columns
from modules.infrastructure.exceptions import DataFetchError
from modules.reporting.models import PriceData


def _make_df(n: int = 200) -> pd.DataFrame:
    """Synthetic OHLCV with dates ending *today* so staleness check passes."""
    rng = np.random.default_rng(0)
    end = pd.Timestamp.today().normalize()
    dates = pd.bdate_range(end=end, periods=n)
    close = 28.0 + rng.normal(0, 0.5, n).cumsum()
    return pd.DataFrame(
        {
            "Open":   close * 1.002,
            "High":   close * 1.015,
            "Low":    close * 0.985,
            "Close":  close,
            "Volume": rng.uniform(5e6, 12e6, n),
        },
        index=dates,
    )


class TestNormalizeColumns:
    def test_lowercase_rename(self):
        df = _make_df()
        result = _normalize_columns(df)
        assert set(result.columns) >= {"open", "high", "low", "close", "volume", "adj_close"}

    def test_adj_close_added_when_absent(self):
        df = _make_df()
        result = _normalize_columns(df)
        assert "adj_close" in result.columns
        # Values should match close (name differs intentionally)
        pd.testing.assert_series_equal(
            result["adj_close"], result["close"], check_names=False
        )

    def test_multiindex_columns_flattened(self):
        df = _make_df()
        df.columns = pd.MultiIndex.from_tuples([(c, "SLV") for c in df.columns])
        result = _normalize_columns(df)
        assert not isinstance(result.columns, pd.MultiIndex)


class TestPriceFetcherMocked:
    @patch("modules.collection.price_fetcher.yf.download")
    def test_returns_price_data(self, mock_dl):
        mock_dl.return_value = _make_df(200)
        fetcher = PriceFetcher()
        pd_obj = fetcher.fetch_price_data("SLV", force_refresh=True)

        assert isinstance(pd_obj, PriceData)
        assert pd_obj.ticker == "SLV"
        assert len(pd_obj.ohlcv) == 200
        assert not pd_obj.is_stale    # dates end today so should be fresh

    @patch("modules.collection.price_fetcher.yf.download")
    def test_empty_response_raises_data_fetch_error(self, mock_dl, tmp_path, monkeypatch):
        """Empty yfinance response raises DataFetchError (no cache to fall back on)."""
        monkeypatch.setattr("modules.collection.base_fetcher.CACHE_DIR", tmp_path)
        mock_dl.return_value = pd.DataFrame()
        fetcher = PriceFetcher()
        fetcher._cache_dir = tmp_path   # point fetcher at empty tmp dir
        with pytest.raises(DataFetchError):
            fetcher.fetch_price_data("SLV", force_refresh=True)

    @patch("modules.collection.price_fetcher.yf.download")
    def test_stale_cache_fallback(self, mock_dl, tmp_path, monkeypatch):
        """When live fetch fails, a stale cache entry should be returned."""
        monkeypatch.setattr("modules.collection.base_fetcher.CACHE_DIR", tmp_path)

        good_df = _make_df(150)
        stale_payload = {"fetched_at": time.time() - 86400 * 10, "data": good_df}
        cache_file = tmp_path / "SLV.pkl"
        with cache_file.open("wb") as f:
            pickle.dump(stale_payload, f)

        mock_dl.side_effect = Exception("network down")
        fetcher = PriceFetcher()
        fetcher._cache_dir = tmp_path
        pd_obj = fetcher.fetch_price_data("SLV", force_refresh=True)

        assert len(pd_obj.ohlcv) == 150
