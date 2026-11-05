"""
Zero-setup authentication.

No secret is embedded in this package. On first use the SDK asks the gateway
for its own key and stores it locally, so every install has an individual,
individually rate-limited identity. Order of precedence:

1. an explicit api_key argument or the BAALEBOS_API_KEY environment variable
2. a key saved by a previous run
3. a freshly registered key (first run on this machine)
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Optional

import requests

from .exceptions import (
    BaalebosAuthError,
    BaalebosConnectionError,
    BaalebosRateLimitError,
    BaalebosUnavailableError,
    describe_network_error,
)

DEFAULT_API_URL = "https://gateway.baalebo.xyz/webhook/baalebos-ai"
DEFAULT_SIGNUP_URL = DEFAULT_API_URL + "-signup"


def config_dir() -> Path:
    override = os.getenv("BAALEBOS_CONFIG_DIR")
    return Path(override) if override else Path.home() / ".config" / "baalebos_ai"


def credentials_file() -> Path:
    return config_dir() / "credentials.json"


def load_saved_key() -> Optional[str]:
    path = credentials_file()
    if not path.exists():
        return None
    try:
        key = json.loads(path.read_text()).get("api_key")
    except (ValueError, OSError):
        return None
    return key or None


def save_key(api_key: str) -> None:
    path = credentials_file()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"api_key": api_key}))
    try:
        os.chmod(path, 0o600)  # holds a real credential: owner-only
    except OSError:
        pass  # best effort on platforms with different permission models


def forget_saved_key() -> None:
    try:
        credentials_file().unlink()
    except FileNotFoundError:
        pass


def register(signup_url: str = DEFAULT_SIGNUP_URL, timeout: float = 15.0) -> str:
    """Ask the gateway for a new key and return it (does not save it)."""
    try:
        resp = requests.post(signup_url, timeout=timeout)
    except requests.RequestException as exc:
        raise BaalebosConnectionError(
            f"Could not reach the signup endpoint ({signup_url}): {describe_network_error(exc)}"
        ) from exc
    return key_from_signup_response(resp.status_code, resp.text, _json_or_none(resp))


def _json_or_none(resp):
    try:
        return resp.json()
    except ValueError:
        return None


def key_from_signup_response(status: int, text: str, data) -> str:
    """Shared by the sync and async clients: turn a signup response into a key or a typed error."""
    if status == 429:
        raise BaalebosRateLimitError(
            "Too many keys have been requested from your network today. Try again tomorrow, "
            "or set BAALEBOS_API_KEY if you already have a key.",
            status_code=429,
        )
    if status in (404, 502, 503, 504):
        raise BaalebosUnavailableError(
            f"The signup endpoint is unavailable (HTTP {status}). The gateway may be down, "
            f"or BAALEBOS_API_URL may be wrong.",
            status_code=status,
        )
    if status != 200:
        raise BaalebosAuthError(f"Signup failed with HTTP {status}.", status_code=status)

    key = data.get("api_key") if isinstance(data, dict) else None
    if not key:
        raise BaalebosAuthError("The signup endpoint did not return an api_key.")
    return key


def get_api_key(signup_url: str = DEFAULT_SIGNUP_URL) -> str:
    """Resolve a key: env var -> saved key -> register a new one (and save it)."""
    env_key = os.getenv("BAALEBOS_API_KEY")
    if env_key:
        return env_key
    saved = load_saved_key()
    if saved:
        return saved
    key = register(signup_url)
    save_key(key)
    return key
