# SLV Modular Trading System — Project Instructions

## Key Files

| File | Purpose |
|---|---|
| `SLV_Trading_Assistant\main.py` | Entry point — runs the trading assistant; shows interactive menu when run with no arguments |
| `SLV_Trading_Assistant\requirements.txt` | Python dependencies |
| `SLV_Trading_Assistant\.env` | Environment variables (API keys etc.) — never commit |
| `SLV_Trading_Assistant\.env.example` | Safe template showing required env vars |
| `SLV_Trading_Assistant\config\settings.py` | Core application settings + all API key constants |
| `SLV_Trading_Assistant\config\data_sources.py` | Tickers, FRED series, RSS feed URLs |
| `SLV_Trading_Assistant\config\trading_styles.py` | Trading style definitions, domain weights, and per-style BUY/SELL thresholds |
| `SLV_Trading_Assistant\modules\collection\schwab_client.py` | Schwab OAuth2 singleton — loads token from `data\schwab_token.json` |
| `SLV_Trading_Assistant\modules\collection\schwab_options_fetcher.py` | Fetches SLV options chain; extracts ATM IV, skew, IV percentile |
| `SLV_Trading_Assistant\modules\collection\price_fetcher.py` | Price data — Schwab primary, yfinance fallback (daily bars) |
| `SLV_Trading_Assistant\modules\collection\intraday_fetcher.py` | 5-min intraday bars — Schwab primary, yfinance fallback; used by Day style |
| `SLV_Trading_Assistant\modules\collection\news_fetcher.py` | RSS feed fetcher (3 feeds) |
| `SLV_Trading_Assistant\modules\collection\newsapi_fetcher.py` | NewsAPI.org fetcher — silver/gold/SLV headlines |
| `SLV_Trading_Assistant\modules\collection\finnhub_fetcher.py` | Finnhub company news fetcher — SLV + GLD |
| `SLV_Trading_Assistant\modules\collection\macro_fetcher.py` | FRED REST API fetcher |
| `SLV_Trading_Assistant\modules\collection\data_store.py` | SQLite read/write helpers |
| `SLV_Trading_Assistant\modules\analysis\news\news_analyzer.py` | News orchestrator — merges all 5 sources, classifies, caps at 100 items |
| `SLV_Trading_Assistant\modules\analysis\news\classifier.py` | Keyword/regex news classifier (bullish/bearish/neutral) |
| `SLV_Trading_Assistant\modules\reporting\models.py` | All inter-module data contract dataclasses |
| `SLV_Trading_Assistant\modules\infrastructure\database.py` | DB schema init (includes iv_history table) |
| `SLV_Trading_Assistant\data\slv_assistant.db` | SQLite database |
| `SLV_Trading_Assistant\data\schwab_token.json` | Schwab OAuth2 token — auto-created on first auth; never commit |
| `SLV_Trading_Assistant\scheduler\create_windows_task.py` | Registers the Windows scheduled task |
| `SLV_Trading_Assistant\scheduler\slv_task.xml` | Task Scheduler XML definition |
| `SLV_Trading_Assistant\logs\slv_assistant.log` | Runtime log |
| `SLV_Trading_Assistant\tests\` | Test suite (pytest) |
| `SLV_Trading_Assistant\PROGRESS.md` | Development progress notes |
| `SLV_Trading_Assistant\README.md` | Project readme |
| `SLV Modular System Architect & Sub-Agent Plan Implementation.md` | Implementation plan |
| `SLV Modular System Architect & Sub-Agent.md` | Architecture design document |

## Notes

Python project — use `pip install -r requirements.txt` to install dependencies. Never commit `.env`. Tests run with `pytest` from the `SLV_Trading_Assistant` folder.

## Key Behavioural Notes

- **Interactive menu**: running `python main.py` with no arguments shows a two-step menu (command → trading style). CLI flags still work as before for automated/scheduled runs.
- **HTML reports open in browser** via `os.startfile()` (Windows-native); `webbrowser.open()` kept as non-Windows fallback.
- **Style-specific thresholds**: BUY/SELL signal thresholds differ by style (Day ±0.15 → Long Term ±0.30); defined alongside weights in `trading_styles.py`.
- **Volume scoring**: OBV trend (±0.10) and high relative-volume confirmation (±0.05) now contribute to the technical domain score in `score_aggregator.py`.
- **Day style intraday data**: when `--style day` is selected, `intraday_fetcher.py` fetches 5-min OHLCV bars (Schwab primary, yfinance fallback) for technical analysis instead of daily bars. Daily bars are still used for the HTML chart and macro context.
- **Schwab response check**: all Schwab API response checks use `resp.is_success` (httpx) not `resp.ok` (requests). Do not revert this.
