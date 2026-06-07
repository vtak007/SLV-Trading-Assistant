# Rev 2  (chain bozo_exception so base_fetcher can detect permanent errors)
"""
RSS news fetcher for SLV Trading Assistant.
Subclasses BaseFetcher for cache/retry; TTL = NEWS_CACHE_TTL (1 hour).
Per-feed exception handling prevents one broken feed from killing the run.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import feedparser

from config.data_sources import NEWS_RSS_FEEDS
from config.settings import NEWS_CACHE_TTL
from modules.collection.base_fetcher import BaseFetcher
from modules.infrastructure.exceptions import DataFetchError
from modules.infrastructure.logger import get_logger
from modules.reporting.models import NewsItem

log = get_logger("news_fetcher")


class NewsFetcher(BaseFetcher):

    def __init__(self) -> None:
        super().__init__(cache_ttl_seconds=NEWS_CACHE_TTL)

    def fetch_all_feeds(self, force_refresh: bool = False) -> list[NewsItem]:
        """Fetch all configured RSS feeds; return flat list of NewsItems."""
        items: list[NewsItem] = []
        for feed_name in NEWS_RSS_FEEDS:
            try:
                raw = self.fetch(feed_name, force_refresh=force_refresh)
                items.extend(self._parse_entries(raw, feed_name))
                log.info("Feed '%s': %d items", feed_name, len(raw))
            except Exception as exc:
                log.warning("Feed '%s' unavailable: %s", feed_name, exc)
        return items

    # ------------------------------------------------------------------
    # BaseFetcher contract
    # ------------------------------------------------------------------

    def _fetch_fresh(self, key: str) -> Any:
        """Fetch one RSS feed by name key; returns list of raw entry dicts."""
        url = NEWS_RSS_FEEDS.get(key)
        if not url:
            raise DataFetchError(f"Unknown feed key: '{key}'")

        parsed = feedparser.parse(url)
        # bozo=True means malformed XML, but entries may still be present
        if parsed.bozo and not parsed.entries:
            raise DataFetchError(
                f"feedparser failed for '{key}': {parsed.bozo_exception}"
            ) from parsed.bozo_exception

        return parsed.entries

    # ------------------------------------------------------------------
    # Parsing helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_entries(entries: list, source: str) -> list[NewsItem]:
        """Convert raw feedparser entries to NewsItem objects."""
        fetched_at = datetime.now(timezone.utc)
        items: list[NewsItem] = []

        for e in entries:
            headline = (e.get("title") or "").strip()
            if not headline:
                continue

            url = e.get("link", "")

            # feedparser returns time.struct_time; convert to datetime
            pub_struct = e.get("published_parsed") or e.get("updated_parsed")
            published_at: datetime | None = None
            if pub_struct:
                try:
                    published_at = datetime(*pub_struct[:6], tzinfo=timezone.utc)
                except Exception:
                    pass

            items.append(NewsItem(
                headline=headline,
                source=source,
                url=url,
                published_at=published_at,
                fetched_at=fetched_at,
            ))

        return items
