# Rev 1

PRIMARY_TICKER: str = "SLV"

# ^VIX is unreliable via yfinance; VIXY (ProShares VIX Short-Term Futures ETF) used instead
PRICE_TICKERS: list[str] = ["SLV", "GLD", "VIXY", "TIP", "UUP", "GDX"]

FRED_SERIES: dict[str, str] = {
    "DGS10":    "10-Year Treasury Constant Maturity Rate",
    "FEDFUNDS": "Effective Federal Funds Rate",
    "CPIAUCSL": "CPI for All Urban Consumers",
    "PPIFIS":   "PPI by Commodity: Final Demand",
    "UNRATE":   "Unemployment Rate",
    "PAYEMS":   "All Employees, Total Nonfarm",
    "T10YIE":   "10-Year Breakeven Inflation Rate",
    "DTWEXBGS": "Nominal Broad U.S. Dollar Index",
}

NEWS_RSS_FEEDS: dict[str, str] = {
    # "kitco" removed: https://www.kitco.com/rss/ is an index page, not a feed (served malformed XML)
    # "reuters_business" removed: feeds.reuters.com DNS no longer resolves (retired ~2020)
    "marketwatch":          "https://feeds.marketwatch.com/marketwatch/marketpulse/",
    "fed_reserve":          "https://www.federalreserve.gov/feeds/press_all.xml",
    "fxstreet_commodities": "https://www.fxstreet.com/rss/news",
}
