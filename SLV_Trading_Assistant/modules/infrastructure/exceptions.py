# Rev 1
"""Custom exception hierarchy. Import from here at all external boundaries."""


class SLVBaseError(Exception):
    """Root exception for all SLV Trading Assistant errors."""


class DataFetchError(SLVBaseError):
    """Raised when a data fetch from an external source fails."""


class StaleDataError(SLVBaseError):
    """Raised when cached data exceeds its freshness threshold and no live fallback exists."""


class ValidationError(SLVBaseError):
    """Raised when data fails a shape, type, or range check."""


class DatabaseError(SLVBaseError):
    """Raised on SQLite read/write failures."""


class CacheError(SLVBaseError):
    """Raised on local cache read/write failures."""


class ConfigurationError(SLVBaseError):
    """Raised when required configuration (e.g. API key) is absent or invalid."""
