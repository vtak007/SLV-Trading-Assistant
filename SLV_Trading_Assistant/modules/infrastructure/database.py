# Rev 1
"""SQLite connection management and schema initialisation."""
import sqlite3
from contextlib import contextmanager
from typing import Generator

from config.settings import DB_PATH
from modules.infrastructure.exceptions import DatabaseError
from modules.infrastructure.logger import get_logger

log = get_logger("database")

_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS price_data (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    ticker      TEXT    NOT NULL,
    date        TEXT    NOT NULL,
    open        REAL,
    high        REAL,
    low         REAL,
    close       REAL,
    volume      REAL,
    adj_close   REAL,
    fetched_at  TEXT    NOT NULL,
    is_stale    INTEGER NOT NULL DEFAULT 0,
    UNIQUE(ticker, date)
);

CREATE TABLE IF NOT EXISTS macro_data (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    series_id   TEXT    NOT NULL,
    date        TEXT    NOT NULL,
    value       REAL,
    fetched_at  TEXT    NOT NULL,
    source      TEXT    NOT NULL DEFAULT 'FRED',
    is_stale    INTEGER NOT NULL DEFAULT 0,
    UNIQUE(series_id, date)
);

CREATE TABLE IF NOT EXISTS news_items (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    headline        TEXT    NOT NULL,
    source          TEXT,
    url             TEXT    UNIQUE,
    published_at    TEXT,
    fetched_at      TEXT    NOT NULL,
    classification  TEXT,
    short_impact    TEXT,
    medium_impact   TEXT,
    long_impact     TEXT,
    confidence      REAL
);

CREATE TABLE IF NOT EXISTS economic_events (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    event_name      TEXT    NOT NULL,
    scheduled_at    TEXT    NOT NULL,
    actual_value    REAL,
    forecast_value  REAL,
    prior_value     REAL,
    impact_level    TEXT
);

CREATE TABLE IF NOT EXISTS signals (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    generated_at    TEXT    NOT NULL,
    trading_style   TEXT    NOT NULL,
    action          TEXT    NOT NULL,
    confidence      REAL,
    risk_score      REAL,
    raw_json        TEXT
);

CREATE TABLE IF NOT EXISTS data_quality_log (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    logged_at   TEXT    NOT NULL,
    module      TEXT    NOT NULL,
    metric_name TEXT    NOT NULL,
    status      TEXT    NOT NULL,
    message     TEXT
);

CREATE TABLE IF NOT EXISTS iv_history (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    ticker           TEXT    NOT NULL,
    atm_iv           REAL    NOT NULL,
    underlying_price REAL,
    fetched_at       TEXT    NOT NULL
);
"""


def initialize_database() -> None:
    """Create all tables if they don't already exist."""
    try:
        with get_connection() as conn:
            conn.executescript(_SCHEMA_SQL)
        log.info("Database ready at %s", DB_PATH)
    except sqlite3.Error as exc:
        raise DatabaseError(f"Schema creation failed: {exc}") from exc


@contextmanager
def get_connection() -> Generator[sqlite3.Connection, None, None]:
    """
    Yield a WAL-mode SQLite connection with row_factory set.
    Commits on clean exit, rolls back on exception.
    """
    conn: sqlite3.Connection | None = None
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA foreign_keys=ON;")
        yield conn
        conn.commit()
    except sqlite3.Error as exc:
        if conn:
            conn.rollback()
        raise DatabaseError(f"Database operation failed: {exc}") from exc
    finally:
        if conn:
            conn.close()
