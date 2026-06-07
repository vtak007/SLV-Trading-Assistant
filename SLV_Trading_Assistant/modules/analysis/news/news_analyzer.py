# Rev 2  (added NewsAPI + Finnhub sources)
"""
News analysis orchestrator.
Fetches RSS feeds, NewsAPI, and Finnhub; classifies items; detects upcoming events.
Gracefully degrades if all feeds fail -- returns empty NewsResult rather than crashing.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from modules.collection.news_fetcher import NewsFetcher
from modules.collection.newsapi_fetcher import NewsApiFetcher
from modules.collection.finnhub_fetcher import FinnhubFetcher
from modules.collection.calendar_fetcher import CalendarFetcher
from modules.analysis.news.classifier import NewsClassifier
from modules.analysis.news.event_detector import EventDetector
from modules.infrastructure.logger import get_logger
from modules.reporting.models import NewsItem, NewsResult

log = get_logger("news.analyzer")

_MAX_ITEMS = 100  # cap per run; raised from 50 when NewsAPI + Finnhub sources were added


class NewsAnalyzer:

    def __init__(self) -> None:
        self._rss_fetcher     = NewsFetcher()
        self._newsapi_fetcher = NewsApiFetcher()
        self._finnhub_fetcher = FinnhubFetcher()
        self._calendar        = CalendarFetcher()
        self._classifier      = NewsClassifier()
        self._detector        = EventDetector()

    def analyze(
        self,
        force_refresh: bool = False,
        analysis_datetime: Optional[datetime] = None,
    ) -> NewsResult:
        """
        Fetch, classify, and assess event risk; return NewsResult.
        analysis_datetime anchors the look-ahead filter and event proximity checks.
        """
        as_of = analysis_datetime or datetime.now(timezone.utc)

        # --- Collection (graceful degradation: each source fails independently) ---
        raw_items: list[NewsItem] = []
        fetch_failed = False
        try:
            raw_items.extend(self._rss_fetcher.fetch_all_feeds(force_refresh=force_refresh))
        except Exception as exc:
            log.error("All RSS feeds failed: %s", exc)
            fetch_failed = True

        raw_items.extend(self._newsapi_fetcher.fetch_news(force_refresh=force_refresh))
        raw_items.extend(self._finnhub_fetcher.fetch_news(force_refresh=force_refresh))

        # Anti-look-ahead: filter out items published after analysis_datetime
        filtered: list[NewsItem] = [
            item for item in raw_items
            if item.published_at is None or item.published_at <= as_of
        ]

        # Sort newest-first, then cap
        _epoch = datetime.min.replace(tzinfo=timezone.utc)
        filtered.sort(key=lambda i: i.published_at or _epoch, reverse=True)
        filtered = filtered[:_MAX_ITEMS]

        # --- Classify ---
        classified = self._classifier.classify_batch(filtered)

        # --- Calendar events (always available, no network needed) ---
        upcoming = self._calendar.get_upcoming_events(as_of=as_of)

        # --- Event risk ---
        event_risk_level, _ = self._detector.detect(upcoming, as_of=as_of)

        result = NewsResult(
            items=classified,
            upcoming_events=upcoming,
            event_risk_level=event_risk_level,
            analysis_datetime=as_of,
        )

        log.info(
            "News analysis complete: %d items, %d upcoming events, risk_level=%s%s",
            len(classified),
            len(upcoming),
            event_risk_level,
            " [feeds unavailable]" if fetch_failed else "",
        )
        return result
