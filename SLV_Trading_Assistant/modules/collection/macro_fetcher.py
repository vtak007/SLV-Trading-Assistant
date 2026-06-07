# Rev 2  (replaced pandas_datareader with direct FRED REST API -- distutils removed in Python 3.12+)
"""
FRED macro data fetcher using the FRED REST API directly.
Subclasses BaseFetcher to inherit pickle cache, retry, and stale fallback.
pandas_datareader is NOT used here due to distutils incompatibility on Python 3.13.
"""
from __future__ import annotations

from datetime import datetime, timedelta

import pandas as pd
import requests

from config.settings import FRED_API_KEY, MACRO_CACHE_TTL
from modules.collection.base_fetcher import BaseFetcher
from modules.infrastructure.exceptions import DataFetchError
from modules.infrastructure.logger import get_logger

log = get_logger("macro_fetcher")

_FRED_BASE_URL = "https://api.stlouisfed.org/fred/series/observations"
_LOOKBACK_YEARS = 5
_REQUEST_TIMEOUT = 15  # seconds


class MacroFetcher(BaseFetcher):

    def __init__(self) -> None:
        super().__init__(cache_ttl_seconds=MACRO_CACHE_TTL)

    def fetch_series(self, series_id: str, force_refresh: bool = False) -> pd.Series:
        """Return a pandas Series for a FRED series ID, using cache when fresh."""
        return self.fetch(series_id.upper(), force_refresh=force_refresh)

    def _fetch_fresh(self, key: str) -> pd.Series:
        if not FRED_API_KEY:
            raise DataFetchError(
                "FRED_API_KEY is not set -- add it to your .env file."
            )

        end   = datetime.today()
        start = end - timedelta(days=365 * _LOOKBACK_YEARS)

        params = {
            "series_id":        key,
            "api_key":          FRED_API_KEY,
            "file_type":        "json",
            "observation_start": start.strftime("%Y-%m-%d"),
            "observation_end":   end.strftime("%Y-%m-%d"),
        }

        try:
            resp = requests.get(_FRED_BASE_URL, params=params, timeout=_REQUEST_TIMEOUT)
            resp.raise_for_status()
        except requests.RequestException as exc:
            raise DataFetchError(f"FRED API request failed for {key}: {exc}") from exc

        payload = resp.json()
        observations = payload.get("observations", [])

        if not observations:
            raise DataFetchError(f"FRED returned no observations for series {key}")

        records = []
        for obs in observations:
            val_str = obs.get("value", "")
            if val_str == "." or val_str == "":   # FRED uses "." for missing values
                continue
            try:
                records.append((obs["date"], float(val_str)))
            except (ValueError, KeyError):
                continue

        if not records:
            raise DataFetchError(f"FRED series {key}: all observations are missing/NaN")

        dates, vals = zip(*records)
        series = pd.Series(
            list(vals),
            index=pd.to_datetime(list(dates)),
            name=key,
        )
        log.info(
            "Fetched FRED %s: %d obs (%s to %s)",
            key,
            len(series),
            series.index[0].date(),
            series.index[-1].date(),
        )
        return series
