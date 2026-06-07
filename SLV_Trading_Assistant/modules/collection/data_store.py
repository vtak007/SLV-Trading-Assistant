# Rev 4  (added write_iv_reading / read_iv_history for Schwab IV percentile tracking)
"""Unified SQLite read/write API. All persistence goes through this class."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

import pandas as pd

from modules.infrastructure.database import get_connection
from modules.infrastructure.exceptions import DatabaseError
from modules.infrastructure.logger import get_logger
from modules.reporting.models import NewsItem, PriceData

log = get_logger("data_store")


class DataStore:

    # ------------------------------------------------------------------
    # Price data
    # ------------------------------------------------------------------

    def write_price_data(self, price_data: PriceData) -> int:
        """
        Upsert OHLCV rows for a ticker.
        INSERT OR REPLACE handles duplicate (ticker, date) pairs safely.
        Returns the number of rows written.
        """
        df = price_data.ohlcv.copy()
        df.index.name = "date"
        df = df.reset_index()
        df["date"] = df["date"].astype(str).str[:10]   # keep YYYY-MM-DD only
        df["ticker"] = price_data.ticker
        df["fetched_at"] = price_data.fetched_at.isoformat()
        df["is_stale"] = int(price_data.is_stale)

        # Ensure adj_close exists (some older cache entries may lack it)
        if "adj_close" not in df.columns:
            df["adj_close"] = df["close"]

        rows = df[[
            "ticker", "date", "open", "high", "low",
            "close", "volume", "adj_close", "fetched_at", "is_stale",
        ]].to_dict(orient="records")

        sql = """
            INSERT OR REPLACE INTO price_data
              (ticker, date, open, high, low, close, volume, adj_close, fetched_at, is_stale)
            VALUES
              (:ticker, :date, :open, :high, :low, :close, :volume, :adj_close, :fetched_at, :is_stale)
        """
        with get_connection() as conn:
            conn.executemany(sql, rows)

        log.info("Wrote %d price rows for %s", len(rows), price_data.ticker)
        return len(rows)

    def read_price_data(
        self,
        ticker: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> Optional[pd.DataFrame]:
        """
        Read price rows for `ticker` from SQLite.
        Returns a DataFrame indexed by date, or None if no rows exist.
        Enforces analysis_date boundary: caller passes end_date to prevent look-ahead.
        """
        sql = """
            SELECT date, open, high, low, close, volume, adj_close, is_stale
            FROM price_data
            WHERE ticker = ?
        """
        params: list = [ticker.upper()]

        if start_date:
            sql += " AND date >= ?"
            params.append(start_date)
        if end_date:
            sql += " AND date <= ?"
            params.append(end_date)

        sql += " ORDER BY date ASC"

        with get_connection() as conn:
            rows = conn.execute(sql, params).fetchall()

        if not rows:
            return None

        df = pd.DataFrame([dict(r) for r in rows])
        df["date"] = pd.to_datetime(df["date"])
        df = df.set_index("date")
        return df

    def mark_price_stale(self, ticker: str) -> None:
        """Set is_stale=1 for every row belonging to `ticker`."""
        with get_connection() as conn:
            conn.execute(
                "UPDATE price_data SET is_stale = 1 WHERE ticker = ?",
                (ticker.upper(),),
            )
        log.info("Marked all %s price rows as stale", ticker)

    def latest_price_date(self, ticker: str) -> Optional[str]:
        """Return the most recent YYYY-MM-DD date stored for `ticker`, or None."""
        with get_connection() as conn:
            row = conn.execute(
                "SELECT MAX(date) AS latest FROM price_data WHERE ticker = ?",
                (ticker.upper(),),
            ).fetchone()
        return row["latest"] if row and row["latest"] else None

    # ------------------------------------------------------------------
    # Macro data
    # ------------------------------------------------------------------

    def write_macro_data(self, series_id: str, series: pd.Series) -> int:
        """
        Upsert FRED macro rows for a series.
        INSERT OR REPLACE handles duplicate (series_id, date) pairs safely.
        Returns the number of rows written.
        """
        df = series.reset_index()
        df.columns = ["date", "value"]
        df["date"]      = df["date"].astype(str).str[:10]   # YYYY-MM-DD
        df["series_id"] = series_id.upper()
        df["fetched_at"] = datetime.now(timezone.utc).isoformat()
        df["source"]    = "FRED"
        df["is_stale"]  = 0

        rows = df[["series_id", "date", "value", "fetched_at", "source", "is_stale"]].to_dict(
            orient="records"
        )

        sql = """
            INSERT OR REPLACE INTO macro_data
              (series_id, date, value, fetched_at, source, is_stale)
            VALUES
              (:series_id, :date, :value, :fetched_at, :source, :is_stale)
        """
        with get_connection() as conn:
            conn.executemany(sql, rows)

        log.info("Wrote %d macro rows for %s", len(rows), series_id)
        return len(rows)

    def read_macro_data(
        self,
        series_id: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> Optional[pd.Series]:
        """
        Read macro rows for `series_id` from SQLite.
        Returns a Series with DatetimeIndex, or None if no rows exist.
        """
        sql = "SELECT date, value FROM macro_data WHERE series_id = ?"
        params: list = [series_id.upper()]

        if start_date:
            sql += " AND date >= ?"
            params.append(start_date)
        if end_date:
            sql += " AND date <= ?"
            params.append(end_date)

        sql += " ORDER BY date ASC"

        with get_connection() as conn:
            rows = conn.execute(sql, params).fetchall()

        if not rows:
            return None

        df = pd.DataFrame([dict(r) for r in rows])
        df["date"] = pd.to_datetime(df["date"])
        series = df.set_index("date")["value"]
        series.name = series_id.upper()
        return series

    def latest_macro_date(self, series_id: str) -> Optional[str]:
        """Return the most recent YYYY-MM-DD date stored for `series_id`, or None."""
        with get_connection() as conn:
            row = conn.execute(
                "SELECT MAX(date) AS latest FROM macro_data WHERE series_id = ?",
                (series_id.upper(),),
            ).fetchone()
        return row["latest"] if row and row["latest"] else None

    def mark_macro_stale(self, series_id: str) -> None:
        """Set is_stale=1 for every row belonging to `series_id`."""
        with get_connection() as conn:
            conn.execute(
                "UPDATE macro_data SET is_stale = 1 WHERE series_id = ?",
                (series_id.upper(),),
            )
        log.info("Marked all %s macro rows as stale", series_id)

    # ------------------------------------------------------------------
    # News data
    # ------------------------------------------------------------------

    def write_news_items(self, items: list[NewsItem]) -> int:
        """
        Upsert news items into the news_items table.
        INSERT OR IGNORE on URL (unique) avoids duplicating the same article.
        Returns the number of rows actually inserted.
        """
        if not items:
            return 0

        sql = """
            INSERT OR IGNORE INTO news_items
              (headline, source, url, published_at, fetched_at,
               classification, short_impact, medium_impact, long_impact, confidence)
            VALUES
              (:headline, :source, :url, :published_at, :fetched_at,
               :classification, :short_impact, :medium_impact, :long_impact, :confidence)
        """
        rows = [
            {
                "headline":       item.headline,
                "source":         item.source,
                "url":            item.url or "",
                "published_at":   item.published_at.isoformat() if item.published_at else None,
                "fetched_at":     item.fetched_at.isoformat(),
                "classification": item.classification,
                "short_impact":   item.short_impact,
                "medium_impact":  item.medium_impact,
                "long_impact":    item.long_impact,
                "confidence":     item.confidence,
            }
            for item in items
        ]

        with get_connection() as conn:
            conn.executemany(sql, rows)

        log.info("Wrote %d news items", len(rows))
        return len(rows)

    def read_news_items(
        self,
        limit: int = 50,
        since: Optional[str] = None,
        up_to: Optional[str] = None,
    ) -> list[NewsItem]:
        """
        Read recent news items from SQLite.
        since / up_to are ISO datetime strings (published_at boundary).
        Returns list of NewsItem ordered newest-first.
        """
        sql = "SELECT * FROM news_items WHERE 1=1"
        params: list = []

        if since:
            sql += " AND published_at >= ?"
            params.append(since)
        if up_to:
            sql += " AND published_at <= ?"
            params.append(up_to)

        sql += " ORDER BY published_at DESC LIMIT ?"
        params.append(limit)

        with get_connection() as conn:
            rows = conn.execute(sql, params).fetchall()

        fetched_at_default = datetime.now(timezone.utc)
        result: list[NewsItem] = []
        for r in rows:
            row = dict(r)
            pub = row.get("published_at")
            result.append(NewsItem(
                headline=row["headline"],
                source=row.get("source", ""),
                url=row.get("url", ""),
                published_at=datetime.fromisoformat(pub) if pub else None,
                fetched_at=datetime.fromisoformat(row["fetched_at"]) if row.get("fetched_at") else fetched_at_default,
                classification=row.get("classification", "neutral"),
                short_impact=row.get("short_impact", "unknown"),
                medium_impact=row.get("medium_impact", "unknown"),
                long_impact=row.get("long_impact", "unknown"),
                confidence=float(row.get("confidence", 0.0)),
            ))
        return result

    # ------------------------------------------------------------------
    # IV history (Schwab options — for IV percentile computation)
    # ------------------------------------------------------------------

    def write_iv_reading(self, ticker: str, atm_iv: float, underlying_price: float) -> None:
        """Append one ATM IV reading to iv_history for percentile tracking."""
        with get_connection() as conn:
            conn.execute(
                """INSERT INTO iv_history (ticker, atm_iv, underlying_price, fetched_at)
                   VALUES (?, ?, ?, ?)""",
                (ticker.upper(), atm_iv, underlying_price,
                 datetime.now(timezone.utc).isoformat()),
            )

    def read_iv_history(self, ticker: str, limit: int = 252) -> list[float]:
        """Return up to `limit` most recent ATM IV readings (newest-first) for percentile use."""
        with get_connection() as conn:
            rows = conn.execute(
                """SELECT atm_iv FROM iv_history
                   WHERE ticker = ?
                   ORDER BY fetched_at DESC
                   LIMIT ?""",
                (ticker.upper(), limit),
            ).fetchall()
        return [r["atm_iv"] for r in rows]

    # ------------------------------------------------------------------
    # Data quality log
    # ------------------------------------------------------------------

    def log_quality(
        self, module: str, metric_name: str, status: str, message: str = ""
    ) -> None:
        """Append a structured row to the data_quality_log table."""
        sql = """
            INSERT INTO data_quality_log (logged_at, module, metric_name, status, message)
            VALUES (?, ?, ?, ?, ?)
        """
        with get_connection() as conn:
            conn.execute(sql, (
                datetime.now(timezone.utc).isoformat(),
                module, metric_name, status, message,
            ))
