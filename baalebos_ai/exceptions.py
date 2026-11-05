"""
Exception hierarchy.

The first five classes are the SDK's established public API (1.0.x) and are unchanged. The newer
ones subclass them, so existing handlers keep working: an `except BaalebosAPIError` that used to
catch a 429 or a 503 still does.

    BaalebosError
    ├── BaalebosConfigError          bad configuration (e.g. a malformed URL)
    ├── BaalebosConnectionError      the request never reached the gateway (DNS, refused, timeout)
    ├── BaalebosStructuredOutputError  chat_json() could not get a valid JSON object
    └── BaalebosAPIError             the gateway answered with an error status (.status_code)
        ├── BaalebosAuthError          401: bad or missing key
        ├── BaalebosRateLimitError     429: a daily limit was reached
        ├── BaalebosRequestError       400/413/422: the request itself was invalid
        └── BaalebosUnavailableError   404/5xx: the gateway is down or every provider failed
"""


class BaalebosError(Exception):
    """Base class for all errors raised by this SDK. Catch this to catch anything we raise."""


class BaalebosConfigError(BaalebosError):
    """Raised when configuration (api_url / api_key) is invalid."""


class BaalebosConnectionError(BaalebosError):
    """Raised when the request never reached the gateway at all
    (DNS failure, connection refused, timeout)."""


class BaalebosAPIError(BaalebosError):
    """Raised when the gateway responded, but with an error status
    (401 Unauthorized, 429 rate-limited, 5xx server error, etc.)."""

    def __init__(self, message: str, status_code: int = None):
        super().__init__(message)
        self.status_code = status_code


class BaalebosAuthError(BaalebosAPIError):
    """Raised for 401 Unauthorized, or when a key could not be obtained."""


class BaalebosRateLimitError(BaalebosAPIError):
    """Raised for 429: your key's daily limit, or the shared public cap, is reached."""


class BaalebosRequestError(BaalebosAPIError):
    """Raised for 400/413/422: empty or oversized message, unknown model, ..."""


class BaalebosUnavailableError(BaalebosAPIError):
    """Raised for 404/5xx: the gateway is down, mis-addressed, or every provider failed."""


class BaalebosStructuredOutputError(BaalebosError):
    """Raised when a JSON object can't be extracted from the model's answer."""


def describe_network_error(exc: Exception) -> str:
    """A short, human reason for a requests/httpx exception (the raw chain is very noisy)."""
    name = type(exc).__name__
    if "Timeout" in name:
        return "the request timed out"
    if "Connect" in name or "SSL" in name:
        return "could not connect (is the URL right and the service up?)"
    return str(exc)[:120]
