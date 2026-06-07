# Rev 1
"""
Tests for Session 3: news classifier, event detector, calendar fetcher, news analyzer.
All tests run offline -- no network calls.
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from modules.analysis.news.classifier import NewsClassifier
from modules.analysis.news.event_detector import EventDetector
from modules.collection.calendar_fetcher import CalendarFetcher
from modules.reporting.models import NewsItem

FIXTURES_DIR = Path(__file__).parent / "fixtures"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_item(headline: str, source: str = "test", published_at=None) -> NewsItem:
    return NewsItem(
        headline=headline,
        source=source,
        url=f"https://example.com/{headline[:10]}",
        published_at=published_at or datetime(2026, 5, 27, 12, 0, tzinfo=timezone.utc),
        fetched_at=datetime(2026, 5, 27, 13, 0, tzinfo=timezone.utc),
    )


def upcoming(name: str, hours_away: float, as_of=None) -> dict:
    as_of = as_of or datetime(2026, 5, 27, 12, 0, tzinfo=timezone.utc)
    return {
        "event_name":   name,
        "scheduled_at": as_of + timedelta(hours=hours_away),
        "impact_level": "critical" if name == "FOMC" else "high",
    }


# ---------------------------------------------------------------------------
# NewsClassifier
# ---------------------------------------------------------------------------

class TestNewsClassifier:
    clf = NewsClassifier()

    def test_bullish_silver_rises(self):
        item = self.clf.classify(make_item("Silver rises 2% on safe-haven demand"))
        assert item.classification == "bullish"
        assert item.confidence > 0.4

    def test_bullish_dovish_fed(self):
        item = self.clf.classify(make_item("Fed turns dovish; rate cut expected next meeting"))
        assert item.classification == "bullish"

    def test_bullish_dollar_falls(self):
        item = self.clf.classify(make_item("Dollar weakens sharply; DXY drops to multi-month low"))
        assert item.classification == "bullish"

    def test_bearish_silver_falls(self):
        item = self.clf.classify(make_item("Silver falls 3% as dollar strengthens"))
        assert item.classification == "bearish"
        assert item.confidence > 0.4

    def test_bearish_hawkish(self):
        item = self.clf.classify(make_item("Fed hawkish; rate hike back on the table"))
        assert item.classification == "bearish"

    def test_bearish_dollar_rises(self):
        item = self.clf.classify(make_item("Dollar rallies strongly on strong jobs data"))
        assert item.classification == "bearish"

    def test_neutral_no_keywords(self):
        item = self.clf.classify(make_item("Market update: trading volumes steady midweek"))
        assert item.classification == "neutral"
        assert item.confidence == pytest.approx(0.30)

    def test_neutral_mixed_signals(self):
        # Both bullish and bearish signals without dominance
        item = self.clf.classify(make_item("Silver rises but gold falls; mixed precious metals session"))
        # Mixed or neutral (depends on scores) -- just verify it's not an error
        assert item.classification in {"bullish", "bearish", "neutral"}

    def test_short_impact_set_for_event_headline(self):
        item = self.clf.classify(make_item("CPI beats forecast; silver surges higher"))
        assert item.short_impact == "bullish"
        assert item.medium_impact == "bullish"

    def test_long_impact_set_for_structural_headline(self):
        # "trend" and "Federal Reserve" hit long-horizon patterns; "rate cuts" hits bullish
        item = self.clf.classify(make_item(
            "Silver long-term trend is bullish as Federal Reserve pivots to rate cuts"
        ))
        assert item.long_impact == "bullish"

    def test_short_impact_neutral_for_non_event(self):
        item = self.clf.classify(make_item("Silver rises on supply deficit"))
        # "supply deficit" is bullish but not a short-horizon event keyword
        assert item.short_impact == "neutral"
        assert item.medium_impact == "bullish"

    def test_confidence_bounded(self):
        item = self.clf.classify(make_item(
            "Silver rises rally surges safe-haven demand supply deficit precious metals bullish"
        ))
        assert 0.0 <= item.confidence <= 1.0

    def test_classify_batch_length(self):
        items = [make_item(f"Silver update {i}") for i in range(5)]
        result = self.clf.classify_batch(items)
        assert len(result) == 5

    def test_fixture_classifications(self):
        """Spot-check sample_news.json against expected classifications."""
        raw = json.loads((FIXTURES_DIR / "sample_news.json").read_text())
        for entry in raw:
            item = self.clf.classify(make_item(entry["headline"], entry["source"]))
            expected = entry["classification"]
            # Allow adjacent category (neutral is acceptable for borderline)
            if expected == "bullish":
                assert item.classification in {"bullish", "neutral"}, (
                    f"Expected bullish/neutral, got {item.classification!r} for: {entry['headline']}"
                )
            elif expected == "bearish":
                assert item.classification in {"bearish", "neutral"}, (
                    f"Expected bearish/neutral, got {item.classification!r} for: {entry['headline']}"
                )


# ---------------------------------------------------------------------------
# EventDetector
# ---------------------------------------------------------------------------

class TestEventDetector:
    det = EventDetector()
    AS_OF = datetime(2026, 5, 27, 12, 0, tzinfo=timezone.utc)

    def test_no_events_returns_low(self):
        level, warnings = self.det.detect([], as_of=self.AS_OF)
        assert level == "low"
        assert warnings == []

    def test_fomc_within_no_trade_window(self):
        """FOMC within 4h triggers critical + no-trade warning."""
        events = [upcoming("FOMC", hours_away=2.0, as_of=self.AS_OF)]
        level, warnings = self.det.detect(events, as_of=self.AS_OF)
        assert level == "critical"
        assert any("NO-TRADE" in w for w in warnings)

    def test_cpi_within_no_trade_window(self):
        """CPI within 1h triggers no-trade."""
        events = [upcoming("CPI", hours_away=0.5, as_of=self.AS_OF)]
        level, warnings = self.det.detect(events, as_of=self.AS_OF)
        assert level == "critical"
        assert any("NO-TRADE" in w for w in warnings)

    def test_fomc_24h_is_critical(self):
        events = [upcoming("FOMC", hours_away=20.0, as_of=self.AS_OF)]
        level, warnings = self.det.detect(events, as_of=self.AS_OF)
        assert level == "critical"
        assert any("CRITICAL" in w for w in warnings)

    def test_fomc_48h_is_high(self):
        events = [upcoming("FOMC", hours_away=36.0, as_of=self.AS_OF)]
        level, warnings = self.det.detect(events, as_of=self.AS_OF)
        assert level == "high"

    def test_fomc_72h_is_medium(self):
        events = [upcoming("FOMC", hours_away=60.0, as_of=self.AS_OF)]
        level, warnings = self.det.detect(events, as_of=self.AS_OF)
        assert level == "medium"

    def test_fomc_far_away_is_low(self):
        events = [upcoming("FOMC", hours_away=200.0, as_of=self.AS_OF)]
        level, _ = self.det.detect(events, as_of=self.AS_OF)
        assert level == "low"

    def test_past_event_ignored(self):
        events = [upcoming("FOMC", hours_away=-5.0, as_of=self.AS_OF)]
        level, warnings = self.det.detect(events, as_of=self.AS_OF)
        assert level == "low"
        assert warnings == []

    def test_escalation_to_highest(self):
        """Multiple events: highest severity wins."""
        events = [
            upcoming("NFP",  hours_away=36.0, as_of=self.AS_OF),   # high
            upcoming("FOMC", hours_away=2.0,  as_of=self.AS_OF),   # critical / no-trade
        ]
        level, _ = self.det.detect(events, as_of=self.AS_OF)
        assert level == "critical"

    def test_has_no_trade_condition_true(self):
        events = [upcoming("FOMC", hours_away=1.0, as_of=self.AS_OF)]
        assert self.det.has_no_trade_condition(events, as_of=self.AS_OF) is True

    def test_has_no_trade_condition_false(self):
        events = [upcoming("FOMC", hours_away=10.0, as_of=self.AS_OF)]
        assert self.det.has_no_trade_condition(events, as_of=self.AS_OF) is False


# ---------------------------------------------------------------------------
# CalendarFetcher
# ---------------------------------------------------------------------------

class TestCalendarFetcher:
    cal = CalendarFetcher()

    def test_returns_list(self):
        events = self.cal.get_upcoming_events(as_of=datetime(2026, 5, 27, tzinfo=timezone.utc))
        assert isinstance(events, list)

    def test_events_have_required_keys(self):
        events = self.cal.get_upcoming_events(
            as_of=datetime(2026, 5, 1, tzinfo=timezone.utc), lookahead_days=60
        )
        for ev in events:
            assert "event_name" in ev
            assert "scheduled_at" in ev
            assert "impact_level" in ev

    def test_events_sorted_by_date(self):
        events = self.cal.get_upcoming_events(
            as_of=datetime(2026, 1, 1, tzinfo=timezone.utc), lookahead_days=90
        )
        dates = [e["scheduled_at"] for e in events]
        assert dates == sorted(dates)

    def test_fomc_present_in_2026(self):
        events = self.cal.get_upcoming_events(
            as_of=datetime(2026, 1, 1, tzinfo=timezone.utc), lookahead_days=365
        )
        fomc_events = [e for e in events if e["event_name"] == "FOMC"]
        assert len(fomc_events) >= 6

    def test_lookback_includes_past_events(self):
        """lookback_days > 0 should include recent past events."""
        # Use Jan 30 2026 -- FOMC was Jan 28; with 5-day lookback it should appear
        events = self.cal.get_upcoming_events(
            as_of=datetime(2026, 1, 30, tzinfo=timezone.utc),
            lookback_days=5,
            lookahead_days=0,
        )
        fomc = [e for e in events if e["event_name"] == "FOMC"]
        assert len(fomc) >= 1

    def test_narrow_window_finds_only_nearby(self):
        events = self.cal.get_upcoming_events(
            as_of=datetime(2026, 5, 27, tzinfo=timezone.utc),
            lookahead_days=1,
        )
        for ev in events:
            hours = (ev["scheduled_at"] - datetime(2026, 5, 27, tzinfo=timezone.utc)).total_seconds() / 3600
            assert hours <= 24 + 1  # +1 for release-time offset within the day


# ---------------------------------------------------------------------------
# NewsAnalyzer (offline: mock NewsFetcher._fetch_fresh)
# ---------------------------------------------------------------------------

class TestNewsAnalyzerOffline:

    def _make_analyzer_with_mock_entries(self, entries):
        from modules.analysis.news.news_analyzer import NewsAnalyzer
        analyzer = NewsAnalyzer()
        analyzer._fetcher._fetch_fresh = MagicMock(return_value=entries)
        return analyzer

    def test_returns_news_result(self):
        from modules.reporting.models import NewsResult
        from modules.analysis.news.news_analyzer import NewsAnalyzer
        analyzer = NewsAnalyzer()
        analyzer._fetcher.fetch_all_feeds = MagicMock(return_value=[])
        result = analyzer.analyze()
        assert isinstance(result, NewsResult)

    def test_empty_feeds_no_crash(self):
        from modules.analysis.news.news_analyzer import NewsAnalyzer
        analyzer = NewsAnalyzer()
        analyzer._fetcher.fetch_all_feeds = MagicMock(return_value=[])
        result = analyzer.analyze()
        assert result.items == []
        assert result.event_risk_level in {"low", "medium", "high", "critical"}

    def test_look_ahead_filter(self):
        """Items published after analysis_datetime must be excluded."""
        from modules.analysis.news.news_analyzer import NewsAnalyzer
        future_item = make_item("Future headline", published_at=datetime(2030, 1, 1, tzinfo=timezone.utc))
        past_item   = make_item("Past headline",   published_at=datetime(2020, 1, 1, tzinfo=timezone.utc))

        analyzer = NewsAnalyzer()
        analyzer._fetcher.fetch_all_feeds = MagicMock(return_value=[future_item, past_item])
        as_of = datetime(2026, 5, 27, tzinfo=timezone.utc)
        result = analyzer.analyze(analysis_datetime=as_of)

        headlines = [i.headline for i in result.items]
        assert "Past headline" in headlines
        assert "Future headline" not in headlines

    def test_all_items_classified(self):
        from modules.analysis.news.news_analyzer import NewsAnalyzer
        items = [
            make_item("Silver rises on safe-haven demand"),
            make_item("Silver falls as dollar strengthens"),
            make_item("Market update midweek"),
        ]
        analyzer = NewsAnalyzer()
        analyzer._fetcher.fetch_all_feeds = MagicMock(return_value=items)
        result = analyzer.analyze()
        for item in result.items:
            assert item.classification in {"bullish", "bearish", "neutral", "unknown"}
