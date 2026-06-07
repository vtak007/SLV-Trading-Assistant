# Rev 1
"""
Detects directional conflicts between technical trend and macro composite score.
A conflict penalises confidence and is surfaced in the report as a caution.
"""
from __future__ import annotations

from modules.infrastructure.logger import get_logger
from modules.reporting.models import MacroResult, TechnicalResult

log = get_logger("engines.conflict_resolver")

# Macro composite must disagree by at least this magnitude to register as a conflict
_MACRO_THRESHOLD = 0.20


def detect_conflict(
    tech: TechnicalResult,
    macro: MacroResult,
) -> tuple[bool, list[str]]:
    """
    Return (has_conflict, conflict_descriptions).
    Conflict = tech bullish while macro bearish, or vice versa.
    """
    conflicts: list[str] = []

    tech_bull  = tech.trend_direction == "bullish"
    tech_bear  = tech.trend_direction == "bearish"
    macro_bull = macro.composite_score >=  _MACRO_THRESHOLD
    macro_bear = macro.composite_score <= -_MACRO_THRESHOLD

    if tech_bull and macro_bear:
        conflicts.append(
            f"Price action BULLISH but macro composite BEARISH "
            f"({macro.composite_score:+.2f}) -- consider macro headwind"
        )
    elif tech_bear and macro_bull:
        conflicts.append(
            f"Price action BEARISH but macro composite BULLISH "
            f"({macro.composite_score:+.2f}) -- technicals may be lagging macro"
        )

    if conflicts:
        log.info("Signal conflict detected: %s", conflicts)
    return bool(conflicts), conflicts
