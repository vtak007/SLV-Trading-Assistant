# SLV Modular Trading Assistant — Architecture & Implementation Plan

## Context

The user wants to build a Python-based research assistant and signal generator for trading the SLV silver ETF. It is a **decision support tool only** — no live trading. The specification is fully captured in `SLV Modular System Architect & Sub-Agent.md`. The project directory currently contains only that document; all code must be built from scratch.

The system must support four trading styles (day / swing / position / long-term), analyze a wide set of macro drivers and news, and produce an explainable 11-section report with a trade plan, confidence score, and risk warnings. All data must come from free/public sources.

---

## System Architecture

### Layers (strict dependency order — lower layers never import upper)

```
Layer 0 — Infrastructure     config/, modules/infrastructure/
Layer 1 — Data Collection    modules/collection/
Layer 2 — Analysis           modules/analysis/ (technical, macro, news)
Layer 3 — Engines            modules/engines/ (signal, risk)
Layer 4 — Reporting          modules/reporting/
Layer 5 — Orchestration      main.py, runner.py
```

### Folder Structure

```
SLV_Trading_Assistant/
├── main.py                          # CLI entry point (Rev 1)
├── requirements.txt
├── .env.example                     # FRED_API_KEY placeholder
├── config/
│   ├── settings.py                  # paths, constants, env loading
│   ├── trading_styles.py            # day/swing/position/long-term profiles + weights
│   └── data_sources.py              # tickers, FRED series IDs, RSS URLs
├── data/                            # gitignored, runtime-created
│   ├── slv_assistant.db             # SQLite database
│   ├── cache/                       # JSON/pickle per-ticker cache
│   └── reports/                     # generated output files
├── modules/
│   ├── infrastructure/
│   │   ├── database.py              # schema creation, connection management
│   │   ├── logger.py                # rotating file + console logging
│   │   ├── exceptions.py            # DataFetchError, StaleDataError, ValidationError
│   │   └── validators.py            # OHLCV shape/type/range checks
│   ├── collection/
│   │   ├── base_fetcher.py          # abstract base: cache logic, freshness check
│   │   ├── price_fetcher.py         # yfinance: SLV, GLD, ^VIX, TIP, UUP, GDX
│   │   ├── macro_fetcher.py         # FRED API: yields, CPI, PPI, payrolls
│   │   ├── news_fetcher.py          # feedparser: Kitco, Reuters, MarketWatch, Fed RSS
│   │   ├── calendar_fetcher.py      # upcoming economic events
│   │   └── data_store.py            # unified SQLite read/write API
│   ├── analysis/
│   │   ├── technical/
│   │   │   ├── indicators.py        # MA, EMA, RSI, MACD, BB, ATR via pandas-ta
│   │   │   ├── volume_analysis.py   # VROC, relative volume, OBV
│   │   │   ├── pattern_detector.py  # breakouts, pullbacks
│   │   │   ├── support_resistance.py# pivot-based S/R levels
│   │   │   ├── vol_regime.py        # ATR percentile regime (low/normal/high/extreme)
│   │   │   └── technical_analyzer.py# orchestrator → returns TechnicalResult
│   │   ├── macro/
│   │   │   ├── yield_analyzer.py    # real yield, nominal yield pressure
│   │   │   ├── dollar_analyzer.py   # UUP + DTWEX
│   │   │   ├── inflation_analyzer.py# CPI/PPI surprise scoring
│   │   │   ├── fed_policy_analyzer.py# Fed stance classification
│   │   │   ├── gs_ratio_analyzer.py # gold-silver ratio
│   │   │   ├── sentiment_analyzer.py# VIX risk-on/off
│   │   │   └── macro_analyzer.py    # orchestrator → returns MacroResult
│   │   └── news/
│   │       ├── classifier.py        # keyword/rule-based impact classification
│   │       ├── event_detector.py    # FOMC/CPI/NFP detection + pre-event warnings
│   │       └── news_analyzer.py     # orchestrator → returns NewsResult
│   ├── engines/
│   │   ├── score_aggregator.py      # weighted domain scores per trading style
│   │   ├── confidence_calc.py       # confidence reduction rules
│   │   ├── conflict_resolver.py     # bull/bear conflict detection
│   │   ├── regime_classifier.py     # market regime labeling
│   │   ├── signal_engine.py         # master aggregation → SignalResult
│   │   └── risk_engine.py           # ATR stops, position sizing, flags → RiskResult
│   └── reporting/
│       ├── models.py                # all output dataclasses
│       ├── sections/
│       │   ├── s01_executive_summary.py
│       │   ├── s02_trading_style.py
│       │   ├── s03_technical_setup.py
│       │   ├── s04_macro_scorecard.py
│       │   ├── s05_news_events.py
│       │   ├── s06_historical_context.py
│       │   ├── s07_signal_decision.py
│       │   ├── s08_trade_plan.py
│       │   ├── s09_risk_warnings.py
│       │   ├── s10_data_quality.py
│       │   └── s11_final_summary.py
│       ├── formatters/
│       │   ├── text_formatter.py
│       │   ├── html_formatter.py
│       │   └── chart_generator.py   # matplotlib static + plotly interactive
│       └── report_engine.py         # orchestrator for 11-section report
└── tests/
    ├── fixtures/                    # static CSV/JSON snapshots for offline testing
    ├── test_price_fetcher.py
    ├── test_indicators.py
    ├── test_macro_analyzer.py
    ├── test_news_classifier.py
    ├── test_signal_engine.py
    ├── test_risk_engine.py
    └── test_report_engine.py
```

