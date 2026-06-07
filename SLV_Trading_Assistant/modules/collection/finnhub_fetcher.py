# Rev 1
"""
Finnhub news fetcher for SLV Trading Assistant.
Fetches company news for SLV and GLD over the last 7 days.
Skips silently when FINNHUB_API_KEY is not configured.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

import requests

from config.settings import FINNHUB_API_KEY, NEWS_CACHE_TTL
from modules.collection.base_fetcher import BaseFetcher
from modules.infrastructure.exceptions import DataFetchError
from modules.infrastructure.logger import get_logger
from modules.reporting.models import NewsItem

log = get_logger("finnhub_fetcher")

_ENDPOINT   = "https://finnhub.io/api/v1/company-news"
_SYMBOLS    = ["SLV", "GLD"]
_LOOKBACK_DAYS = 7


class FinnhubFetcher(BaseFetcher):

    def __init__(self) -> None:
        super().__init__(cache_ttl_seconds=NEWS_CACHE_TTL)

    @property
    def is_configured(self) -> bool:
        return bool(FINNHUB_API_KEY)

    def fetch_news(self, force_refresh: bool = False) -> list[NewsItem]:
        """Return NewsItems from Finnhub for all configured symbols; empty list if key not set."""
        if not self.is_configured:
            log.debug("FINNHUB_API_KEY not set — skipping Finnhub source")
            return []

        items: list[NewsItem] = []
        for symbol in _SYMBOLS:
            try:
                raw: list[dict] = self.fetch(f"finnhub_{symbol.lower()}", force_refresh=force_refresh)
                items.extend(self._parse(raw, symbol))
            except Exception as exc:
                log.warning("Finnhub fetch failed for %s: %s", symbol, exc)

        return items

    # ------------------------------------------------------------------
    # BaseFetcher contract
    # ------------------------------------------------------------------

    def _fetch_fresh(self, key: str) -> Any:
        # key is "finnhub_slv" or "finnhub_gld" — extract symbol
        symbol = key.split("_", 1)[1].upper()

        now  = datetime.now(timezone.utc)
        to   = now.strftime("%Y-%m-%d")
        frm  = (now - timedelta(days=_LOOKBACK_DAYS)).strftime("%Y-%m-%d")

        params = {
            "symbol": symbol,
            "from":   frm,
            "to":     to,
            "token":  FINNHUB_API_KEY,
        }
        resp = requests.get(_ENDPOINT, params=params, timeout=15)
        if resp.status_code == 401:
            raise DataFetchError("Finnhub: invalid API key (401)")
        if resp.status_code == 429:
            raise DataFetchError("Finnhub: rate limit exceeded (429)")
        if not resp.ok:
            raise DataFetchError(f"Finnhub HTTP {resp.status_code}: {resp.text[:200]}")

        data = resp.json()
        if not isinstance(data, list):
            raise DataFetchError(f"Finnhub unexpected response type: {type(data)}")

        return data

    # ------------------------------------------------------------------
    # Parsing
    # ------------------------------------------------------------------

    @staticmethod
    def _parse(articles: list[dict], symbol: str) -> list[NewsItem]:
        fetched_at = datetime.now(timezone.utc)
        items: list[NewsItem] = []

        for a in articles:
            headline = (a.get("headline") or "").strip()
            if not headline:
                continue

            published_at: datetime | None = None
            ts = a.get("datetime")
            if ts:
                try:
                    published_at = datetime.fromtimestamp(int(ts), tz=timezone.utc)
                except (ValueError, OSError):
                    pass

            source_name = (a.get("source") or "finnhub").strip()

            items.append(NewsItem(
                headline=headline,
                source=f"finnhub:{source_name}",
                url=a.get("url") or "",
                published_at=published_at,
                fetched_at=fetched_at,
            ))

        return items
