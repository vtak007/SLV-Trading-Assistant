# Rev 1
"""
Intraday price fetcher for Day-style analysis.
Fetches 5-minute OHLCV bars — Schwab primary, yfinance fallback.
Used in place of daily bars when trading_style == DAY.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pandas as pd
import yfinance as yf

from modules.collection.schwab_client import get_schwab_client
from modules.infrastructure.exceptions import DataFetchError
from modules.infrastructure.logger import get_logger
from modules.infrastructure.validators import validate_ohlcv
from modules.reporting.models import PriceData

log = get_logger("intraday_fetcher")

_LOOKBACK_DAYS = 8    # calendar days requested — guarantees >= 5 full trading days
_STALE_HOURS   = 24   # mark stale if last bar is older than this


class IntradayFetcher:

    def fetch(self, ticker: str) -> PriceData:
        ticker = ticker.upper()
        warnings: list[str] = []

        df, source = self._fetch_bars(ticker, warnings)
        is_stale   = _check_stale(df, warnings)

        return PriceData(
            ticker     = ticker,
            ohlcv      = df,
            fetched_at = datetime.now(timezone.utc),
            is_stale   = is_stale,
            warnings   = warnings,
            source     = source,
        )

    def _fetch_bars(self, ticker: str, warnings: list[str]) -> tuple[pd.DataFrame, str]:
        client = get_schwab_client()
        if client is not None:
            try:
                log.info("Downloading %s intraday (5-min) from Schwab", ticker)
                return _fetch_schwab(client, ticker), "schwab_5m"
            except Exception as exc:
                log.warning(
                    "Schwab intraday fetch failed for %s (%s) — falling back to yfinance",
                    ticker, exc,
                )
        log.info("Downloading %s intraday (5-min) from yfinance", ticker)
        return _fetch_yfinance(ticker), "yfinance_5m"


# ---------------------------------------------------------------------------
# Source-specific fetchers
# ---------------------------------------------------------------------------

def _fetch_schwab(client, ticker: str) -> pd.DataFrame:
    end   = datetime.now(timezone.utc)
    start = end - timedelta(days=_LOOKBACK_DAYS)

    resp = client.get_price_history_every_five_minutes(
        ticker,
        start_datetime           = start,
        end_datetime             = end,
        need_extended_hours_data = False,
    )

    if not resp.is_success:
        raise DataFetchError(
            f"Schwab intraday API returned HTTP {resp.status_code} for {ticker}"
        )

    data = resp.json()
    if data.get("empty", True) or not data.get("candles"):
        raise DataFetchError(f"Schwab returned empty intraday candles for {ticker}")

    df = pd.DataFrame(data["candles"])
    # Epoch-milliseconds → UTC-aware DatetimeIndex
    df.index      = pd.to_datetime(df["datetime"], unit="ms", utc=True)
    df.index.name = "date"
    df = df.drop(columns=["datetime"]).rename(columns=str.lower)
    if "adj_close" not in df.columns:
        df["adj_close"] = df["close"]

    validate_ohlcv(df, ticker)
    return df


def _fetch_yfinance(ticker: str) -> pd.DataFrame:
    try:
        raw = yf.download(
            ticker,
            period      = "5d",
            interval    = "5m",
            auto_adjust = True,
            progress    = False,
            actions     = False,
        )
    except Exception as exc:
        raise DataFetchError(
            f"yfinance intraday download failed for {ticker}: {exc}"
        ) from exc

    if raw is None or raw.empty:
        raise DataFetchError(f"yfinance returned empty intraday data for {ticker}")

    if isinstance(raw.columns, pd.MultiIndex):
        raw.columns = raw.columns.get_level_values(0)

    df = raw.copy()
    df.columns = df.columns.str.lower().str.replace(" ", "_", regex=False)
    if "adj_close" not in df.columns:
        df["adj_close"] = df["close"]

    # Normalise to UTC so _filter_to_date comparisons are consistent
    if df.index.tzinfo is None:
        df.index = df.index.tz_localize("UTC")
    else:
        df.index = df.index.tz_convert("UTC")

    validate_ohlcv(df, ticker)
    return df


# ---------------------------------------------------------------------------
# Staleness check
# ---------------------------------------------------------------------------

def _check_stale(df: pd.DataFrame, warnings: list[str]) -> bool:
    if df.empty:
        warnings.append("Intraday: no bars returned")
        return True

    last_ts = pd.Timestamp(df.index[-1])
    if last_ts.tzinfo is None:
        last_ts = last_ts.tz_localize("UTC")
    else:
        last_ts = last_ts.tz_convert("UTC")

    age_hours = (
        datetime.now(timezone.utc) - last_ts.to_pydatetime()
    ).total_seconds() / 3600

    if age_hours > _STALE_HOURS:
        warnings.append(
            f"Intraday data is {age_hours:.1f}h old "
            f"(last bar: {last_ts.strftime('%Y-%m-%d %H:%M UTC')})"
        )
        return True

    return False
