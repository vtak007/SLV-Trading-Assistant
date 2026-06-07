# Rev 1
"""
Risk calculation engine.
Produces ATR-based stop loss, position sizing, and risk flags.
Position size (shares) is expressed per $10,000 account at 1% risk per trade;
scale proportionally for other account sizes.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from modules.infrastructure.logger import get_logger
from modules.reporting.models import (
    NewsResult, PriceData, RiskResult, SignalResult, TechnicalResult,
)

log = get_logger("engines.risk_engine")

_DEFAULT_ACCOUNT  = 10_000.0
_ATR_STOP_MULT    = 2.0
_ATR_GAP_THRESHOLD = 1.5   # last bar's high-low range > 1.5 * ATR signals gap risk


class RiskEngine:

    def calculate(
        self,
        tech: TechnicalResult,
        news: NewsResult,
        price_data: PriceData,
        signal: SignalResult,
        account_size: float = _DEFAULT_ACCOUNT,
        account_risk_pct: float = 0.01,
        as_of: Optional[datetime] = None,
    ) -> RiskResult:
        """Produce a RiskResult from technical data and the already-generated signal."""
        _ = as_of or datetime.now(timezone.utc)  # reserved for future date-aware logic

        ind   = tech.indicators
        close = ind.get("close") or 0.0
        atr   = ind.get("atr_14") or 0.0

        # ATR-based stop loss level
        atr_stop = (
            round(close - _ATR_STOP_MULT * atr, 2)
            if close > 0 and atr > 0
            else 0.0
        )

        # Position size in shares for the reference account
        if atr > 0 and close > 0 and signal.action in ("BUY", "SELL"):
            dollar_risk = account_size * account_risk_pct
            stop_dist   = _ATR_STOP_MULT * atr
            shares      = max(0, int(dollar_risk / stop_dist))
        else:
            shares = 0

        # Gap risk: last bar range wider than 1.5x ATR suggests overnight gaps can blow stops
        gap_flag = False
        if atr > 0 and not price_data.ohlcv.empty:
            last          = price_data.ohlcv.iloc[-1]
            bar_range     = float(last["high"]) - float(last["low"])
            gap_flag      = bar_range > _ATR_GAP_THRESHOLD * atr

        major_event_flag = news.event_risk_level in ("critical", "high")

        no_trade = [r for r in signal.no_trade_reason.split("; ") if r] \
            if signal.no_trade_reason else []

        log.info(
            "Risk: atr_stop=%.2f shares=%d gap=%s event=%s",
            atr_stop, shares, gap_flag, major_event_flag,
        )
        return RiskResult(
            atr_stop             = atr_stop,
            position_size_shares = shares,
            gap_risk_flag        = gap_flag,
            major_event_flag     = major_event_flag,
            no_trade_conditions  = no_trade,
            atr_value            = round(atr, 4),
            account_risk_pct     = account_risk_pct,
        )
