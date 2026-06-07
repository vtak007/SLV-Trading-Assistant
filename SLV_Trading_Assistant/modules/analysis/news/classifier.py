# Rev 1
"""
Keyword/rule-based news classifier for SLV impact.
Classifies each NewsItem as bullish / bearish / neutral for silver and assigns
short/medium/long horizon impact and a rule-confidence score.
"""
from __future__ import annotations

import re
from dataclasses import replace

from modules.infrastructure.logger import get_logger
from modules.reporting.models import NewsItem

log = get_logger("news.classifier")

# Each pattern has a weight. Weights are summed to produce directional scores.
_BULLISH: list[tuple[re.Pattern, float]] = [
    (re.compile(r"\bsilver\s+(rise|rises|rising|rally|rallies|surges?|jumps?|gains?|higher|climbs?)\b", re.I), 2.0),
    (re.compile(r"\bgold\s+(rally|rallies|surges?|jumps?|gains?|higher|climbs?)\b", re.I), 1.5),
    (re.compile(r"\b(rate\s+cut|rate\s+cuts|cutting\s+rates?|cuts?\s+rates?)\b", re.I), 1.5),
    (re.compile(r"\bdovish\b", re.I), 1.5),
    (re.compile(r"\b(quantitative\s+easing|QE\b)", re.I), 1.5),
    (re.compile(r"\binflation\s+(rises?|surges?|spikes?|hotter|accelerates?|elevated|beats?)\b", re.I), 1.0),
    (re.compile(r"\b(cpi|ppi)\s+(beats?|above\s+forecast|higher\s+than\s+expected|hotter)\b", re.I), 1.0),
    (re.compile(r"\bdollar\s+(falls?|drops?|weakens?|slides?|lower|declines?)\b", re.I), 1.5),
    (re.compile(r"\b(dxy|dollar\s+index)\s+(falls?|drops?|weakens?|slides?)\b", re.I), 1.5),
    (re.compile(r"\bsafe.?haven\s+(demand|buying|flows?|bid)\b", re.I), 1.5),
    (re.compile(r"\b(supply\s+deficit|supply\s+crunch|supply\s+squeeze|undersupply)\b", re.I), 1.0),
    (re.compile(r"\bindustrial\s+(demand|buying|orders?)\b", re.I), 1.0),
    (re.compile(r"\bgold.silver\s+ratio\s+(falls?|drops?|decreases?|narrows?|lower)\b", re.I), 1.0),
    (re.compile(r"\b(recession|slowdown|economic\s+contraction|GDP\s+falls?)\b", re.I), 0.75),
    (re.compile(r"\bgeopolitical\s+(tension|risk|crisis|conflict|instability)\b", re.I), 0.75),
    (re.compile(r"\bfed\s+(pivot|pauses?|holds?|turns?\s+dovish)\b", re.I), 1.0),
    (re.compile(r"\bsilver\s+(bullish|upside|breakout|strong|outperforms?)\b", re.I), 2.0),
    (re.compile(r"\bprecious\s+metals?\s+(rally|rise|gains?|bullish|climbs?)\b", re.I), 1.5),
    (re.compile(r"\breal\s+yields?\s+(fall|falls?|drops?|negative|lower)\b", re.I), 1.0),
    (re.compile(r"\b(ETF\s+inflows?|gold\s+inflows?|silver\s+inflows?)\b", re.I), 1.0),
]

