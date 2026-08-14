class BaalebosError(Exception):
    """Base class for all errors raised by this SDK. Catch this to catch anything we raise."""
    pass


class BaalebosConfigError(BaalebosError):
    """Raised when required configuration (api_url / api_key) is missing."""
    pass


class BaalebosConnectionError(BaalebosError):
    """Raised when the request never reached the gateway at all
    (DNS failure, connection refused, timeout)."""
    pass


class BaalebosAPIError(BaalebosError):
    """Raised when the gateway responded, but with an error status
    (401 Unauthorized, 429 rate-limited, 5xx server error, etc.)."""

    def __init__(self, message: str, status_code: int = None):
        super().__init__(message)
        self.status_code = status_code


class BaalebosAuthError(BaalebosAPIError):
    """Raised specifically for 401 Unauthorized - a bad or missing x-api-key."""
    pass