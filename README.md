# SLV Trading Assistant

A modular Python research assistant and signal generator for trading the **SLV silver ETF**. The system collects price data, macro-economic indicators, and news headlines, analyses them together, and produces an explainable 11-section research report with a trade signal, confidence score, entry/stop/target levels, and risk warnings.

**This is a decision support tool only. It does not place trades. All output is research, not personalised financial advice.**

---

## Table of Contents

1. [Repository Layout](#repository-layout)
2. [What the System Does](#what-the-system-does)
3. [Prerequisites](#prerequisites)
4. [Installation](#installation)
5. [First-Time Setup](#first-time-setup)
6. [Running the System](#running-the-system)
7. [CLI Reference](#cli-reference)
8. [The 11-Section Report](#the-11-section-report)
9. [Trading Style Profiles](#trading-style-profiles)
10. [Data Sources and Tools](#data-sources-and-tools)
11. [Offline Mode](#offline-mode)
12. [Signal History](#signal-history)
13. [Windows Task Scheduler (Automated Daily Runs)](#windows-task-scheduler)
14. [Running the Tests](#running-the-tests)
15. [Project Layout](#project-layout)
16. [Disclaimer](#disclaimer)

---

## Repository Layout

```
SLV_Trading_Assistant/   # Main Python package — entry point, modules, tests, config
SLV Modular System Architect & Sub-Agent.md         # Architecture design document
SLV Modular System Architect & Sub-Agent Plan Implementation.md  # Implementation plan
reference-and-read-the-virtual-tulip.md             # Reference notes
```

All commands below assume you have moved into the `SLV_Trading_Assistant` package folder first:

```bash
cd SLV_Trading_Assistant
```

---

## What the System Does

The assistant runs a five-stage pipeline every time it executes:

```
[1] Collect   →   [2] Analyse   →   [3] Score   →   [4] Report   →   [5] Save
Price + Macro     Technical         Signal engine    11-section        SQLite DB
+ News data       + Macro           + Risk engine    text or HTML      + JSON file
                  + News                             report
```

**Stage 1 — Collect**: Downloads SLV price history from Schwab (yfinance as fallback), fetches SLV options chain data from Schwab for implied volatility, pulls FRED economic data, and collects news from five sources (three RSS feeds, NewsAPI.org, and Finnhub). Results are cached locally in SQLite and pickle files so the system still works if a data source is temporarily unavailable.

**Stage 2 — Analyse**: Calculates ~30 technical indicators (using live IV from the options chain when available), scores 8 macro drivers against SLV's known relationships, and classifies each news headline by sentiment and time horizon. Volume metrics (OBV trend, relative volume, VROC) are calculated and contribute to the technical score.

**Stage 3 — Score**: A signal engine aggregates the three analysis layers using weights and BUY/SELL thresholds that both differ by trading style. A confidence calculator applies penalty rules for stale data, conflicts between layers, and upcoming high-impact events. A risk engine calculates ATR-based stop levels and position sizing.

**Stage 4 — Report**: Renders a structured 11-section report in plain text or self-contained HTML (with an interactive 4-panel price chart).

**Stage 5 — Save**: Writes the signal to the SQLite `signals` table and to a timestamped JSON file in `data/signals/`.

---

## Prerequisites

| Requirement | Version | Notes |
|---|---|---|
| Python | 3.10 or newer | Tested on 3.13 |
| pip | any recent | comes with Python |
| Internet connection | required on first run | cache enables offline re-runs |
| FRED API key | free | see [First-Time Setup](#first-time-setup) |
| Schwab developer account | free | for price data + options IV |
| NewsAPI.org key | free tier available | for news headlines |
| Finnhub key | free tier available | for company news |

---

## Installation

```bash
# 1. From the repo root, move into the SLV_Trading_Assistant folder.
#    All commands below are run from inside that folder.
cd SLV_Trading_Assistant

# 2. (Recommended) Create and activate a virtual environment
python -m venv venv

# Windows PowerShell
venv\Scripts\Activate.ps1

# Windows Command Prompt
venv\Scripts\activate.bat

# macOS / Linux
source venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt
```

> **Note on pandas-ta**: if you are on Python 3.13 and see an installation error, try
> `pip install pandas-ta --no-build-isolation` or install `setuptools` first
> (`pip install setuptools`).

---

## First-Time Setup

### 1. Get a free FRED API key

FRED (Federal Reserve Economic Data) provides the macroeconomic data the system uses.

1. Go to [https://fred.stlouisfed.org/docs/api/api_key.html](https://fred.stlouisfed.org/docs/api/api_key.html)
2. Click **Request API Key** and create a free account.
3. Copy the key you receive by email.

### 2. Set up a Schwab developer app

Schwab provides real-time price data and the options chain used for implied volatility.

1. Go to [https://developer.schwab.com](https://developer.schwab.com) and log in with your **developer** account.
2. Create a new app and set the **redirect URI** to exactly `https://127.0.0.1`.
3. Copy the **Client ID** and **Client Secret** from the app details page.

### 3. Get a NewsAPI.org key

1. Register free at [https://newsapi.org/register](https://newsapi.org/register).
2. Copy the API key from your account dashboard.

### 4. Get a Finnhub key

1. Register free at [https://finnhub.io/register](https://finnhub.io/register).
2. Copy the API key from your account dashboard.

### 5. Create your `.env` file

```bash
# Copy the example file
copy .env.example .env       # Windows
cp .env.example .env         # macOS / Linux
```

Open `.env` in any text editor and fill in all keys:

```
FRED_API_KEY=your_fred_key_here
SCHWAB_CLIENT_ID=your_schwab_client_id_here
SCHWAB_CLIENT_SECRET=your_schwab_client_secret_here
NEWSAPI_API_KEY=your_newsapi_key_here
FINNHUB_API_KEY=your_finnhub_key_here
```

> **Schwab and news API keys are optional** — the system degrades gracefully if any key is absent. Without Schwab, price data falls back to yfinance and IV-based vol regime detection is disabled. Without NewsAPI/Finnhub, only the three RSS feeds are used.

### 6. Schwab first-time authentication

Schwab uses OAuth2 and requires a one-time interactive browser login to generate an access token.

1. Run the system from a **regular terminal** (not an IDE console):
   ```bash
   python main.py
   ```
2. The terminal will display a Schwab authorization URL. Open it in your browser.
3. Log in with your **Schwab brokerage (customer) account** — not your developer account.
4. Click **Allow** when prompted to grant the app access.
5. Your browser will redirect to `https://127.0.0.1` and show a "This site can't be reached" or "refused to connect" error — **this is expected and normal**. The authorization code is embedded in the URL, not the page content.
6. Copy the **entire URL** from the browser address bar and paste it at the `Redirect URL>` prompt in the terminal.
7. The terminal will confirm: `Schwab auth complete — token saved to data/schwab_token.json`.

All subsequent runs are fully headless — the token is refreshed automatically.

### 7. Verify the setup

```bash
python main.py --style swing
```

On the first run the system downloads ~1 year of price history and all FRED series. This takes 30–60 seconds depending on connection speed. Subsequent runs read from the local cache and complete in a few seconds.

---

## Running the System

### Interactive menu (recommended)

Run with no arguments to get a guided two-step menu — choose a command, then choose a trading style:

```bash
python main.py
```

```
==============================================================
  SLV Trading Assistant
==============================================================

  Commands:

    [1] Generate text report
    [2] Generate HTML report
    [3] Generate HTML report + open in browser
    [4] Force refresh + generate text report
    [5] Force refresh + generate HTML report + open in browser
    [6] Collect data only  (no report)
    [7] View last signal
    [8] View data status
    [9] Exit
```

After selecting a report command you are prompted to pick a trading style (Day / Swing / Position / Long Term). Pressing Enter defaults to Swing.

### CLI — text report in the terminal

```bash
python main.py --style swing
```

### CLI — HTML report (recommended)

```bash
python main.py --style swing --output html
```

The HTML file is saved to `data/reports/`. It is fully self-contained — you can email or archive it without any external dependencies.

### CLI — open the report in your browser automatically

```bash
python main.py --style swing --output html --open-browser
```

### CLI — force a fresh data download (ignore cache)

```bash
python main.py --style swing --refresh
```

### CLI — collect data only, no report

```bash
python main.py --collect-only
```

---

## CLI Reference

| Flag | Values | Default | Description |
|---|---|---|---|
| `--style` | `day` `swing` `position` `long_term` | `swing` | Trading style profile; changes analysis weights |
| `--output` | `text` `html` | `text` | Report format |
| `--refresh` | — | off | Force re-fetch all data, ignoring local cache |
| `--collect-only` | — | off | Fetch and store data; skip report generation |
| `--last-signal` | — | off | Print the most recent stored signal and exit |
| `--status` | — | off | Show data freshness for all sources and exit |
| `--open-browser` | — | off | Auto-open the HTML report after generation |

---

## The 11-Section Report

Every report contains the following sections in order:

| # | Section | What it contains |
|---|---|---|
| 1 | **Executive Summary** | Signal action (BUY / SELL / HOLD / NO TRADE), confidence %, risk score, current price, key metrics at a glance |
| 2 | **Trading Style** | Active style profile, domain weights used for scoring |
| 3 | **Technical Setup** | Price, all indicators (RSI, MACD, Bollinger Bands, ATR, MAs), support/resistance levels, detected patterns, volume regime |
| 4 | **Macro Scorecard** | Each of the 8 macro drivers with its score, current value, and evidence string |
| 5 | **News & Events** | Classified recent headlines, upcoming FOMC/CPI/NFP event countdown, event risk level |
| 6 | **Historical Context** | 52-week range position, 20-day drawdown, comparative context |
| 7 | **Signal Decision** | Composite score breakdown, bullish evidence, bearish evidence, detected conflicts |
| 8 | **Trade Plan** | Entry zone, stop-loss level, price targets (T1/T2/T3), position size as % of account |
| 9 | **Risk Warnings** | All active flags: gap risk, major event imminent, ATR extreme, no-trade overrides |
| 10 | **Data Quality** | Freshness status for every data source; staleness warnings with confidence impact |
| 11 | **Final Summary** | One-paragraph narrative explanation of the signal + full disclaimer |

The HTML report also includes a **4-panel interactive chart** (price with moving averages, volume, RSI, MACD) between sections 3 and 4. Each panel is separated by a visual divider, support/resistance levels are colour-coded relative to the current price (green = support below, red = resistance above), and the trade signal label is displayed above the chart title.

---

## Trading Style Profiles

The style controls how the three analysis layers are weighted when computing the composite score, and sets the sensitivity threshold required to trigger a BUY or SELL signal:

| Style | Technical | Macro | News | BUY threshold | SELL threshold | Best for |
|---|---|---|---|---|---|---|
| `day` | 70% | 15% | 15% | > +0.15 | < −0.15 | Intraday / very short holds |
| `swing` | 50% | 30% | 20% | > +0.20 | < −0.20 | 2–10 day holds |
| `position` | 30% | 50% | 20% | > +0.25 | < −0.25 | Weeks to a few months |
| `long_term` | 10% | 65% | 25% | > +0.30 | < −0.30 | Months to years |

Day style is more sensitive (fires on smaller composites); Long Term requires stronger conviction before generating a directional signal. All thresholds and weights are defined in `config/trading_styles.py`.

The default is `swing`. Use `--style position` or `--style long_term` if you are evaluating silver as a portfolio allocation rather than a short-term trade.

### Day style — intraday data

When `--style day` is selected, the system fetches **5-minute OHLCV bars** (Schwab primary, yfinance fallback) in addition to the standard daily data. Technical indicators (RSI, MACD, Bollinger Bands, ATR, moving averages) and ATR-based entry/stop/target levels are all computed on the intraday bars, giving a current-session picture rather than yesterday's close. The daily bars are still used for the HTML chart and all macro analysis.

---

## Data Sources and Tools

### Market Price Data

| Source | Role | Tickers / interval |
|---|---|---|
| **Schwab API** | Primary — daily OHLCV + options chain | `SLV`, `GLD`, `VIXY`, `TIP`, `UUP`, `GDX` (1-day bars) |
| **Schwab API** | Primary — intraday data for Day style | `SLV` (5-minute bars, last 5 trading days) |
| **yfinance** (Yahoo Finance) | Fallback for both daily and intraday | same tickers / same intervals |

> `^VIX` (CBOE Volatility Index) is not reliably available via yfinance; `VIXY` is used as a proxy with high correlation.

### Options Data (Implied Volatility)

| Source | What it provides |
|---|---|
| **Schwab options chain** | ATM implied volatility, put/call skew, and IV percentile (vs. rolling 20-day history) for SLV |

The IV percentile is used by the volatility regime classifier (`low / normal / high / extreme`). A minimum of 20 daily readings is needed before the percentile is reliable; earlier runs report raw IV only. IV data is stored in the `iv_history` database table.

### Macroeconomic Data

| Source | What it provides |
|---|---|
| **FRED REST API** (Federal Reserve Bank of St. Louis) | All 8 economic series listed below |

| FRED Series ID | Description | How it scores SLV |
|---|---|---|
| `DGS10` | 10-Year Treasury Constant Maturity Rate | Falling real yields are bullish for silver |
| `T10YIE` | 10-Year Breakeven Inflation Rate | Rising inflation expectations support silver |
| `FEDFUNDS` | Effective Federal Funds Rate | Fed cutting cycle is bullish; hiking is bearish |
| `CPIAUCSL` | CPI for All Urban Consumers (seasonally adjusted) | High/rising CPI supports silver as an inflation hedge |
| `PPIFIS` | PPI — Final Demand (commodity price pressure) | Rising PPI is bullish for industrial metal demand |
| `DTWEXBGS` | Nominal Broad U.S. Dollar Index | Falling dollar is bullish for dollar-denominated commodities |
| `UNRATE` | Unemployment Rate | Stored for context; informs Fed policy stance |
| `PAYEMS` | All Employees, Total Nonfarm (payrolls) | Stored for context; informs Fed policy stance |

> A free FRED API key is required. Register at [https://fred.stlouisfed.org](https://fred.stlouisfed.org). Without a key, all macro drivers return `UNKNOWN`.

### News Sources

Up to 100 headlines per run are collected from five sources, sorted newest-first, and classified as bullish / bearish / neutral for SLV.

**RSS feeds**

| Feed | Source |
|---|---|
| **MarketWatch** | Market Pulse headlines |
| **Federal Reserve** | Fed press releases and statements |
| **FXStreet** | Commodities and FX news |

**API sources** (require API keys in `.env`)

| Source | Coverage | Key |
|---|---|---|
| **NewsAPI.org** | Searches hundreds of publications for `silver OR SLV OR gold OR precious metals` — 30 articles per run | `NEWSAPI_API_KEY` |
| **Finnhub** | Company news for SLV and GLD over the last 7 days | `FINNHUB_API_KEY` |

> All news sources degrade gracefully — a failing source is logged and skipped; the system continues with whatever succeeds.

### Economic Event Calendar

FOMC meeting dates, CPI release dates, and NFP (Non-Farm Payroll) release dates are hardcoded from the official published schedules for 2025–2026. The system computes countdowns to each upcoming event and applies confidence penalties and no-trade overrides near high-impact events:

| Event | No-trade window | Confidence penalty |
|---|---|---|
| FOMC meeting | within 4 hours | −15 |
| CPI release | within 1 hour | −15 |
| Any high-impact event | within 24 hours | −15 |

### Python Libraries

| Library | Version | Purpose |
|---|---|---|
| `yfinance` | ≥ 0.2.40 | Yahoo Finance price downloads (fallback) |
| `schwab-py` | ≥ 1.4.0 | Schwab API — price history and options chain |
| `pandas` | ≥ 2.0.0 | DataFrame operations throughout the pipeline |
| `numpy` | ≥ 1.26.0 | Numerical calculations |
| `pandas-ta` | ≥ 0.3.14b | Technical indicators (MA, EMA, RSI, MACD, Bollinger Bands, ATR, OBV) |
| `requests` | ≥ 2.31.0 | FRED REST API, NewsAPI, and Finnhub HTTP fetches |
| `feedparser` | ≥ 6.0.10 | RSS feed parsing |
| `beautifulsoup4` | ≥ 4.12.0 | HTML parsing fallback for news fetching |
| `python-dotenv` | ≥ 1.0.0 | Loading API keys from `.env` |
| `matplotlib` | ≥ 3.7.0 | Static PNG chart fallback |
| `plotly` | ≥ 5.15.0 | Interactive 4-panel HTML chart (embedded inline) |
| `sqlite3` | stdlib | Local database storage (no separate install needed) |

### Local Storage

| Location | Contents |
|---|---|
| `data/slv_assistant.db` | SQLite database — price history, macro data, news items, IV history, economic events, signals, data quality log |
| `data/schwab_token.json` | Schwab OAuth2 token (auto-refreshed; never commit this file) |
| `data/cache/` | Pickle files — per-source cache for offline fallback |
| `data/reports/` | Generated HTML and text report files |
| `data/signals/` | One JSON file per run with full signal detail |
| `logs/` | Rotating log files (one per module) |

---

## Offline Mode

Once you have run the system at least once with a working internet connection, you can run it entirely from the local cache:

```powershell
$env:SLV_OFFLINE = "1"
python main.py --style swing
```

All network calls are skipped. The system raises a clear error if a required cache file does not exist yet (i.e., if the source has never been fetched).

To reset the environment variable:

```powershell
Remove-Item Env:SLV_OFFLINE
```

---

## Signal History

Every time a report is generated, two records are written:

1. **Database row** in the `signals` table (`data/slv_assistant.db`)
2. **JSON file** at `data/signals/signal_{timestamp}_{style}.json`

The JSON file contains: `action`, `confidence`, `risk_score`, `regime_label`, `entry_zone`, `stop_loss`, `targets`, `position_size_pct`, `bullish_evidence`, `bearish_evidence`, `conflicts`, `explanation`, `no_trade_reason`.

To view the most recent signal without regenerating a report:

```bash
python main.py --last-signal
```

To see data freshness for all stored sources:

```bash
python main.py --status
```

---

## Windows Task Scheduler

To have the system run automatically on weekday mornings, use the included scheduler helper:

```powershell
# Generate the XML and print the registration command
python scheduler/create_windows_task.py --time 06:30 --style swing --output html

# Generate and register in one step (requires admin rights or UAC prompt)
python scheduler/create_windows_task.py --time 06:30 --style swing --output html --install
```

To register manually after generating the XML:

```powershell
schtasks /Create /XML "scheduler\slv_task.xml" /TN "SLV Trading Assistant"
```

To delete the scheduled task later:

```powershell
schtasks /Delete /TN "SLV Trading Assistant" /F
```

The task is configured to run only when a network connection is available, and to start at the next available time if the machine was off during the scheduled window.

---

## Running the Tests

The test suite is fully offline — no network access is required. All tests use static fixtures or synthetic data.

```bash
# Run all tests
python -m pytest tests/ -v

# Run a specific test file
python -m pytest tests/test_indicators.py -v

# Quick pass/fail summary
python -m pytest tests/ -q
```

Expected result: **193 tests passed**.

---

## Project Layout

```
SLV_Trading_Assistant/
├── main.py                          # CLI entry point
├── requirements.txt
├── .env.example                     # Copy to .env and add your API keys
├── config/
│   ├── settings.py                  # Paths, cache TTLs, environment variables
│   ├── trading_styles.py            # Style profiles and domain weights
│   └── data_sources.py              # Tickers, FRED series IDs, RSS URLs
├── data/                            # Created automatically on first run
│   ├── slv_assistant.db
│   ├── schwab_token.json            # Created after first-time Schwab auth
│   ├── cache/
│   ├── reports/
│   └── signals/
├── modules/
│   ├── infrastructure/              # Exceptions, logging, database, validators
│   ├── collection/
│   │   ├── schwab_client.py         # Schwab OAuth2 singleton
│   │   ├── schwab_options_fetcher.py# Options chain + ATM IV extraction
│   │   ├── price_fetcher.py         # Schwab primary / yfinance fallback
│   │   ├── news_fetcher.py          # RSS feed fetcher
│   │   ├── newsapi_fetcher.py       # NewsAPI.org fetcher
│   │   ├── finnhub_fetcher.py       # Finnhub company news fetcher
│   │   ├── macro_fetcher.py         # FRED REST API fetcher
│   │   ├── calendar_fetcher.py      # Hardcoded economic event calendar
│   │   └── data_store.py            # SQLite read/write helpers
│   ├── analysis/
│   │   ├── technical/               # Indicators, volume, vol regime, S/R, patterns
│   │   ├── macro/                   # 8 macro driver analyzers + orchestrator
│   │   └── news/                    # Classifier, event detector, news orchestrator
│   ├── engines/                     # Signal engine, risk engine, confidence calc
│   └── reporting/
│       ├── models.py                # All output dataclasses
│       ├── sections/                # s01 through s11
│       ├── formatters/              # Text, HTML, chart generators
│       └── report_engine.py
├── scheduler/
│   └── create_windows_task.py       # Windows Task Scheduler XML helper
├── tests/
│   ├── fixtures/                    # Static JSON/CSV snapshots for offline tests
│   ├── conftest.py
│   └── test_*.py                    # 193 tests across all modules
└── logs/                            # Rotating log files (created automatically)
```

---

## Disclaimer

This system is research and decision support, not personalised financial advice. All signals, scores, and trade plans are generated algorithmically from publicly available data and are provided for informational purposes only. Past performance of any indicator or signal methodology does not guarantee future results. You are solely responsible for any trading decisions you make. Consult a licensed financial adviser before making investment decisions.
