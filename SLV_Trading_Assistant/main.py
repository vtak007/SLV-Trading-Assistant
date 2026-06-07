# Rev 6  (Schwab price + options IV integration)
"""
SLV Trading Assistant - CLI entry point.
Session 5: full argparse CLI — all planned flags implemented.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import webbrowser
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from config.settings import DB_PATH
from config.trading_styles import TradingStyle, DEFAULT_STYLE
from modules.infrastructure.database import get_connection, initialize_database
from modules.infrastructure.logger import get_logger
from modules.collection.price_fetcher import PriceFetcher
from modules.collection.intraday_fetcher import IntradayFetcher
from modules.collection.data_store import DataStore
from modules.collection.schwab_options_fetcher import SchwabOptionsFetcher
from modules.analysis.technical.technical_analyzer import TechnicalAnalyzer
from modules.analysis.macro.macro_analyzer import MacroAnalyzer
from modules.analysis.news.news_analyzer import NewsAnalyzer
from modules.engines.signal_engine import SignalEngine
from modules.engines.risk_engine import RiskEngine
from modules.reporting.report_engine import ReportEngine

log = get_logger("main")

_SEP = "=" * 62


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="SLV Trading Assistant — signal generation and research report"
    )
    p.add_argument(
        "--style",
        choices=["day", "swing", "position", "long_term"],
        default=DEFAULT_STYLE.value,
        help="Trading style profile (default: %(default)s)",
    )
    p.add_argument(
        "--output",
        choices=["text", "html"],
        default="text",
        help="Report output format (default: text)",
    )
    p.add_argument(
        "--refresh",
        action="store_true",
        help="Force re-fetch all data, ignoring local cache",
    )
    p.add_argument(
        "--collect-only",
        action="store_true",
        help="Fetch and store data without generating a report",
    )
    p.add_argument(
        "--last-signal",
        action="store_true",
        help="Display the most recent stored signal and exit",
    )
    p.add_argument(
        "--status",
        action="store_true",
        help="Show data freshness status for all sources and exit",
    )
    p.add_argument(
        "--open-browser",
        action="store_true",
        help="Auto-open the HTML report in the default browser after generation",
    )
    return p.parse_args()


def _prompt_int(prompt: str, lo: int, hi: int) -> int:
    """Re-prompt until the user enters an integer in [lo, hi]."""
    while True:
        try:
            val = int(input(f"{prompt} [{lo}-{hi}]: ").strip())
            if lo <= val <= hi:
                return val
        except (ValueError, EOFError):
            pass
        print(f"  Please enter a number between {lo} and {hi}.")


def _show_menu() -> argparse.Namespace:
    """Interactive two-step menu shown when main.py is run with no arguments."""
    _STYLE_ROWS = [
        ("day",       "Day",       "Intraday / very short holds",  "Tech 70%  Macro 15%  News 15%"),
        ("swing",     "Swing",     "2-10 day holds",               "Tech 50%  Macro 30%  News 20%"),
        ("position",  "Position",  "Weeks to a few months",        "Tech 30%  Macro 50%  News 20%"),
        ("long_term", "Long Term", "Months to years",              "Tech 10%  Macro 65%  News 25%"),
    ]

    # (label, needs_style, output, refresh, collect_only, open_browser, last_signal, status)
    _COMMANDS = [
        ("Generate text report",                    True,  "text", False, False, False, False, False),
        ("Generate HTML report",                    True,  "html", False, False, False, False, False),
        ("Generate HTML report + open in browser",  True,  "html", False, False, True,  False, False),
        ("Force refresh + generate text report",    True,  "text", True,  False, False, False, False),
        ("Force refresh + generate HTML report + open in browser", True, "html", True, False, True, False, False),
        ("Collect data only  (no report)",          False, "text", False, True,  False, False, False),
        ("View last signal",                        False, "text", False, False, False, True,  False),
        ("View data status",                        False, "text", False, False, False, False, True),
        ("Exit",                                    False, None,   False, False, False, False, False),
    ]

    print()
    print(_SEP)
    print("  SLV Trading Assistant")
    print(_SEP)
    print()
    print("  Commands:")
    print()
    for i, (label, *_rest) in enumerate(_COMMANDS, 1):
        print(f"    [{i}] {label}")
    print()

    cmd_idx = _prompt_int("  Enter choice", 1, len(_COMMANDS)) - 1
    label, needs_style, output, refresh, collect_only, open_browser, last_signal, status = _COMMANDS[cmd_idx]

    if output is None:
        print()
        sys.exit(0)

    style = DEFAULT_STYLE.value
    if needs_style:
        print()
        print("  Trading style:")
        print()
        for i, (key, name, desc, weights) in enumerate(_STYLE_ROWS, 1):
            marker = "  (default)" if key == DEFAULT_STYLE.value else ""
            print(f"    [{i}] {name:<10}  {desc:<34}  {weights}{marker}")
        print()
        raw = input("  Enter choice [1-4] or press Enter for Swing: ").strip()
        if raw:
            try:
                sidx = int(raw) - 1
                if 0 <= sidx < len(_STYLE_ROWS):
                    style = _STYLE_ROWS[sidx][0]
            except ValueError:
                pass
        print()

    return argparse.Namespace(
        style        = style,
        output       = output,
        refresh      = refresh,
        collect_only = collect_only,
        open_browser = open_browser,
        last_signal  = last_signal,
        status       = status,
    )


def main() -> None:
    args = _show_menu() if len(sys.argv) == 1 else parse_args()

    initialize_database()

    # --- Informational commands (no data collection needed) ---
    if args.last_signal:
        _cmd_last_signal()
        return

    if args.status:
        _cmd_status()
        return

    style = TradingStyle(args.style)
    now   = datetime.now(timezone.utc)

    # --- Data collection ---
    fetcher    = PriceFetcher()
    price_data = fetcher.fetch_price_data("SLV", force_refresh=args.refresh)

    store = DataStore()
    store.write_price_data(price_data)

    macro_analyzer = MacroAnalyzer()
    macro_result   = macro_analyzer.analyze(force_refresh=args.refresh)

    news_analyzer = NewsAnalyzer()
    news_result   = news_analyzer.analyze(force_refresh=args.refresh)
    store.write_news_items(news_result.items)

    options_fetcher = SchwabOptionsFetcher()
    options_data    = options_fetcher.fetch_options_data("SLV")

    if args.collect_only:
        print("[OK] Data collection complete. No report generated (--collect-only).")
        return

    # --- Technical data source: 5-min intraday for Day style, daily for all others ---
    tech_price_data = price_data
    if style == TradingStyle.DAY:
        try:
            intraday_fetcher = IntradayFetcher()
            tech_price_data  = intraday_fetcher.fetch("SLV")
            log.info("Day style: using intraday (5-min) bars for technical analysis")
        except Exception as exc:
            log.warning(
                "Intraday fetch failed (%s) — falling back to daily bars for tech analysis", exc
            )

    # --- Analysis ---
    tech_analyzer = TechnicalAnalyzer()
    tech_result   = tech_analyzer.analyze(tech_price_data, analysis_date=now, options_data=options_data)

    # --- Engines ---
    signal_engine = SignalEngine()
    signal_result = signal_engine.generate(
        tech_price_data, tech_result, macro_result, news_result,
        style, analysis_datetime=now,
    )

    risk_engine = RiskEngine()
    risk_result = risk_engine.calculate(
        tech_result, news_result, tech_price_data, signal_result, as_of=now
    )

    # --- Report ---
    report_engine = ReportEngine()
    content, saved_path = report_engine.generate_report(
        price_data    = price_data,
        tech_result   = tech_result,
        macro_result  = macro_result,
        news_result   = news_result,
        signal_result = signal_result,
        risk_result   = risk_result,
        trading_style = style,
        output_format = args.output,
        generated_at  = now,
    )

    if args.output == "text":
        print(content)
    else:
        print(f"[OK] HTML report saved to: {saved_path}")
        print(f"     Open in browser: file:///{saved_path.as_posix()}")

    _print_summary(signal_result, saved_path, args.output)

    # Auto-open browser if requested
    if args.open_browser and args.output == "html":
        try:
            os.startfile(str(saved_path))
        except AttributeError:
            webbrowser.open(saved_path.as_uri())
        print("[OK] Report opened in default browser.")
    elif args.open_browser and args.output != "html":
        print("[NOTE] --open-browser has no effect with --output text.")


# ---------------------------------------------------------------------------
# Informational commands
# ---------------------------------------------------------------------------

def _cmd_last_signal() -> None:
    """Print the most recently stored signal from the database."""
    print(_SEP)
    print("  Last Stored Signal")
    print(_SEP)

    try:
        with get_connection() as conn:
            row = conn.execute(
                """SELECT generated_at, trading_style, action, confidence,
                          risk_score, raw_json
                   FROM signals
                   ORDER BY generated_at DESC
                   LIMIT 1"""
            ).fetchone()
    except Exception as exc:
        print(f"  [ERROR] Could not read signals table: {exc}")
        return

    if row is None:
        print("  No signals stored yet. Run main.py to generate the first signal.")
        return

    raw = {}
    try:
        raw = json.loads(row["raw_json"] or "{}")
    except (json.JSONDecodeError, TypeError):
        pass

    print(f"  Generated   : {row['generated_at']}")
    print(f"  Style       : {row['trading_style'].upper()}")
    print(f"  Action      : {row['action']}")
    print(f"  Confidence  : {row['confidence']:.0f}%")
    print(f"  Risk Score  : {row['risk_score']:.0f}/100")
    if raw.get("regime"):
        print(f"  Regime      : {raw['regime']}")
    if raw.get("entry_zone") and raw["entry_zone"] != [0.0, 0.0]:
        lo, hi = raw["entry_zone"]
        print(f"  Entry Zone  : ${lo:.2f} -- ${hi:.2f}")
    if raw.get("stop_loss") and raw["stop_loss"] != 0.0:
        print(f"  Stop Loss   : ${raw['stop_loss']:.2f}")
    if raw.get("targets"):
        tgts = "  ".join(f"${t:.2f}" for t in raw["targets"])
        print(f"  Targets     : {tgts}")
    if raw.get("explanation"):
        print()
        for line in raw["explanation"].splitlines():
            print(f"  {line}")
    print(_SEP)


def _cmd_status() -> None:
    """Print data freshness status for all stored sources."""
    print(_SEP)
    print("  SLV Trading Assistant — Data Status")
    print(_SEP)

    try:
        with get_connection() as conn:
            # Price
            price_row = conn.execute(
                """SELECT COUNT(*) as cnt, MAX(date) as latest,
                          MAX(fetched_at) as fetched, MAX(is_stale) as stale
                   FROM price_data WHERE ticker = 'SLV'"""
            ).fetchone()

            # Macro: per-series latest
            macro_rows = conn.execute(
                """SELECT series_id, COUNT(*) as cnt, MAX(date) as latest,
                          MAX(fetched_at) as fetched
                   FROM macro_data GROUP BY series_id ORDER BY series_id"""
            ).fetchall()

            # News
            news_row = conn.execute(
                """SELECT COUNT(*) as cnt, MAX(fetched_at) as fetched,
                          MAX(published_at) as latest_pub
                   FROM news_items"""
            ).fetchone()

            # Last signal
            sig_row = conn.execute(
                """SELECT generated_at, trading_style, action, confidence
                   FROM signals ORDER BY generated_at DESC LIMIT 1"""
            ).fetchone()

    except Exception as exc:
        print(f"  [ERROR] Database read failed: {exc}")
        return

    # Price
    p_stale  = bool(price_row["stale"]) if price_row else False
    p_status = "STALE" if p_stale else ("FRESH" if price_row and price_row["cnt"] else "NO DATA")
    p_rows   = price_row["cnt"] if price_row else 0
    p_latest = price_row["latest"] if price_row else "N/A"
    print(f"\n  Price (SLV)")
    print(f"    Status  : {p_status}")
    print(f"    Rows    : {p_rows}")
    print(f"    Latest  : {p_latest}")

    # Macro
    print(f"\n  Macro (FRED) — {len(macro_rows)} series")
    if macro_rows:
        print(f"  {'Series':<12} {'Rows':>5}  Latest")
        print(f"  {'-'*12} {'-'*5}  {'-'*12}")
        for r in macro_rows:
            print(f"  {r['series_id']:<12} {r['cnt']:>5}  {r['latest']}")
    else:
        print("  No macro data stored yet")

    # News
    n_cnt    = news_row["cnt"] if news_row else 0
    n_fetch  = (news_row["fetched"] or "N/A")[:16] if news_row else "N/A"
    n_status = "FRESH" if n_cnt > 0 else "NO DATA"
    print(f"\n  News")
    print(f"    Status  : {n_status}")
    print(f"    Items   : {n_cnt}")
    print(f"    Fetched : {n_fetch}")

    # Last signal
    print(f"\n  Last Signal")
    if sig_row:
        print(f"    Generated  : {sig_row['generated_at'][:16]}")
        print(f"    Style      : {sig_row['trading_style'].upper()}")
        print(f"    Action     : {sig_row['action']}")
        print(f"    Confidence : {sig_row['confidence']:.0f}%")
    else:
        print("    No signals stored yet")

    print(f"\n{_SEP}")


def _print_summary(signal_result, saved_path: Path, fmt: str) -> None:
    print()
    print(_SEP)
    print(f"  SIGNAL  : {signal_result.action}")
    print(f"  Confidence : {signal_result.confidence:.0f}%  |  Risk: {signal_result.risk_score:.0f}/100")
    print(f"  Regime  : {signal_result.regime_label}")
    if signal_result.no_trade_reason:
        print(f"  NO-TRADE: {signal_result.no_trade_reason}")
    if fmt == "html":
        print(f"  Report  : {saved_path}")
    print(_SEP)


if __name__ == "__main__":
    main()
