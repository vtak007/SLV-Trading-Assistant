# Rev 1
from dataclasses import dataclass
from enum import Enum


class TradingStyle(str, Enum):
    DAY       = "day"
    SWING     = "swing"
    POSITION  = "position"
    LONG_TERM = "long_term"


@dataclass(frozen=True)
class StyleWeights:
    technical:     float
    macro:         float
    news:          float
    buy_threshold: float  # composite must exceed this to trigger BUY
    sell_threshold: float  # composite must fall below this to trigger SELL

    def __post_init__(self) -> None:
        total = self.technical + self.macro + self.news
        if abs(total - 1.0) > 1e-9:
            raise ValueError(f"Weights must sum to 1.0, got {total:.4f}")
        if self.sell_threshold >= 0:
            raise ValueError("sell_threshold must be negative")
        if self.buy_threshold <= 0:
            raise ValueError("buy_threshold must be positive")


STYLE_WEIGHTS: dict[TradingStyle, StyleWeights] = {
    TradingStyle.DAY:       StyleWeights(technical=0.70, macro=0.15, news=0.15, buy_threshold=0.15, sell_threshold=-0.15),
    TradingStyle.SWING:     StyleWeights(technical=0.50, macro=0.30, news=0.20, buy_threshold=0.20, sell_threshold=-0.20),
    TradingStyle.POSITION:  StyleWeights(technical=0.30, macro=0.50, news=0.20, buy_threshold=0.25, sell_threshold=-0.25),
    TradingStyle.LONG_TERM: StyleWeights(technical=0.10, macro=0.65, news=0.25, buy_threshold=0.30, sell_threshold=-0.30),
}

DEFAULT_STYLE: TradingStyle = TradingStyle.SWING
