import os
import stat
import sys

import pytest
import requests
from conftest import FakeResponse, Recorder

from baalebos_ai import auth
from baalebos_ai.client import derive_url
from baalebos_ai.exceptions import (
    BaalebosAuthError,
    BaalebosConnectionError,
    BaalebosRateLimitError,
    BaalebosUnavailableError,
)


def test_env_key_wins_and_never_touches_network(monkeypatch):
    monkeypatch.setenv("BAALEBOS_API_KEY", "from-env")
    rec = Recorder([FakeResponse(200, {"api_key": "x"})])
    monkeypatch.setattr(requests, "post", rec)
    assert auth.get_api_key() == "from-env"
    assert rec.calls == []


def test_registers_once_then_reuses_saved_key(monkeypatch):
    rec = Recorder([FakeResponse(200, {"api_key": "fresh"})])
    monkeypatch.setattr(requests, "post", rec)
    assert auth.get_api_key() == "fresh"
    assert auth.get_api_key() == "fresh"
    assert len(rec.calls) == 1
    assert auth.load_saved_key() == "fresh"


@pytest.mark.skipif(sys.platform.startswith("win"), reason="POSIX permissions")
def test_credentials_file_is_owner_only():
    auth.save_key("secret")
    assert stat.S_IMODE(os.stat(auth.credentials_file()).st_mode) == 0o600


def test_forget_is_idempotent():
    auth.save_key("k")
    auth.forget_saved_key()
    auth.forget_saved_key()
    assert auth.load_saved_key() is None


def test_corrupt_credentials_file_is_ignored():
    auth.credentials_file().parent.mkdir(parents=True)
    auth.credentials_file().write_text("{not json")
    assert auth.load_saved_key() is None


@pytest.mark.parametrize(
    "resp, exc",
    [
        (FakeResponse(429, {"error": "too_many_signups"}), BaalebosRateLimitError),
        (FakeResponse(404, text="nope"), BaalebosUnavailableError),
        (FakeResponse(503), BaalebosUnavailableError),
        (FakeResponse(200, {"nokey": True}), BaalebosAuthError),
        (FakeResponse(200, text="<html>"), BaalebosAuthError),
        (FakeResponse(500), BaalebosAuthError),
    ],
)
def test_register_failure_modes(monkeypatch, resp, exc):
    monkeypatch.setattr(requests, "post", Recorder([resp]))
    with pytest.raises(exc):
        auth.register("https://example.test/signup")


def test_signup_errors_carry_the_http_status(monkeypatch):
    monkeypatch.setattr(requests, "post", Recorder([FakeResponse(429, {})]))
    with pytest.raises(BaalebosRateLimitError) as e:
        auth.register("https://example.test/signup")
    assert e.value.status_code == 429


def test_register_network_error(monkeypatch):
    monkeypatch.setattr(requests, "post", Recorder([requests.ConnectionError("boom")]))
    with pytest.raises(BaalebosConnectionError, match="Could not reach"):
        auth.register("https://example.test/signup")


def test_failed_registration_saves_nothing(monkeypatch):
    monkeypatch.setattr(requests, "post", Recorder([FakeResponse(503)]))
    with pytest.raises(BaalebosUnavailableError):
        auth.get_api_key("https://example.test/signup")
    assert auth.load_saved_key() is None


def test_derive_url_supports_self_hosting():
    assert derive_url("https://me.dev/webhook/baalebos-ai", "signup") == "https://me.dev/webhook/baalebos-ai-signup"
    assert derive_url("https://me.dev/webhook/baalebos-ai/", "health") == "https://me.dev/webhook/baalebos-ai-health"
