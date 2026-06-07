# Rev 3  (permanent-error fast-fail: DNS failures skip retries)
"""
Abstract base fetcher.
Subclasses implement _fetch_fresh(); this base handles cache read/write,
freshness checks, and retry logic so those concerns don't leak into fetchers.

Set env var SLV_OFFLINE=1 to skip all live network calls and serve only from
the local pickle cache. Raises DataFetchError if no cache exists for a key.
"""
from __future__ import annotations

import os
import pickle
import socket
import time
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Optional

from config.settings import CACHE_DIR
from modules.infrastructure.exceptions import CacheError, DataFetchError
from modules.infrastructure.logger import get_logger

log = get_logger("base_fetcher")

_MAX_RETRIES = 3
_RETRY_BASE_DELAY = 2.0     # seconds; multiplied by attempt number for back-off


class BaseFetcher(ABC):

    def __init__(self, cache_ttl_seconds: int, max_retries: int = _MAX_RETRIES) -> None:
        self.cache_ttl = cache_ttl_seconds
        self.max_retries = max_retries
        self._cache_dir = CACHE_DIR

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def fetch(self, key: str, force_refresh: bool = False) -> Any:
        """
        Return data for `key`.
        Uses fresh cache when available; falls back to stale cache on live failure.
        When SLV_OFFLINE=1 only the local cache is consulted — no network calls.
        """
        cache_path = self._cache_path(key)

        # Offline mode: never touch the network
        if os.environ.get("SLV_OFFLINE") == "1":
            cached = self._read_cache(cache_path)
            if cached is not None:
                log.debug("Offline mode: serving from cache: %s", key)
                return cached["data"]
            raise DataFetchError(
                f"Offline mode (SLV_OFFLINE=1): no cache available for '{key}'"
            )

        if not force_refresh:
            cached = self._read_cache(cache_path)
            if cached is not None and self._is_fresh(cached):
                log.debug("Cache hit (fresh): %s", key)
                return cached["data"]

        try:
            data = self._fetch_with_retry(key)
        except DataFetchError:
            stale = self._read_cache(cache_path)
            if stale is not None:
                log.warning("Live fetch failed for '%s' — using stale cache", key)
                return stale["data"]
            raise

        self._write_cache(cache_path, data)
        return data

    # ------------------------------------------------------------------
    # Subclass contract
    # ------------------------------------------------------------------

    @abstractmethod
    def _fetch_fresh(self, key: str) -> Any:
        """Fetch live data from the external source. Must raise DataFetchError on failure."""

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _fetch_with_retry(self, key: str) -> Any:
        last_exc: Optional[Exception] = None
        for attempt in range(1, self.max_retries + 1):
            try:
                return self._fetch_fresh(key)
            except Exception as exc:
                last_exc = exc
                if _is_permanent_network_error(exc):
                    log.warning(
                        "Permanent network failure for '%s' (DNS/unreachable) — skipping retries: %s",
                        key, exc,
                    )
                    break
                log.warning(
                    "Fetch attempt %d/%d failed for '%s': %s",
                    attempt, self.max_retries, key, exc,
                )
                if attempt < self.max_retries:
                    time.sleep(_RETRY_BASE_DELAY * attempt)
        raise DataFetchError(
            f"All {self.max_retries} fetch attempts failed for '{key}'"
        ) from last_exc

    def _cache_path(self, key: str) -> Path:
        safe = key.replace("/", "_").replace("^", "").replace(" ", "_")
        return self._cache_dir / f"{safe}.pkl"

    def _is_fresh(self, cached: dict) -> bool:
        return (time.time() - cached.get("fetched_at", 0)) < self.cache_ttl

    def _read_cache(self, path: Path) -> Optional[dict]:
        if not path.exists():
            return None
        try:
            with path.open("rb") as f:
                return pickle.load(f)
        except Exception as exc:
            log.warning("Cache read failed for %s: %s", path.name, exc)
            return None

    def _write_cache(self, path: Path, data: Any) -> None:
        payload = {"fetched_at": time.time(), "data": data}
        try:
            with path.open("wb") as f:
                pickle.dump(payload, f, protocol=pickle.HIGHEST_PROTOCOL)
        except OSError as exc:
            raise CacheError(f"Failed to write cache {path.name}: {exc}") from exc


# ---------------------------------------------------------------------------
# Module-level helpers
# ---------------------------------------------------------------------------

def _is_permanent_network_error(exc: Exception) -> bool:
    """
    Walk the exception cause chain looking for a socket.gaierror (DNS failure)
    or similar non-retriable network condition.
    Returns True when retrying would be pointless.
    """
    seen: set[int] = set()
    node: Optional[Exception] = exc
    while node is not None and id(node) not in seen:
        seen.add(id(node))
        if isinstance(node, socket.gaierror):
            return True
        node = getattr(node, "__cause__", None) or getattr(node, "__context__", None)
    return False
