# Rev 1
"""
NewsAPI.org fetcher for SLV Trading Assistant.
Queries the /v2/everything endpoint for silver/SLV/gold news.
Skips silently when NEWSAPI_API_KEY is not configured.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import requests

from config.settings import NEWSAPI_API_KEY, NEWS_CACHE_TTL
from modules.collection.base_fetcher import BaseFetcher
from modules.infrastructure.exceptions import DataFetchError
from modules.infrastructure.logger import get_logger
from modules.reporting.models import NewsItem

log = get_logger("newsapi_fetcher")

_ENDPOINT = "https://newsapi.org/v2/everything"
_QUERY     = "silver OR SLV OR gold OR precious metals"
_PAGE_SIZE = 30
_CACHE_KEY = "newsapi_news"


class NewsApiFetcher(BaseFetcher):

    def __init__(self) -> None:
        super().__init__(cache_ttl_seconds=NEWS_CACHE_TTL)

    @property
    def is_configured(self) -> bool:
        return bool(NEWSAPI_API_KEY)

    def fetch_news(self, force_refresh: bool = False) -> list[NewsItem]:
        """Return NewsItems from NewsAPI; empty list if key not set."""
        if not self.is_configured:
            log.debug("NEWSAPI_API_KEY not set — skipping NewsAPI source")
            return []
        try:
            raw: list[dict] = self.fetch(_CACHE_KEY, force_refresh=force_refresh)
            return self._parse(raw)
        except Exception as exc:
            log.warning("NewsAPI fetch failed: %s", exc)
            return []

    # ------------------------------------------------------------------
    # BaseFetcher contract
    # ------------------------------------------------------------------

    def _fetch_fresh(self, key: str) -> Any:
        params = {
            "q":        _QUERY,
            "sortBy":   "publishedAt",
            "pageSize": _PAGE_SIZE,
            "language": "en",
            "apiKey":   NEWSAPI_API_KEY,
        }
        resp = requests.get(_ENDPOINT, params=params, timeout=15)
        if resp.status_code == 401:
            raise DataFetchError("NewsAPI: invalid API key (401)")
        if resp.status_code == 426:
            raise DataFetchError("NewsAPI: plan upgrade required (426) — free tier may be restricted")
        if not resp.ok:
            raise DataFetchError(f"NewsAPI HTTP {resp.status_code}: {resp.text[:200]}")

        data = resp.json()
        if data.get("status") != "ok":
            raise DataFetchError(f"NewsAPI error: {data.get('message', 'unknown')}")

        return data.get("articles", [])

    # ------------------------------------------------------------------
    # Parsing
    # ------------------------------------------------------------------

    @staticmethod
    def _parse(articles: list[dict]) -> list[NewsItem]:
        fetched_at = datetime.now(timezone.utc)
        items: list[NewsItem] = []

        for a in articles:
            headline = (a.get("title") or "").strip()
            if not headline or headline == "[Removed]":
                continue

            published_at: datetime | None = None
            raw_ts = a.get("publishedAt")
            if raw_ts:
                try:
                    published_at = datetime.fromisoformat(raw_ts.replace("Z", "+00:00"))
                except ValueError:
                    pass

            source_name = (a.get("source") or {}).get("name") or "newsapi"

            items.append(NewsItem(
                headline=headline,
                source=f"newsapi:{source_name}",
                url=a.get("url") or "",
                published_at=published_at,
                fetched_at=fetched_at,
            ))

        return items