### SQLite Schema

```
price_data      (ticker, date, open, high, low, close, volume, adj_close, fetched_at, is_stale)
macro_data      (series_id, date, value, fetched_at, source, is_stale)
news_items      (id, headline, source, url, published_at, fetched_at, classification,
                 short_impact, medium_impact, long_impact, confidence)
economic_events (id, event_name, scheduled_at, actual_value, forecast_value, prior_value, impact_level)
signals         (id, generated_at, trading_style, action, confidence, risk_score, raw_json)
data_quality_log(id, logged_at, module, metric_name, status, message)
```

### Key Data Contracts (dataclasses in `modules/reporting/models.py`)

- `PriceData` — ticker, OHLCV DataFrame, fetched_at, is_stale
- `TechnicalResult` — indicators dict, support/resistance lists, vol_regime, trend_direction, warnings
- `MacroDriverScore` — driver_name, score (bullish/bearish/neutral/mixed/unknown), value, evidence, weight
- `MacroResult` — list[MacroDriverScore], composite_score (-1.0 to +1.0), missing_data_warnings
- `NewsResult` — list[NewsItem], upcoming_events, event_risk_level
- `SignalResult` — action, confidence 0–100, risk_score 0–100, regime_label, entry_zone, stop_loss, targets, position_size_pct, bull/bear/conflict evidence, explanation
- `RiskResult` — atr_stop, position_size_shares, gap_risk_flag, major_event_flag, no_trade_conditions

### Key Technology Choices

| Need | Tool | Reason |
|---|---|---|
| Price data | yfinance | Free, covers all required ETFs (SLV, GLD, TIP, UUP, GDX, ^VIX) |
| Macro data | pandas_datareader + FRED API | Authoritative source for 10yr yield, Fed funds, CPI, PPI, payrolls |
| DXY proxy | UUP ETF via yfinance | DXY futures not free; UUP has high correlation |
| News | feedparser + requests/bs4 | RSS is stable and machine-readable; avoids fragile HTML scraping |
| Storage | sqlite3 | Zero-config, file-based, queryable, Windows-native |
| Indicators | pandas-ta | Pure Python (no compiled binaries), covers all required indicators |
| Charts | matplotlib (static) + plotly (HTML) | matplotlib for embedded report PNGs; plotly for interactive HTML |
| Config | python-dotenv + dataclasses | .env for secrets (FRED key), typed dataclasses for config objects |

### Anti-Look-Ahead Bias Controls

- All analysis functions accept an explicit `analysis_date` parameter; they filter data to `<= analysis_date`
- Signal engine receives a snapshot dataclass — it cannot re-fetch data
- pandas-ta standard indicators never peek forward when used correctly
- News items filtered to `published_at <= analysis_datetime`
- Historical context (Section 6) only compares to periods strictly before `analysis_datetime`

---

## Phased Roadmap

### Phase 1 — Foundation: Data Infrastructure + Technical Analysis
**Goal**: Working pipeline that fetches, stores, caches, and validates SLV and related ETF OHLCV, calculates all technical indicators, and prints a validated technical snapshot.

Files: all of `config/`, `modules/infrastructure/`, `modules/collection/price_fetcher.py`, `modules/collection/data_store.py`, `modules/collection/base_fetcher.py`, all of `modules/analysis/technical/`, `modules/reporting/models.py`, `main.py` (minimal CLI), `tests/` fixtures + price/indicator tests.

Data sources: yfinance (SLV, GLD, ^VIX, TIP, UUP, GDX).

Done when: `python main.py --style swing` prints a validated SLV technical snapshot with data freshness statuses and survives a yfinance outage by falling back to cache.

Risks: pandas-ta compatibility on Python 3.13 needs verification; ^VIX via yfinance is inconsistent — fallback to VIXY ETF.

### Phase 2 — Macro Data Pipeline + Macro Driver Scorecard
**Goal**: FRED API integration, 11 macro drivers scored, composite macro score produced.

Files: `modules/collection/macro_fetcher.py`, all of `modules/analysis/macro/`, tests + macro fixtures.

FRED Series: DGS10, FEDFUNDS, CPIAUCSL, PPIFIS, UNRATE, PAYEMS, T10YIE, DTWEXBGS.

