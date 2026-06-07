# Rev 1
"""
Economic event detection and risk classification.
Checks how close upcoming FOMC/CPI/NFP events are and assigns
event_risk_level + human-readable countdown warnings.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from modules.infrastructure.logger import get_logger

log = get_logger("news.event_detector")

# Hours-before thresholds per event type
# no_trade: trading suspended (Session 4 signal engine checks this flag)
_WINDOWS: dict[str, dict[str, float]] = {
    "FOMC": {
        "no_trade": 4.0,
        "critical": 24.0,
        "high":     48.0,
        "medium":   72.0,
    },
    "CPI": {
        "no_trade": 1.0,
        "critical": 3.0,
        "high":     24.0,
        "medium":   48.0,
    },
    "NFP": {
        "no_trade": 1.0,
        "critical": 3.0,
        "high":     24.0,
        "medium":   48.0,
    },
}

_DEFAULT_WINDOW = _WINDOWS["CPI"]

_LEVEL_ORDER: dict[str, int] = {
    "low": 0, "medium": 1, "high": 2, "critical": 3
}


class EventDetector:

    def detect(
        self,
        upcoming_events: list[dict],
        as_of: Optional[datetime] = None,
    ) -> tuple[str, list[str]]:
        """
        Classify event risk from a list of upcoming event dicts.

        Returns
        -------
        event_risk_level : str
            "low" / "medium" / "high" / "critical"
        warnings : list[str]
            Human-readable countdown strings for each relevant event.
        """
        as_of = as_of or datetime.now(timezone.utc)
        risk_level = "low"
        warnings: list[str] = []

        for event in upcoming_events:
            name  = event.get("event_name", "UNKNOWN")
            sched = event.get("scheduled_at")
            if not isinstance(sched, datetime):
                continue
            if not sched.tzinfo:
                sched = sched.replace(tzinfo=timezone.utc)

            hours_away = (sched - as_of).total_seconds() / 3600.0
            if hours_away < 0:
                continue   # already past

            win    = _WINDOWS.get(name, _DEFAULT_WINDOW)
            fmt_dt = sched.strftime("%Y-%m-%d %H:%M UTC")

            if hours_away <= win["no_trade"]:
                risk_level = "critical"
                warnings.append(
                    f"NO-TRADE: {name} in {hours_away:.1f}h ({fmt_dt}) -- "
                    "trading suspended per risk rules"
                )
            elif hours_away <= win["critical"]:
                risk_level = _escalate(risk_level, "critical")
                warnings.append(
                    f"CRITICAL: {name} in {hours_away:.1f}h ({fmt_dt}) -- "
                    "extreme volatility expected; reduce exposure"
                )
            elif hours_away <= win["high"]:
                risk_level = _escalate(risk_level, "high")
                warnings.append(
                    f"HIGH RISK: {name} in {hours_away:.1f}h ({fmt_dt}) -- "
                    "reduce position sizing"
                )
            elif hours_away <= win["medium"]:
                risk_level = _escalate(risk_level, "medium")
                warnings.append(
                    f"CAUTION: {name} in {hours_away:.1f}h ({fmt_dt}) -- "
                    "monitor closely"
                )

        return risk_level, warnings

    def has_no_trade_condition(
        self,
        upcoming_events: list[dict],
        as_of: Optional[datetime] = None,
    ) -> bool:
        """Return True if any event triggers the no-trade window."""
        level, _ = self.detect(upcoming_events, as_of=as_of)
        # A no-trade warning sets risk_level to "critical" immediately,
        # but there could also be critical events that aren't no-trade.
        # Re-evaluate directly for the no-trade flag.
        as_of = as_of or datetime.now(timezone.utc)
        for event in upcoming_events:
            name  = event.get("event_name", "UNKNOWN")
            sched = event.get("scheduled_at")
            if not isinstance(sched, datetime):
                continue
            hours_away = (sched - as_of).total_seconds() / 3600.0
            win = _WINDOWS.get(name, _DEFAULT_WINDOW)
            if 0 <= hours_away <= win["no_trade"]:
                return True
        return False


def _escalate(current: str, candidate: str) -> str:
    """Return the more severe risk level."""
    return candidate if _LEVEL_ORDER.get(candidate, 0) > _LEVEL_ORDER.get(current, 0) else current
