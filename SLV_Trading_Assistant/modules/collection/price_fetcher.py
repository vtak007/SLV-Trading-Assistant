# Rev 2  (Schwab as primary price source; yfinance as fallback)
"""Price fetcher: Schwab primary, yfinance fallback. Downloads OHLCV for SLV and related ETFs."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import numpy as np
import pandas as pd
import yfinance as yf

from config.data_sources import PRICE_TICKERS
from config.settings import DEFAULT_LOOKBACK_DAYS, PRICE_CACHE_TTL
from modules.collection.base_fetcher import BaseFetcher
from modules.collection.schwab_client import get_schwab_client
from modules.infrastructure.exceptions import DataFetchError
from modules.infrastructure.logger import get_logger
from modules.infrastructure.validators import validate_ohlcv
from modules.reporting.models import PriceData

log = get_logger("price_fetcher")


class PriceFetcher(BaseFetcher):

    def __init__(self) -> None:
        super().__init__(cache_ttl_seconds=PRICE_CACHE_TTL)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def fetch_price_data(self, ticker: str, force_refresh: bool = False) -> PriceData:
        """Return a validated PriceData object for `ticker`."""
        ticker = ticker.upper()
        df: pd.DataFrame = self.fetch(ticker, force_refresh=force_refresh)

        is_stale, warnings = _check_staleness(df, ticker)

        return PriceData(
            ticker=ticker,
            ohlcv=df,
            fetched_at=datetime.now(timezone.utc),
            is_stale=is_stale,
            warnings=warnings,
            source=_fetch_source.get(ticker, "yfinance"),
        )

    def fetch_all(self, force_refresh: bool = False) -> dict[str, PriceData]:
        """Fetch all configured tickers. Logs and skips any that fail."""
        results: dict[str, PriceData] = {}
        for ticker in PRICE_TICKERS:
            try:
                results[ticker] = self.fetch_price_data(ticker, force_refresh=force_refresh)
                log.info("Fetched %-6s  %d rows, stale=%s", ticker, len(results[ticker].ohlcv), results[ticker].is_stale)
            except DataFetchError as exc:
                log.error("Skipping %s — %s", ticker, exc)
        return results

    # ------------------------------------------------------------------
    # BaseFetcher contract
    # ------------------------------------------------------------------

    def _fetch_fresh(self, key: str) -> pd.DataFrame:
        ticker = key.upper()

        client = get_schwab_client()
        if client is not None:
            try:
                log.info("Downloading %s from Schwab", ticker)
                df = _fetch_from_schwab(client, ticker)
                _fetch_source[ticker] = "schwab"
                return df
            except Exception as exc:
                log.warning(
                    "Schwab price fetch failed for %s (%s) — falling back to yfinance",
                    ticker, exc,
                )

        log.info("Downloading %s from yfinance", ticker)
        df = _fetch_from_yfinance(ticker)
        _fetch_source[ticker] = "yfinance"
        return df


# ---------------------------------------------------------------------------
# Module-level helpers
# ---------------------------------------------------------------------------

# Tracks the live-fetch source (schwab/yfinance) for the most recent _fetch_fresh call.
# Cache hits inherit the source stored when data was last fetched fresh.
_fetch_source: dict[str, str] = {}


def _fetch_from_schwab(client, ticker: str) -> pd.DataFrame:
    """Download daily OHLCV from Schwab price history API."""
    end   = datetime.now(timezone.utc)
    start = end - timedelta(days=DEFAULT_LOOKBACK_DAYS)

    resp = client.get_price_history_every_day(
        ticker,
        start_datetime=start,
        end_datetime=end,
        need_previous_close=False,
    )

    if not resp.is_success:
        raise DataFetchError(f"Schwab API returned HTTP {resp.status_code} for {ticker}")

    data = resp.json()
    if data.get("empty", True) or not data.get("candles"):
        raise DataFetchError(f"Schwab returned empty candles for {ticker}")

    candles = data["candles"]
    df = pd.DataFrame(candles)

    # Convert epoch-ms timestamps to a tz-naive DatetimeIndex (same format as yfinance)
    df.index = pd.to_datetime(df["datetime"], unit="ms").normalize()
    df.index.name = "date"
    df = df.drop(columns=["datetime"])
    df = df.rename(columns=str.lower)

    if "adj_close" not in df.columns:
        df["adj_close"] = df["close"]

    validate_ohlcv(df, ticker)
    return df


def _fetch_from_yfinance(ticker: str) -> pd.DataFrame:
    """Download daily OHLCV from yfinance (fallback source)."""
    end   = datetime.now(timezone.utc)
    start = end - timedelta(days=DEFAULT_LOOKBACK_DAYS)

    try:
        raw = yf.download(
            ticker,
            start=start.strftime("%Y-%m-%d"),
            end=end.strftime("%Y-%m-%d"),
            auto_adjust=True,
            progress=False,
            actions=False,
        )
    except Exception as exc:
        raise DataFetchError(f"yfinance download failed for {ticker}: {exc}") from exc

    if raw is None or raw.empty:
        raise DataFetchError(f"yfinance returned empty data for {ticker}")

    df = _normalize_yfinance_columns(raw)
    validate_ohlcv(df, ticker)
    return df


def _normalize_yfinance_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Standardise yfinance output to lowercase snake_case columns."""
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)

    df = df.copy()
    df.columns = df.columns.str.lower().str.replace(" ", "_", regex=False)

    if "adj_close" not in df.columns:
        df["adj_close"] = df["close"]

    return df


def _check_staleness(df: pd.DataFrame, ticker: str) -> tuple[bool, list[str]]:
    """Return (is_stale, warnings) based on the age of the most recent bar."""
    warnings: list[str] = []
    is_stale = False

    if df.empty:
        warnings.append(f"{ticker}: no price rows returned")
        return True, warnings

    last_date = pd.Timestamp(df.index[-1]).date()
    today = datetime.now(timezone.utc).date()
    trading_days_old = int(np.busday_count(last_date, today))

    if trading_days_old > 2:
        is_stale = True
        warnings.append(
            f"{ticker} price data is {trading_days_old} trading days old (last bar: {last_date})"
        )

    return is_stale, warnings
