"""baalebos-ai: a zero-setup client for the Baalebos multi-provider LLM gateway."""

from .client import AsyncBaalebosAI, BaalebosAI, check_status
from .exceptions import (
    BaalebosAPIError,
    BaalebosAuthError,
    BaalebosConfigError,
    BaalebosConnectionError,
    BaalebosError,
    BaalebosRateLimitError,
    BaalebosRequestError,
    BaalebosStructuredOutputError,
    BaalebosUnavailableError,
)

__version__ = "1.1.0"

__all__ = [
    "BaalebosAI",
    "AsyncBaalebosAI",
    "check_status",
    "BaalebosError",
    "BaalebosConfigError",
    "BaalebosConnectionError",
    "BaalebosAPIError",
    "BaalebosAuthError",
    "BaalebosRateLimitError",
    "BaalebosRequestError",
    "BaalebosUnavailableError",
    "BaalebosStructuredOutputError",
    "__version__",
]
