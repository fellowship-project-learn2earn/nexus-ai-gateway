"""
Zero-friction auth: on first use, the CLI/SDK requests its OWN unique
key from the gateway's signup endpoint and saves it locally. No shared
secret is ever embedded in this package's source code -- each install
gets its own individually-tracked, individually-rate-limited key.

This protects the underlying free-tier provider accounts (Groq,
Cerebras, etc.) from being exhausted by a single leaked shared key,
since usage is now attributable and cappable per key, not global.
"""

import json
import os
from pathlib import Path

import requests

CONFIG_DIR = Path.home() / ".config" / "baalebos_ai"
CREDENTIALS_FILE = CONFIG_DIR / "credentials.json"

DEFAULT_SIGNUP_URL = "https://gateway.baalebo.xyz/webhook/baalebos-ai-signup"


class AuthError(Exception):
    """Raised when signup or credential loading fails."""


def _load_saved_key() -> str | None:
    if not CREDENTIALS_FILE.exists():
        return None
    try:
        data = json.loads(CREDENTIALS_FILE.read_text())
        return data.get("api_key")
    except (json.JSONDecodeError, OSError):
        return None


def _save_key(api_key: str) -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    CREDENTIALS_FILE.write_text(json.dumps({"api_key": api_key}))
    try:
        os.chmod(CREDENTIALS_FILE, 0o600)
    except OSError:
        pass


def _request_new_key(signup_url: str) -> str:
    try:
        response = requests.post(signup_url, timeout=15)
        response.raise_for_status()
    except requests.RequestException as exc:
        raise AuthError(f"Could not reach signup endpoint: {exc}") from exc

    data = response.json()
    api_key = data.get("api_key")
    if not api_key:
        raise AuthError(f"Signup endpoint did not return an api_key: {data}")
    return api_key


def get_api_key(signup_url: str = None) -> str:
    """
    Returns a usable API key, in priority order:
    1. BAALEBOS_API_KEY environment variable (team members / manual override)
    2. A previously auto-registered key saved locally
    3. A freshly auto-registered key (first run for this install)
    """
    env_key = os.getenv("BAALEBOS_API_KEY")
    if env_key:
        return env_key

    saved = _load_saved_key()
    if saved:
        return saved

    new_key = _request_new_key(signup_url or DEFAULT_SIGNUP_URL)
    _save_key(new_key)
    return new_key
