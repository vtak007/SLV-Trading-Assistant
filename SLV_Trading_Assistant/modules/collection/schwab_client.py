# Rev 1
"""
Schwab OAuth2 client singleton.

First run (no token file): opens a browser for Schwab login and saves the token.
Subsequent runs: loads the stored token and auto-refreshes silently.
Returns None when credentials are absent or initialisation fails so all callers
degrade gracefully to their yfinance / no-options fallback.
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional

from config.settings import (
    SCHWAB_CLIENT_ID,
    SCHWAB_CLIENT_SECRET,
    SCHWAB_REDIRECT_URI,
    SCHWAB_TOKEN_PATH,
)
from modules.infrastructure.logger import get_logger

log = get_logger("schwab_client")

_client = None
_client_initialised = False


def get_schwab_client():
    """Return the authenticated Schwab client, or None if unavailable."""
    global _client, _client_initialised

    if _client_initialised:
        return _client

    _client_initialised = True

    if not SCHWAB_CLIENT_ID or not SCHWAB_CLIENT_SECRET:
        log.debug("Schwab credentials not configured — Schwab integration disabled")
        return None

    try:
        import schwab  # noqa: F401
    except ImportError:
        log.warning("schwab-py is not installed — run: pip install schwab-py")
        return None

    import schwab.auth

    token_path = Path(SCHWAB_TOKEN_PATH)

    try:
        if token_path.exists():
            _client = schwab.auth.client_from_token_file(
                token_path=str(token_path),
                api_key=SCHWAB_CLIENT_ID,
                app_secret=SCHWAB_CLIENT_SECRET,
            )
            log.info("Schwab client ready (token: %s)", token_path.name)
        else:
            log.info(
                "No Schwab token found at %s — starting first-time auth flow.", token_path
            )
            log.info(
                "A browser window will open. Log in to Schwab, then paste the "
                "full redirect URL when prompted."
            )
            _client = schwab.auth.client_from_manual_flow(
                api_key=SCHWAB_CLIENT_ID,
                app_secret=SCHWAB_CLIENT_SECRET,
                callback_url=SCHWAB_REDIRECT_URI,
                token_path=str(token_path),
            )
            log.info("Schwab auth complete — token saved to %s", token_path)
    except Exception as exc:
        log.warning("Schwab client init failed: %s — continuing without Schwab", exc)
        _client = None

    return _client


def reset_schwab_client() -> None:
    """Force re-initialisation on the next call (used in tests)."""
    global _client, _client_initialised
    _client = None
    _client_initialised = False
