# Rev 3  (Session 5: added OptionsData for Schwab IV integration)
"""
Data contract dataclasses for the SLV Trading Assistant.
All inter-module data transfers use these types — never pass raw dicts across layer boundaries.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

import pandas as pd


# ---------------------------------------------------------------------------
# Layer 1 — Collection
# ---------------------------------------------------------------------------

@dataclass
class PriceData:
    ticker: str
    ohlcv: pd.DataFrame          # index: DatetimeIndex; cols: open/high/low/close/volume/adj_close
    fetched_at: datetime
    is_stale: bool = False
    warnings: list[str] = field(default_factory=list)
    source: str = "yfinance"     # "schwab" | "yfinance"


@dataclass
class OptionsData:
    ticker: str
    atm_iv: float               # ATM implied volatility, annualised decimal (0.245 = 24.5%)
    iv_percentile: float        # percentile vs stored history (0–100); -1 when < 20 readings
    put_call_skew: float        # 25-delta put IV minus 25-delta call IV; positive = put premium
    underlying_price: float     # SLV spot from options chain
    fetched_at: datetime
    is_available: bool = True
    warnings: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Layer 2 — Analysis: Technical
# ---------------------------------------------------------------------------

@dataclass
class TechnicalResult:
    ticker: str
    analysis_date: datetime
    indicators: dict = field(default_factory=dict)
    support_levels: list[float] = field(default_factory=list)
    resistance_levels: list[float] = field(default_factory=list)
    vol_regime: str = "unknown"         # low / normal / high / extreme
    trend_direction: str = "neutral"    # bullish / bearish / neutral
    warnings: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Layer 2 — Analysis: Macro
# ---------------------------------------------------------------------------

@dataclass
class MacroDriverScore:
    driver_name: str
    score: str                  # bullish / bearish / neutral / mixed / unknown
    value: Optional[float]
    evidence: str
    weight: float


@dataclass
class MacroResult:
    drivers: list[MacroDriverScore] = field(default_factory=list)
    composite_score: float = 0.0    # -1.0 (fully bearish) to +1.0 (fully bullish)
    missing_data_warnings: list[str] = field(default_factory=list)
    analysis_date: Optional[datetime] = None


# ---------------------------------------------------------------------------
# Layer 2 — Analysis: News
# ---------------------------------------------------------------------------

@dataclass
class NewsItem:
    headline: str
    source: str
    url: str
    published_at: Optional[datetime]
    fetched_at: datetime
    classification: str = "neutral"     # bullish / bearish / neutral / unknown
    short_impact: str = "unknown"
    medium_impact: str = "unknown"
    long_impact: str = "unknown"
    confidence: float = 0.0


@dataclass
class NewsResult:
    items: list[NewsItem] = field(default_factory=list)
    upcoming_events: list[dict] = field(default_factory=list)
    event_risk_level: str = "low"       # low / medium / high / critical
    analysis_datetime: Optional[datetime] = None


# ---------------------------------------------------------------------------
# Layer 3 — Engines
# ---------------------------------------------------------------------------

@dataclass
class SignalResult:
    action: str                                 # BUY / SELL / HOLD / NO_TRADE
    confidence: float                           # 0–100
    risk_score: float                           # 0–100
    regime_label: str = "unknown"
    entry_zone: tuple[float, float] = (0.0, 0.0)
    stop_loss: float = 0.0
    targets: list[float] = field(default_factory=list)
    position_size_pct: float = 0.0
    bullish_evidence: list[str] = field(default_factory=list)
    bearish_evidence: list[str] = field(default_factory=list)
    conflicts: list[str] = field(default_factory=list)
    explanation: str = ""
    no_trade_reason: str = ""
    generated_at: Optional[datetime] = None
    trading_style: str = "swing"


@dataclass
class RiskResult:
    atr_stop: float = 0.0
    position_size_shares: int = 0
    gap_risk_flag: bool = False
    major_event_flag: bool = False
    no_trade_conditions: list[str] = field(default_factory=list)
    atr_value: float = 0.0
    account_risk_pct: float = 0.01      # 1% of account per trade by default


# ---------------------------------------------------------------------------
# Layer 4 — Reporting bundle (passed to all section renderers)
# ---------------------------------------------------------------------------

@dataclass
class ReportBundle:
    price_data: PriceData
    tech_result: TechnicalResult
    macro_result: MacroResult
    news_result: NewsResult
    signal_result: SignalResult
    risk_result: RiskResult
    trading_style: str           # TradingStyle.value string to avoid circular import
    generated_at: datetime