Done when: Full macro scorecard (Section 4 of report) renders with scores, values, evidence, and data-freshness warnings per driver.

Risks: CPI/PPI lag by 1–2 months (expected, not error); FRED rate limits (cache aggressively).

### Phase 3 — News Collection, Classification, Event Detection
**Goal**: RSS feed collection, keyword-based impact classification, economic event detection and pre-event warnings.

Files: `modules/collection/news_fetcher.py`, `modules/collection/calendar_fetcher.py`, all of `modules/analysis/news/`, tests + news fixtures.

RSS Feeds: Kitco, Reuters Commodities, MarketWatch, FXStreet, Fed Reserve press releases.

Done when: News section renders with classified items and upcoming event warnings (FOMC/CPI/NFP flagged with countdown).

Risks: RSS URL changes break feeds — per-feed exception handling; keyword classification misses context but is transparent and debuggable.

### Phase 4 — Signal Engine, Risk Engine, Full 11-Section Report
**Goal**: Integration phase. All analysis layers combined into `SignalResult` + `RiskResult`. Full report generated in text and HTML formats.

Files: all of `modules/engines/`, all of `modules/reporting/sections/`, all of `modules/reporting/formatters/`, `modules/reporting/report_engine.py`, integration tests.

Signal weighting by trading style:
- Day: technical 70%, macro 15%, news 15%
- Swing: technical 50%, macro 30%, news 20%
- Position: technical 30%, macro 50%, news 20%
- Long-term: technical 10%, macro 65%, news 25%

Confidence reduction rules: unknown driver −8 (max −25), stale price −20, stale macro −10/series, no news feeds −15, high-impact event <24h −15, technical/macro conflict −10, VIX>30 −10. Floor: 5.

No-trade overrides: FOMC within 4 hours, CPI within 1 hour, price data >2 trading days old, ATR >3× its 50-day average.

Done when: `python main.py --style swing --output html` generates a complete 11-section report including disclaimer, with no crashes on stale or missing data.

### Phase 5 — CLI Polish, Windows Scheduling, Enhanced HTML Output
**Goal**: Full argparse CLI (`--style`, `--output`, `--refresh`, `--collect-only`, `--last-signal`, `--status`, `--open-browser`), Windows Task Scheduler XML helper, plotly interactive charts embedded as base64 in single-file HTML.

### Phase 6 — Testing, Validation, Hardening
**Goal**: Complete test suite, offline/mock mode, no-look-ahead bias validation tests, structured JSON signal history logging.

---

## Recommended Phase 1 Build Order

Build in this exact sequence (each step imports from previous):

1. `config/settings.py` — paths, constants, env loading
2. `modules/infrastructure/exceptions.py` — custom exception hierarchy (imported everywhere)
3. `modules/infrastructure/logger.py` — logging setup (needed before anything runs)
4. `modules/infrastructure/database.py` — schema creation, connection pool
5. `modules/reporting/models.py` — all dataclasses (module contracts)
6. `modules/infrastructure/validators.py` — OHLCV validators
7. `modules/collection/base_fetcher.py` — abstract fetcher with cache + freshness logic
8. `modules/collection/price_fetcher.py` — yfinance integration
9. `modules/collection/data_store.py` — SQLite read/write API
10. `modules/analysis/technical/indicators.py` — all indicator calculations
11. `modules/analysis/technical/volume_analysis.py`
12. `modules/analysis/technical/vol_regime.py`
13. `modules/analysis/technical/support_resistance.py`
14. `modules/analysis/technical/technical_analyzer.py` — orchestrator
15. `main.py` — minimal CLI: fetch + analyze + print snapshot
16. `tests/` — price fetcher + indicator tests with static fixtures

---

## Verification Plan

- After Phase 1: Run `python main.py --style swing` and confirm technical snapshot prints with data freshness status and no crashes; disconnect network and confirm cache fallback works.
- After Phase 2: Verify macro scorecard renders all 11 drivers; inject a stale series and confirm staleness warning appears and confidence penalty is applied.
- After Phase 3: Confirm news items appear classified; force an upcoming FOMC event in the test fixture and verify the pre-event warning fires.
- After Phase 4: Generate full report in both text and HTML formats; verify all 11 sections present, disclaimer appears, no-trade condition overrides signal when FOMC is imminent.
- Bias test: run signal engine on T-0 data, then append a future row and re-run — verify signal does not change.

---

## Coding Standards (per spec)

- All scripts include revision numbers starting with Rev 1
- `pathlib.Path` for all file paths (no hard-coded slashes)
- `logging` module throughout (rotating file + console)
- `try/except` with typed exceptions at all external boundaries
- Comments explain *why*, not *what*
- Modules separated; no cross-layer imports (lower layer never imports upper)
- Cache all fetched data locally; validate freshness on every read
- Stale or missing data is labeled explicitly, never silently dropped
- Every report includes the disclaimer: "This system is research and decision support, not personalized financial advice."
