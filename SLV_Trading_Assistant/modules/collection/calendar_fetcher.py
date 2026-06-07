# Rev 1
"""
Economic event calendar for FOMC, CPI, and NFP releases.
FOMC dates are hardcoded from the official Fed schedule.
CPI and NFP dates are from BLS published schedule.
2026 dates beyond the official release window are estimates -- update when BLS/Fed publish.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional

from modules.infrastructure.logger import get_logger

log = get_logger("calendar_fetcher")

# FOMC announcement dates (2nd day of each 2-day meeting)
# Source: Federal Reserve published meeting schedule
_FOMC_DATES: list[str] = [
    # 2025 (official)
    "2025-01-29", "2025-03-19", "2025-05-07", "2025-06-18",
    "2025-07-30", "2025-09-17", "2025-10-29", "2025-12-10",
    # 2026 (official where published, estimates beyond)
    "2026-01-28", "2026-03-18", "2026-04-29", "2026-06-17",
    "2026-07-29", "2026-09-16", "2026-10-28", "2026-12-09",
]

# BLS CPI (Consumer Price Index) release dates
# Source: BLS News Release schedule; announcement at 08:30 ET (13:30 UTC)
_CPI_DATES: list[str] = [
    # 2025 (official)
    "2025-01-15", "2025-02-12", "2025-03-12", "2025-04-10",
    "2025-05-13", "2025-06-11", "2025-07-15", "2025-08-12",
    "2025-09-10", "2025-10-15", "2025-11-13", "2025-12-10",
    # 2026 (official where published, estimates beyond)
    "2026-01-14", "2026-02-11", "2026-03-11", "2026-04-09",
    "2026-05-13", "2026-06-10", "2026-07-15", "2026-08-12",
    "2026-09-09", "2026-10-14", "2026-11-12", "2026-12-09",
]

# BLS Non-Farm Payrolls (Employment Situation) release dates
# Source: BLS News Release schedule; announcement at 08:30 ET (13:30 UTC)
_NFP_DATES: list[str] = [
    # 2025 (official)
    "2025-01-10", "2025-02-07", "2025-03-07", "2025-04-04",
    "2025-05-02", "2025-06-06", "2025-07-03", "2025-08-01",
    "2025-09-05", "2025-10-03", "2025-11-07", "2025-12-05",
    # 2026 (official where published, estimates beyond)
    "2026-01-09", "2026-02-06", "2026-03-06", "2026-04-03",
    "2026-05-01", "2026-06-05", "2026-07-02", "2026-08-07",
    "2026-09-04", "2026-10-02", "2026-11-06", "2026-12-04",
]

# Announcement times in UTC (most US releases at 08:30 ET = 13:30 UTC)
_RELEASE_HOUR_UTC = 13
_RELEASE_MINUTE_UTC = 30

# FOMC announcement is at 14:00 ET = 19:00 UTC (or 18:00 UTC summer)
_FOMC_HOUR_UTC = 19


class CalendarFetcher:
    """Provides upcoming economic event dates for event risk detection."""

    def get_upcoming_events(
        self,
        lookback_days: int = 0,
        lookahead_days: int = 30,
        as_of: Optional[datetime] = None,
    ) -> list[dict]:
        """
        Return events in the window [as_of - lookback_days, as_of + lookahead_days].
        Each event: {event_name, scheduled_at (datetime UTC), impact_level}.
        """
        as_of = as_of or datetime.now(timezone.utc)
        start = as_of - timedelta(days=lookback_days)
        end   = as_of + timedelta(days=lookahead_days)

        catalog: list[tuple[str, str, str, int, int]] = [
            # (date_str, event_name, impact_level, hour_utc, minute_utc)
            *[(d, "FOMC", "critical", _FOMC_HOUR_UTC,    0)  for d in _FOMC_DATES],
            *[(d, "CPI",  "high",     _RELEASE_HOUR_UTC, _RELEASE_MINUTE_UTC) for d in _CPI_DATES],
            *[(d, "NFP",  "high",     _RELEASE_HOUR_UTC, _RELEASE_MINUTE_UTC) for d in _NFP_DATES],
        ]

        events: list[dict] = []
        for date_str, name, level, hour, minute in catalog:
            try:
                dt = datetime.fromisoformat(date_str).replace(
                    hour=hour, minute=minute, second=0, tzinfo=timezone.utc
                )
                if start <= dt <= end:
                    events.append({
                        "event_name":   name,
                        "scheduled_at": dt,
                        "impact_level": level,
                    })
            except ValueError:
                log.warning("Invalid date string in calendar: %s", date_str)
                continue

        events.sort(key=lambda e: e["scheduled_at"])
        log.debug(
            "Calendar: %d events in [%s, %s]",
            len(events), start.date(), end.date(),
        )
        return events