_BEARISH: list[tuple[re.Pattern, float]] = [
    (re.compile(r"\bsilver\s+(falls?|drops?|slumps?|tumbles?|slides?|declines?|lower|retreats?)\b", re.I), 2.0),
    (re.compile(r"\bgold\s+(falls?|drops?|slumps?|tumbles?|slides?|declines?|retreats?)\b", re.I), 1.5),
    (re.compile(r"\b(rate\s+hike|rate\s+hikes?|hiking\s+rates?|hikes?\s+rates?)\b", re.I), 1.5),
    (re.compile(r"\bhawkish\b", re.I), 1.5),
    (re.compile(r"\b(quantitative\s+tightening|QT\b)\b", re.I), 1.5),
    (re.compile(r"\bdollar\s+(rises?|rallies?|strengthens?|higher|gains?|climbs?)\b", re.I), 1.5),
    (re.compile(r"\b(dxy|dollar\s+index)\s+(rises?|rallies?|strengthens?|higher)\b", re.I), 1.5),
    (re.compile(r"\brisk.on\b", re.I), 0.75),
    (re.compile(r"\b(supply\s+surplus|oversupply|excess\s+supply)\b", re.I), 1.0),
    (re.compile(r"\bgold.silver\s+ratio\s+(rises?|climbs?|increases?|widens?|higher)\b", re.I), 1.0),
    (re.compile(r"\bsilver\s+(bearish|downside|breakdown|weak|underperforms?)\b", re.I), 2.0),
    (re.compile(r"\bprecious\s+metals?\s+(fall|falls?|drops?|decline|bearish|sell.off)\b", re.I), 1.5),
    (re.compile(r"\binflation\s+(cools?|eases?|falls?|drops?|cold|below\s+forecast|miss)\b", re.I), 1.0),
    (re.compile(r"\b(cpi|ppi)\s+(misses?|below\s+forecast|lower\s+than\s+expected|cold|soft)\b", re.I), 1.0),
    (re.compile(r"\beconomy\s+(strong|resilient|beats?|robust|accelerates?)\b", re.I), 0.75),
    (re.compile(r"\breal\s+yields?\s+(rise|rises|rises?|higher|positive|climbs?)\b", re.I), 1.0),
    (re.compile(r"\b(ETF\s+outflows?|gold\s+outflows?|silver\s+outflows?)\b", re.I), 1.0),
]

# Horizon indicators
_SHORT_HORIZON: list[re.Pattern] = [
    re.compile(r"\b(today|intraday|session|overnight|spike|flash|quick|immediate)\b", re.I),
    re.compile(r"\b(fomc|cpi|nfp|ppi|payroll|jobs\s+report|fed\s+decision)\b", re.I),
]
_LONG_HORIZON: list[re.Pattern] = [
    re.compile(r"\b(trend|long.?term|secular|structural|decade|multi.?year|annual)\b", re.I),
    re.compile(r"\b(monetary\s+policy|federal\s+reserve|inflation\s+target|structural)\b", re.I),
]

# Minimum score differential for a directional classification
_DOMINANCE_RATIO = 1.4   # winning side must be >= 1.4x the losing side


class NewsClassifier:

    def classify(self, item: NewsItem) -> NewsItem:
        """Return a new NewsItem with classification fields populated."""
        text = item.headline

        bull = _score(text, _BULLISH)
        bear = _score(text, _BEARISH)
        total = bull + bear

        if total == 0.0:
            cls = "neutral"
            conf = 0.30
        elif bull >= bear * _DOMINANCE_RATIO:
            cls  = "bullish"
            conf = min(0.90, 0.40 + bull / 5.0)
        elif bear >= bull * _DOMINANCE_RATIO:
            cls  = "bearish"
            conf = min(0.90, 0.40 + bear / 5.0)
        else:
            cls  = "neutral"   # mixed signals cancel out
            conf = 0.35

        is_short = any(p.search(text) for p in _SHORT_HORIZON)
        is_long  = any(p.search(text) for p in _LONG_HORIZON)

        short_impact  = cls if is_short else "neutral"
        medium_impact = cls
        long_impact   = cls if is_long  else "neutral"

        return replace(
            item,
            classification=classification_str(cls),
            short_impact=short_impact,
            medium_impact=medium_impact,
            long_impact=long_impact,
            confidence=round(conf, 3),
        )

    def classify_batch(self, items: list[NewsItem]) -> list[NewsItem]:
        return [self.classify(item) for item in items]


# ---------------------------------------------------------------------------
# Module-level helpers
# ---------------------------------------------------------------------------

def _score(text: str, patterns: list[tuple[re.Pattern, float]]) -> float:
    total = 0.0
    for pat, weight in patterns:
        if pat.search(text):
            total += weight
    return total


def classification_str(cls: str) -> str:
    """Validate classification string; fall back to 'neutral'."""
    return cls if cls in {"bullish", "bearish", "neutral", "unknown"} else "neutral"
