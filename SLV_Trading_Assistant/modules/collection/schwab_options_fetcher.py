# Rev 1
"""
Schwab options chain fetcher.

Fetches the SLV options chain, extracts ATM implied volatility and 25-delta
put/call skew, persists the reading in iv_history for percentile tracking,
and returns an OptionsData object ready for use by the vol regime classifier.

Gracefully returns OptionsData(is_available=False) when:
  - Schwab client is not configured / auth failed
  - Market is closed and no near-term options exist
  - Any network or API error
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional

from modules.collection.data_store import DataStore
from modules.collection.schwab_client import get_schwab_client
from modules.infrastructure.logger import get_logger
from modules.reporting.models import OptionsData

log = get_logger("schwab_options")

_MIN_DTE = 14          # minimum days-to-expiry to consider
_MAX_DTE = 60          # maximum days-to-expiry to consider
_TARGET_DTE = 30       # preferred DTE when choosing expiry
_STRIKE_COUNT = 5      # strikes above and below ATM to request
_MIN_IV_READINGS = 20  # readings needed before percentile is reliable


class SchwabOptionsFetcher:

    def __init__(self) -> None:
        self._store = DataStore()

    def fetch_options_data(self, ticker: str) -> OptionsData:
        """
        Fetch ATM IV from Schwab, persist the reading, and return OptionsData
        with IV percentile computed from accumulated history.
        """
        now = datetime.now(timezone.utc)
        client = get_schwab_client()

        if client is None:
            return _unavailable(ticker, now, "Schwab client not available")

        try:
            return self._fetch_and_build(client, ticker.upper(), now)
        except Exception as exc:
            log.warning("Options fetch failed for %s: %s", ticker, exc)
            return _unavailable(ticker, now, f"Options fetch error: {exc}")

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _fetch_and_build(self, client, ticker: str, now: datetime) -> OptionsData:
        today = now.date()

        resp = client.get_option_chain(
            symbol=ticker,
            contract_type=client.Options.ContractType.ALL,
            strike_count=_STRIKE_COUNT,
            include_underlying_quote=True,
            strategy=client.Options.Strategy.SINGLE,
            strike_range=client.Options.StrikeRange.NEAR_THE_MONEY,
            from_date=today + timedelta(days=_MIN_DTE),
            to_date=today + timedelta(days=_MAX_DTE),
        )

        if not resp.is_success:
            raise RuntimeError(f"Schwab API HTTP {resp.status_code}")

        data = resp.json()
        if data.get("status") != "SUCCESS":
            raise RuntimeError(f"Options chain status: {data.get('status')}")

        underlying_price = float(data.get("underlyingPrice") or 0.0)
        if underlying_price <= 0:
            raise RuntimeError("underlyingPrice missing from options chain response")

        atm_iv, put_call_skew = self._extract_iv(data, underlying_price)
        if atm_iv <= 0:
            raise RuntimeError("Could not extract valid ATM IV from options chain")

        # Persist and compute percentile
        self._store.write_iv_reading(ticker, atm_iv, underlying_price)
        history = self._store.read_iv_history(ticker)

        warnings: list[str] = []
        if len(history) < _MIN_IV_READINGS:
            iv_percentile = -1.0
            remaining = _MIN_IV_READINGS - len(history)
            warnings.append(
                f"IV percentile needs {remaining} more daily reading(s) to be reliable"
            )
        else:
            iv_percentile = float(sum(1 for v in history if v < atm_iv) / len(history) * 100)

        log.info(
            "%s options: ATM_IV=%.1f%% iv_pct=%.1f skew=%.3f spot=%.3f",
            ticker, atm_iv * 100, iv_percentile, put_call_skew, underlying_price,
        )

        return OptionsData(
            ticker=ticker,
            atm_iv=atm_iv,
            iv_percentile=iv_percentile,
            put_call_skew=put_call_skew,
            underlying_price=underlying_price,
            fetched_at=now,
            is_available=True,
            warnings=warnings,
        )

    # ------------------------------------------------------------------
    # IV extraction helpers
    # ------------------------------------------------------------------

    def _extract_iv(
        self, data: dict, underlying_price: float
    ) -> tuple[float, float]:
        """Return (atm_iv_decimal, put_call_skew_decimal) from the chain payload."""
        call_map = data.get("callExpDateMap", {})
        put_map  = data.get("putExpDateMap", {})

        expiry_key = _find_target_expiry(call_map, _TARGET_DTE)
        if expiry_key is None:
            return 0.0, 0.0

        call_strikes = call_map.get(expiry_key, {})
        put_strikes  = put_map.get(expiry_key, {})

        if not call_strikes:
            return 0.0, 0.0

        # ATM strike: numerically nearest to current spot
        try:
            atm_strike = min(
                (float(k) for k in call_strikes),
                key=lambda s: abs(s - underlying_price),
            )
        except ValueError:
            return 0.0, 0.0

        call_entries = _nearest_entries(call_strikes, atm_strike)
        put_entries  = _nearest_entries(put_strikes,  atm_strike)

        call_iv = _entry_iv(call_entries)
        put_iv  = _entry_iv(put_entries)

        if call_iv > 0 and put_iv > 0:
            atm_iv = (call_iv + put_iv) / 2
        else:
            atm_iv = call_iv or put_iv

        skew = _compute_skew(call_strikes, put_strikes)
        return atm_iv, skew


# ---------------------------------------------------------------------------
# Module-level helpers (pure functions)
# ---------------------------------------------------------------------------

def _unavailable(ticker: str, now: datetime, reason: str) -> OptionsData:
    return OptionsData(
        ticker=ticker,
        atm_iv=0.0,
        iv_percentile=-1.0,
        put_call_skew=0.0,
        underlying_price=0.0,
        fetched_at=now,
        is_available=False,
        warnings=[reason],
    )


def _find_target_expiry(exp_map: dict, target_dte: int) -> Optional[str]:
    """Return the expiry key (e.g. '2026-07-17:45') closest to target_dte."""
    best_key, best_diff = None, float("inf")
    for key in exp_map:
        try:
            dte = int(key.split(":")[1])
        except (IndexError, ValueError):
            continue
        diff = abs(dte - target_dte)
        if diff < best_diff:
            best_diff, best_key = diff, key
    return best_key


def _nearest_entries(strikes: dict, target: float) -> Optional[list]:
    """Return the option entry list for the strike nearest to target."""
    if not strikes:
        return None
    nearest = min(strikes, key=lambda k: abs(float(k) - target))
    return strikes[nearest]


def _entry_iv(entries: Optional[list]) -> float:
    """Extract IV from the first entry; convert from percent to decimal."""
    if not entries:
        return 0.0
    raw = entries[0].get("volatility") or 0.0
    # Schwab returns volatility as a percentage (e.g. 24.5 = 24.5%)
    return float(raw) / 100.0


def _compute_skew(call_strikes: dict, put_strikes: dict) -> float:
    """
    25-delta put IV minus 25-delta call IV.
    Positive value = puts more expensive than calls (normal for equities/ETFs).
    Returns 0.0 when data is insufficient.
    """
    def _delta_iv(strikes: dict, target_abs_delta: float) -> float:
        best, best_diff = None, float("inf")
        for entries in strikes.values():
            if not entries:
                continue
            d = abs(float(entries[0].get("delta") or 999))
            if abs(d - target_abs_delta) < best_diff:
                best_diff = abs(d - target_abs_delta)
                best = entries[0]
        if best is None:
            return 0.0
        return _entry_iv([best])

    put_25d  = _delta_iv(put_strikes,  0.25)
    call_25d = _delta_iv(call_strikes, 0.25)
    return (put_25d - call_25d) if (put_25d > 0 and call_25d > 0) else 0.0
