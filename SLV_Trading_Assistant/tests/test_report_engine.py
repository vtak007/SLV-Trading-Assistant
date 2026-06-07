# Rev 1
"""
Integration tests for the report engine — text and HTML output.
All tests are offline; they use synthetic data and do NOT touch the database.
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

import pandas as pd
import pytest

from config.trading_styles import TradingStyle
from modules.reporting.models import (
    MacroDriverScore, MacroResult, NewsItem, NewsResult, PriceData,
    ReportBundle, RiskResult, SignalResult, TechnicalResult,
)
from modules.reporting.formatters import text_formatter, html_formatter
from modules.reporting.sections import (
    s01_executive_summary, s07_signal_decision, s08_trade_plan,
    s09_risk_warnings, s11_final_summary,
)


# ---------------------------------------------------------------------------
# Shared bundle fixture
# ---------------------------------------------------------------------------

@pytest.fixture
def bundle() -> ReportBundle:
    now = datetime(2026, 5, 27, 12, 0, tzinfo=timezone.utc)
    df  = pd.DataFrame(
        {
            "open":  [29.5] * 260,
            "high":  [30.5] * 260,
            "low":   [29.0] * 260,
            "close": [30.0] * 260,
            "volume": [5_000_000] * 260,
            "adj_close": [30.0] * 260,
        },
        index=pd.date_range("2025-06-01", periods=260, freq="B"),
    )
    price_data = PriceData(ticker="SLV", ohlcv=df,
                           fetched_at=now, is_stale=False)

    tech = TechnicalResult(
        ticker="SLV",
        analysis_date=now,
        indicators={
            "close": 30.0, "atr_14": 0.50, "rsi_14": 55.0,
            "macd_hist": 0.05, "bb_pct": 0.5,
            "sma_20": 29.5, "sma_50": 29.0, "sma_200": 27.0,
            "ema_9": 29.8, "ema_21": 29.3,
            "macd": 0.10, "macd_signal": 0.05,
            "bb_upper": 31.5, "bb_lower": 28.5,
            "relative_volume": 1.2, "obv_trend": "rising",
            "patterns": ["bullish_crossover"],
            "support_levels": [28.5, 27.5],
            "resistance_levels": [31.5, 32.5],
        },
        vol_regime="normal",
        trend_direction="bullish",
        support_levels=[28.5, 27.5],
        resistance_levels=[31.5, 32.5],
    )

    macro = MacroResult(
        drivers=[
            MacroDriverScore("Real Yield", "bullish", -0.5, "Real yield negative", 0.15),
            MacroDriverScore("US Dollar", "bearish", 105.0, "DXY elevated", 0.15),
            MacroDriverScore("CPI", "bullish", 3.2, "CPI cooling", 0.10),
            MacroDriverScore("Fed Policy", "bullish", 5.25, "Fed pivoting", 0.15),
            MacroDriverScore("G/S Ratio", "bullish", 8.2, "Ratio high", 0.10),
            MacroDriverScore("Sentiment", "neutral", 18.0, "VIX normal", 0.10),
            MacroDriverScore("Nominal Yield", "bearish", 4.5, "Yield high", 0.10),
            MacroDriverScore("PPI", "neutral", 1.8, "PPI moderate", 0.10),
        ],
        composite_score=0.35,
        analysis_date=now,
    )

    news = NewsResult(
        items=[
            NewsItem(
                headline="Silver demand rises on industrial growth",
                source="MarketWatch",
                url="",
                published_at=now,
                fetched_at=now,
                classification="bullish",
                confidence=0.75,
            ),
            NewsItem(
                headline="Fed speakers hawkish tone",
                source="Reuters",
                url="",
                published_at=now,
                fetched_at=now,
                classification="bearish",
                confidence=0.65,
            ),
        ],
        upcoming_events=[{
            "event_name": "NFP",
            "scheduled_at": datetime(2026, 6, 5, 12, 30, tzinfo=timezone.utc),
            "impact_level": "high",
        }],
        event_risk_level="medium",
        analysis_datetime=now,
    )

    signal = SignalResult(
        action="BUY",
        confidence=62.0,
        risk_score=38.0,
        regime_label="trending_bull",
        entry_zone=(29.85, 30.05),
        stop_loss=29.0,
        targets=[30.75, 31.50, 32.50],
        position_size_pct=0.030,
        bullish_evidence=["Price above 200-day SMA", "MACD histogram positive"],
        bearish_evidence=["US Dollar elevated"],
        conflicts=[],
        explanation="Signal: BUY  |  Composite: +0.38  |  Confidence: 62%",
        no_trade_reason="",
        generated_at=now,
        trading_style="swing",
    )

    risk = RiskResult(
        atr_stop=29.0,
        position_size_shares=100,
        gap_risk_flag=False,
        major_event_flag=False,
        atr_value=0.50,
        account_risk_pct=0.01,
    )

    return ReportBundle(
        price_data=price_data,
        tech_result=tech,
        macro_result=macro,
        news_result=news,
        signal_result=signal,
        risk_result=risk,
        trading_style="swing",
        generated_at=now,
    )


# ---------------------------------------------------------------------------
# Text formatter tests
# ---------------------------------------------------------------------------

class TestTextFormatter:

    def test_generates_non_empty_output(self, bundle):
        text = text_formatter.generate(bundle)
        assert len(text) > 500

    def test_all_11_sections_present(self, bundle):
        text = text_formatter.generate(bundle)
        for i in range(1, 12):
            assert f"SECTION {i}" in text, f"Section {i} missing from text output"

    def test_action_appears_in_text(self, bundle):
        text = text_formatter.generate(bundle)
        assert "BUY" in text

    def test_disclaimer_present(self, bundle):
        text = text_formatter.generate(bundle)
        assert "research and decision support" in text.lower()

    def test_section_render_error_does_not_abort(self, bundle):
        # Corrupt bundle to cause a section error; rest of report should still render
        bundle.signal_result = None  # type: ignore[assignment]
        text = text_formatter.generate(bundle)
        assert "Section render error" in text or len(text) > 0


# ---------------------------------------------------------------------------
# HTML formatter tests
# ---------------------------------------------------------------------------

class TestHtmlFormatter:

    def test_generates_valid_html_skeleton(self, bundle):
        html = html_formatter.generate(bundle)
        assert "<!DOCTYPE html>" in html
        assert "<html" in html
        assert "</html>" in html

    def test_all_section_ids_present(self, bundle):
        html = html_formatter.generate(bundle)
        for i in range(1, 12):
            assert f'id="s{i:02d}"' in html, f"Section id s{i:02d} missing from HTML"

    def test_action_label_in_html(self, bundle):
        html = html_formatter.generate(bundle)
        assert "BUY" in html

    def test_disclaimer_in_html(self, bundle):
        html = html_formatter.generate(bundle)
        assert "research and decision support" in html.lower()

    def test_no_external_urls(self, bundle):
        html = html_formatter.generate(bundle)
        # No actual CDN resource loads — plotly.js is embedded inline.
        # Check for <script src> / <link href> CDN tags, not string literals
        # inside embedded JS which may reference CDN defaults as config strings.
        import re
        cdn_tags = re.findall(
            r'<(?:script|link)[^>]+(?:src|href)\s*=\s*["\']https?://cdn', html
        )
        assert cdn_tags == [], f"Found CDN resource tags: {cdn_tags}"


# ---------------------------------------------------------------------------
# Individual section tests
# ---------------------------------------------------------------------------

class TestSections:

    def test_s01_contains_action(self, bundle):
        assert "BUY" in s01_executive_summary.render_text(bundle)

    def test_s01_contains_confidence(self, bundle):
        assert "62" in s01_executive_summary.render_text(bundle)

    def test_s07_contains_bullish_evidence(self, bundle):
        text = s07_signal_decision.render_text(bundle)
        assert "MACD histogram positive" in text

    def test_s08_shows_entry_and_stop(self, bundle):
        text = s08_trade_plan.render_text(bundle)
        assert "29.85" in text   # entry low
        assert "29.00" in text   # stop loss

    def test_s08_hold_shows_no_entry(self, bundle):
        bundle.signal_result.action = "HOLD"
        text = s08_trade_plan.render_text(bundle)
        assert "No entry recommended" in text

    def test_s09_no_warnings_when_clean(self, bundle):
        text = s09_risk_warnings.render_text(bundle)
        assert "No active risk warnings" in text

    def test_s09_shows_gap_risk(self, bundle):
        bundle.risk_result.gap_risk_flag = True
        text = s09_risk_warnings.render_text(bundle)
        assert "GAP RISK" in text

    def test_s11_contains_disclaimer(self, bundle):
        text = s11_final_summary.render_text(bundle)
        assert "DISCLAIMER" in text

    def test_s11_html_contains_disclaimer_box(self, bundle):
        html = s11_final_summary.render_html(bundle)
        assert "disclaimer-box" in html

    def test_no_trade_bundle_propagates(self, bundle):
        bundle.signal_result.action = "NO_TRADE"
        bundle.signal_result.no_trade_reason = "FOMC in no-trade window"
        text = s01_executive_summary.render_text(bundle)
        assert "NO-TRADE" in text
