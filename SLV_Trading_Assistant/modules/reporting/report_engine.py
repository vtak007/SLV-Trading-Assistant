# Rev 2  (Session 6: added JSON signal history logging to data/signals/)
"""
Report engine orchestrator.
Builds a ReportBundle, selects the appropriate formatter, generates the report,
saves it to disk, and returns the output path.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from config.settings import REPORTS_DIR, SIGNALS_DIR
from config.trading_styles import TradingStyle
from modules.infrastructure.database import get_connection
from modules.infrastructure.logger import get_logger
from modules.reporting.formatters import html_formatter, text_formatter
from modules.reporting.models import (
    MacroResult, NewsResult, PriceData, ReportBundle,
    RiskResult, SignalResult, TechnicalResult,
)

log = get_logger("report_engine")


class ReportEngine:

    def generate_report(
        self,
        price_data: PriceData,
        tech_result: TechnicalResult,
        macro_result: MacroResult,
        news_result: NewsResult,
        signal_result: SignalResult,
        risk_result: RiskResult,
        trading_style: TradingStyle,
        output_format: str = "text",
        generated_at: Optional[datetime] = None,
    ) -> tuple[str, Path]:
        """
        Build the full report.

        Returns
        -------
        content    : str   — report text or HTML
        saved_path : Path  — where the report was written to disk
        """
        as_of = generated_at or datetime.now(timezone.utc)

        bundle = ReportBundle(
            price_data    = price_data,
            tech_result   = tech_result,
            macro_result  = macro_result,
            news_result   = news_result,
            signal_result = signal_result,
            risk_result   = risk_result,
            trading_style = trading_style.value,
            generated_at  = as_of,
        )

        if output_format == "html":
            content = html_formatter.generate(bundle)
            ext     = ".html"
        else:
            content = text_formatter.generate(bundle)
            ext     = ".txt"

        saved_path = self._save(content, as_of, trading_style.value, ext)

        # Persist signal to database and JSON history
        self._persist_signal(signal_result, trading_style)
        self._write_signal_json(signal_result, trading_style, as_of)

        log.info("Report saved: %s", saved_path)
        return content, saved_path

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _save(
        self,
        content: str,
        as_of: datetime,
        style: str,
        ext: str,
    ) -> Path:
        REPORTS_DIR.mkdir(parents=True, exist_ok=True)
        ts       = as_of.strftime("%Y%m%d_%H%M%S")
        filename = f"slv_{style}_{ts}{ext}"
        path     = REPORTS_DIR / filename
        path.write_text(content, encoding="utf-8")
        return path

    def _persist_signal(
        self,
        signal: SignalResult,
        style: TradingStyle,
    ) -> None:
        """Write signal summary to the signals table for historical review."""
        raw = {
            "action":       signal.action,
            "confidence":   signal.confidence,
            "risk_score":   signal.risk_score,
            "regime":       signal.regime_label,
            "entry_zone":   signal.entry_zone,
            "stop_loss":    signal.stop_loss,
            "targets":      signal.targets,
            "explanation":  signal.explanation,
        }
        sql = """
            INSERT INTO signals
              (generated_at, trading_style, action, confidence, risk_score, raw_json)
            VALUES (?, ?, ?, ?, ?, ?)
        """
        try:
            with get_connection() as conn:
                conn.execute(sql, (
                    signal.generated_at.isoformat() if signal.generated_at else "",
                    style.value,
                    signal.action,
                    signal.confidence,
                    signal.risk_score,
                    json.dumps(raw),
                ))
                conn.commit()
        except Exception as exc:  # noqa: BLE001 — DB write failure must not abort report
            log.warning("Could not persist signal to DB: %s", exc)

    def _write_signal_json(
        self,
        signal: SignalResult,
        style: TradingStyle,
        as_of: datetime,
    ) -> Optional[Path]:
        """Write a structured JSON record of the signal to data/signals/."""
        payload = {
            "generated_at":      signal.generated_at.isoformat() if signal.generated_at else "",
            "trading_style":     style.value,
            "action":            signal.action,
            "confidence":        signal.confidence,
            "risk_score":        signal.risk_score,
            "regime_label":      signal.regime_label,
            "entry_zone":        list(signal.entry_zone),
            "stop_loss":         signal.stop_loss,
            "targets":           signal.targets,
            "position_size_pct": signal.position_size_pct,
            "bullish_evidence":  signal.bullish_evidence,
            "bearish_evidence":  signal.bearish_evidence,
            "conflicts":         signal.conflicts,
            "explanation":       signal.explanation,
            "no_trade_reason":   signal.no_trade_reason,
        }
        try:
            SIGNALS_DIR.mkdir(parents=True, exist_ok=True)
            ts       = as_of.strftime("%Y%m%d_%H%M%S")
            filename = f"signal_{ts}_{style.value}.json"
            path     = SIGNALS_DIR / filename
            path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
            log.info("Signal JSON written: %s", path)
            return path
        except Exception as exc:  # noqa: BLE001 — write failure must not abort report
            log.warning("Could not write signal JSON: %s", exc)
            return None
