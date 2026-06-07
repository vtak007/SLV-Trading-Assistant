# Rev 3  (added NEWSAPI_API_KEY + FINNHUB_API_KEY)
from pathlib import Path
import os
from dotenv import load_dotenv

load_dotenv()

BASE_DIR: Path = Path(__file__).resolve().parent.parent
DATA_DIR: Path = BASE_DIR / "data"
CACHE_DIR: Path = DATA_DIR / "cache"
REPORTS_DIR: Path = DATA_DIR / "reports"
SIGNALS_DIR: Path = DATA_DIR / "signals"
DB_PATH: Path = DATA_DIR / "slv_assistant.db"
LOG_DIR: Path = BASE_DIR / "logs"

for _d in (DATA_DIR, CACHE_DIR, REPORTS_DIR, SIGNALS_DIR, LOG_DIR):
    _d.mkdir(parents=True, exist_ok=True)

FRED_API_KEY: str = os.getenv("FRED_API_KEY", "")
LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")

# Schwab API
SCHWAB_CLIENT_ID:    str = os.getenv("SCHWAB_CLIENT_ID", "")
SCHWAB_CLIENT_SECRET: str = os.getenv("SCHWAB_CLIENT_SECRET", "")
SCHWAB_TOKEN_PATH:   str = os.getenv("SCHWAB_TOKEN_PATH", str(DATA_DIR / "schwab_token.json"))
SCHWAB_REDIRECT_URI: str = os.getenv("SCHWAB_REDIRECT_URI", "https://127.0.0.1")

# News API keys (optional — sources are skipped when key is absent)
NEWSAPI_API_KEY:  str = os.getenv("NEWSAPI_API_KEY", "")
FINNHUB_API_KEY:  str = os.getenv("FINNHUB_API_KEY", "")

# Cache freshness thresholds (seconds)
PRICE_CACHE_TTL: int = 3_600          # 1 hour
MACRO_CACHE_TTL: int = 86_400 * 7    # 7 days — FRED updates monthly, cache aggressively
NEWS_CACHE_TTL: int = 3_600           # 1 hour

# Staleness thresholds
PRICE_STALE_TRADING_DAYS: int = 2

# Default historical lookback for price fetches
DEFAULT_LOOKBACK_DAYS: int = 365
