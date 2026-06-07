# Rev 1
"""
Macro analysis orchestrator.
Fetches all FRED series + relevant price data, runs sub-analyzers,
and returns a MacroResult with 8 scored drivers and a composite score.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

import pandas as pd

from config.data_sources import FRED_SERIES
from modules.collection.macro_fetcher import MacroFetcher
from modules.collection.price_fetcher import PriceFetcher
from modules.collection.data_store import DataStore
from modules.infrastructure.logger import get_logger
from modules.reporting.models import MacroDriverScore, MacroResult

from modules.analysis.macro.yield_analyzer import analyze_real_yield, analyze_nominal_yield
from modules.analysis.macro.dollar_analyzer import analyze_dollar
from modules.analysis.macro.inflation_analyzer import analyze_cpi, analyze_ppi
from modules.analysis.macro.fed_policy_analyzer import analyze_fed_policy
from modules.analysis.macro.gs_ratio_analyzer import analyze_gs_ratio
from modules.analysis.macro.sentiment_analyzer import analyze_sentiment

log = get_logger("macro_analyzer")

# Numeric mapping used only for composite score calculation
_SCORE_NUMERIC = {
    "bullish": 1.0,
    "neutral": 0.0,
    "bearish": -1.0,
    "mixed":   0.0,
    "unknown": 0.0,
}


class MacroAnalyzer:

    def __init__(self) -> None:
        self._fred   = MacroFetcher()
        self._prices = PriceFetcher()
        self._store  = DataStore()

    def analyze(
        self,
        analysis_date: Optional[datetime] = None,
        force_refresh: bool = False,
    ) -> MacroResult:
        """
        Fetch all data, score 8 macro drivers, and return MacroResult.
        Degrades gracefully when any series is unavailable.
        """
        if analysis_date is None:
            analysis_date = datetime.now(timezone.utc)

        warnings: list[str] = []
        fred_data  = self._collect_fred(force_refresh, warnings)
        price_data = self._collect_prices(warnings)

        drivers: list[MacroDriverScore] = [
            analyze_real_yield(
                dgs10=fred_data.get("DGS10",   pd.Series(dtype=float)),
                t10yie=fred_data.get("T10YIE", pd.Series(dtype=float)),
                analysis_date=analysis_date,
            ),
            analyze_nominal_yield(
                dgs10=fred_data.get("DGS10", pd.Series(dtype=float)),
                analysis_date=analysis_date,
            ),
            analyze_dollar(
                dtwexbgs=fred_data.get("DTWEXBGS", pd.Series(dtype=float)),
                analysis_date=analysis_date,
            ),
            analyze_cpi(
                cpi=fred_data.get("CPIAUCSL", pd.Series(dtype=float)),
                analysis_date=analysis_date,
            ),
            analyze_ppi(
                ppi=fred_data.get("PPIFIS", pd.Series(dtype=float)),
                analysis_date=analysis_date,
            ),
            analyze_fed_policy(
                fedfunds=fred_data.get("FEDFUNDS", pd.Series(dtype=float)),
                analysis_date=analysis_date,
            ),
            analyze_gs_ratio(
                gld_close=price_data.get("GLD", pd.Series(dtype=float)),
                slv_close=price_data.get("SLV", pd.Series(dtype=float)),
                analysis_date=analysis_date,
            ),
            analyze_sentiment(
                vixy_close=price_data.get("VIXY", pd.Series(dtype=float)),
                analysis_date=analysis_date,
            ),
        ]

        composite = _compute_composite(drivers, warnings)

        return MacroResult(
            drivers=drivers,
            composite_score=composite,
            missing_data_warnings=warnings,
            analysis_date=analysis_date,
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _collect_fred(
        self, force_refresh: bool, warnings: list[str]
    ) -> dict[str, pd.Series]:
        data: dict[str, pd.Series] = {}
        for sid in FRED_SERIES:
            try:
                s = self._fred.fetch_series(sid, force_refresh=force_refresh)
                self._store.write_macro_data(sid, s)
                data[sid] = s
            except Exception as exc:
                log.warning("FRED fetch failed for %s: %s", sid, exc)
                cached = self._store.read_macro_data(sid)
                if cached is not None:
                    data[sid] = cached
                    warnings.append(f"{sid}: live fetch failed -- using DB cache")
                else:
                    warnings.append(f"{sid}: no data available (live and DB both failed)")
        return data

    def _collect_prices(self, warnings: list[str]) -> dict[str, pd.Series]:
        data: dict[str, pd.Series] = {}
        for ticker in ("GLD", "SLV", "VIXY"):
            try:
                pd_obj = self._prices.fetch_price_data(ticker, force_refresh=False)
                data[ticker] = pd_obj.ohlcv["close"]
            except Exception as exc:
                log.warning("Price fetch failed for %s: %s", ticker, exc)
                warnings.append(f"{ticker}: price data unavailable")
        return data


def _compute_composite(
    drivers: list[MacroDriverScore], warnings: list[str]
) -> float:
    scored = [d for d in drivers if d.score != "unknown"]
    total_weight = sum(d.weight for d in scored)
    if total_weight == 0:
        warnings.append("All macro drivers unknown -- composite score unreliable")
        return 0.0
    return sum(_SCORE_NUMERIC[d.score] * d.weight for d in scored) / total_weight
