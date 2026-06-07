# Rev 1
"""
Offline mock mode tests (SLV_OFFLINE=1).

Verifies that setting SLV_OFFLINE=1:
  - Prevents all live network calls
  - Serves data from the local pickle cache even when stale
  - Raises DataFetchError when no cache exists for a key
  - Ignores force_refresh=True (never re-fetches)

All tests are fully offline — no network calls, no database reads.
"""
from __future__ import annotations

import os
import pickle
import time
from pathlib import Path

import pandas as pd
import pytest

from modules.collection.base_fetcher import BaseFetcher
from modules.infrastructure.exceptions import DataFetchError


# ---------------------------------------------------------------------------
# Concrete minimal BaseFetcher subclass for testing
# ---------------------------------------------------------------------------

class _CountingFetcher(BaseFetcher):
    """Records how many times _fetch_fresh was called."""

    def __init__(self, cache_dir: Path, response=None) -> None:
        super().__init__(cache_ttl_seconds=3600, max_retries=1)
        self._cache_dir = cache_dir
        self._response  = response
        self.fetch_fresh_calls = 0

    def _fetch_fresh(self, key: str):
        self.fetch_fresh_calls += 1
        if self._response is None:
            raise DataFetchError(f"Simulated network failure for '{key}'")
        return self._response


def _write_cache(cache_dir: Path, key: str, data, age_seconds: int = 0) -> None:
    """Write a fake pickle cache entry for the given key."""
    safe = key.replace("/", "_").replace("^", "").replace(" ", "_")
    path = cache_dir / f"{safe}.pkl"
    payload = {"fetched_at": time.time() - age_seconds, "data": data}
    with path.open("wb") as f:
        pickle.dump(payload, f, protocol=pickle.HIGHEST_PROTOCOL)


# ---------------------------------------------------------------------------
# Offline mode tests
# ---------------------------------------------------------------------------

class TestOfflineMode:

    def test_offline_serves_fresh_cache(self, tmp_path, monkeypatch):
        monkeypatch.setenv("SLV_OFFLINE", "1")
        expected = pd.DataFrame({"close": [30.0]})
        _write_cache(tmp_path, "SLV", expected, age_seconds=0)

        fetcher = _CountingFetcher(cache_dir=tmp_path, response=None)
        result  = fetcher.fetch("SLV")

        pd.testing.assert_frame_equal(result, expected)
        assert fetcher.fetch_fresh_calls == 0, "_fetch_fresh should never be called in offline mode"

    def test_offline_serves_stale_cache(self, tmp_path, monkeypatch):
        """In offline mode a stale cache entry is returned without complaint."""
        monkeypatch.setenv("SLV_OFFLINE", "1")
        expected = pd.DataFrame({"close": [25.0]})
        # Cache written 10 hours ago — well past the 1-hour TTL
        _write_cache(tmp_path, "SLV", expected, age_seconds=36_000)

        fetcher = _CountingFetcher(cache_dir=tmp_path, response=None)
        result  = fetcher.fetch("SLV")

        pd.testing.assert_frame_equal(result, expected)
        assert fetcher.fetch_fresh_calls == 0

    def test_offline_raises_when_no_cache(self, tmp_path, monkeypatch):
        monkeypatch.setenv("SLV_OFFLINE", "1")
        fetcher = _CountingFetcher(cache_dir=tmp_path, response=None)

        with pytest.raises(DataFetchError, match="Offline mode"):
            fetcher.fetch("MISSING_KEY")

        assert fetcher.fetch_fresh_calls == 0

    def test_offline_ignores_force_refresh(self, tmp_path, monkeypatch):
        """force_refresh=True must have no effect in offline mode."""
        monkeypatch.setenv("SLV_OFFLINE", "1")
        expected = {"value": 42}
        _write_cache(tmp_path, "MY_KEY", expected, age_seconds=0)

        fetcher = _CountingFetcher(cache_dir=tmp_path, response={"value": 99})
        result  = fetcher.fetch("MY_KEY", force_refresh=True)

        assert result == expected        # cache served, not the "live" response
        assert fetcher.fetch_fresh_calls == 0

    def test_online_mode_calls_fetch_fresh_on_cache_miss(self, tmp_path, monkeypatch):
        """Without SLV_OFFLINE set, a cache miss triggers _fetch_fresh."""
        monkeypatch.delenv("SLV_OFFLINE", raising=False)
        expected = {"price": 30.0}
        fetcher  = _CountingFetcher(cache_dir=tmp_path, response=expected)

        result = fetcher.fetch("LIVE_KEY")

        assert result == expected
        assert fetcher.fetch_fresh_calls == 1

    def test_online_mode_skips_fetch_on_fresh_cache(self, tmp_path, monkeypatch):
        """Without SLV_OFFLINE, a fresh cache hit must not call _fetch_fresh."""
        monkeypatch.delenv("SLV_OFFLINE", raising=False)
        cached_data = {"price": 28.0}
        _write_cache(tmp_path, "CACHED_KEY", cached_data, age_seconds=0)

        fetcher = _CountingFetcher(cache_dir=tmp_path, response={"price": 999.0})
        result  = fetcher.fetch("CACHED_KEY")

        assert result == cached_data
        assert fetcher.fetch_fresh_calls == 0
