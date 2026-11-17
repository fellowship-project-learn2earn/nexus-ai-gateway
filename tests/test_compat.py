"""
Pins the public API that baalebos-ai 1.0.x shipped on PyPI. If one of these fails, a release would break
existing users' code: fix the SDK, don't edit the test.
"""
import inspect

import pytest
import requests
from conftest import FakeResponse, Recorder

import baalebos_ai
from baalebos_ai import (
    AsyncBaalebosAI,
    BaalebosAI,
    BaalebosAPIError,
    BaalebosAuthError,
    BaalebosConfigError,
    BaalebosConnectionError,
    BaalebosError,
)
from baalebos_ai import exceptions as exc_module

API = "https://gw.test/webhook/baalebos-ai"

PUBLISHED_NAMES = [
    "BaalebosAI", "BaalebosError", "BaalebosConfigError", "BaalebosConnectionError",
    "BaalebosAPIError", "BaalebosAuthError",
]


@pytest.mark.parametrize("name", PUBLISHED_NAMES)
def test_published_names_are_still_exported(name):
    assert name in baalebos_ai.__all__
    assert hasattr(baalebos_ai, name)
    assert hasattr(exc_module, name) or name == "BaalebosAI"


def test_the_async_client_the_published_readme_promises_exists():
    assert inspect.iscoroutinefunction(AsyncBaalebosAI.chat)


def test_published_exception_hierarchy_is_unchanged():
    assert issubclass(BaalebosConfigError, BaalebosError)
    assert issubclass(BaalebosConnectionError, BaalebosError)
    assert issubclass(BaalebosAPIError, BaalebosError)
    assert issubclass(BaalebosAuthError, BaalebosAPIError)


def test_new_errors_are_caught_by_handlers_written_against_1_0_x():
    """`except BaalebosAPIError` used to catch a 429 or a 503; it must still."""
    for name in ("BaalebosRateLimitError", "BaalebosRequestError", "BaalebosUnavailableError"):
        assert issubclass(getattr(exc_module, name), BaalebosAPIError)


def test_api_error_keeps_its_constructor_and_status_code():
    e = BaalebosAPIError("boom", status_code=500)
    assert e.status_code == 500 and str(e) == "boom"
    assert BaalebosAPIError("no status").status_code is None
    assert BaalebosAuthError("x", status_code=401).status_code == 401


@pytest.mark.parametrize("cls", [BaalebosAI, AsyncBaalebosAI])
def test_constructor_and_chat_keep_their_positional_order(cls):
    ctor = list(inspect.signature(cls.__init__).parameters)
    assert ctor[:3] == ["self", "api_url", "api_key"]
    chat = inspect.signature(cls.chat).parameters
    assert list(chat)[:4] == ["self", "prompt", "mode", "temperature"]
    assert chat["mode"].default == "auto" and chat["temperature"].default == 0.7
    # everything added since is keyword-only, so it can't shift an existing positional argument
    assert chat["model"].kind is inspect.Parameter.KEYWORD_ONLY
    assert chat["models"].kind is inspect.Parameter.KEYWORD_ONLY


def test_positional_call_style_from_1_0_x_still_works(monkeypatch):
    rec = Recorder([FakeResponse(200, {"output": "ok"})])
    monkeypatch.setattr(requests, "post", rec)
    assert BaalebosAI(API, "key").chat("hi", "fast", 0.2) == "ok"
    sent = rec.calls[0][1]
    assert sent["json"] == {"message": "hi", "mode": "fast", "temperature": 0.2}
    assert sent["headers"]["x-api-key"] == "key"


def test_attributes_1_0_x_exposed(monkeypatch):
    c = BaalebosAI(api_url=API, api_key="k")
    assert c.api_url == API and c.api_key == "k"


def test_http_errors_still_surface_as_BaalebosAPIError_with_a_status(monkeypatch):
    monkeypatch.setattr(requests, "post", Recorder([FakeResponse(500, {})]))
    with pytest.raises(BaalebosAPIError) as e:
        BaalebosAI(API, "k", max_retries=0).chat("x")
    assert e.value.status_code == 500


def test_401_with_a_supplied_key_is_still_BaalebosAuthError_401(monkeypatch):
    monkeypatch.setattr(requests, "post", Recorder([FakeResponse(401, {})]))
    with pytest.raises(BaalebosAuthError) as e:
        BaalebosAI(API, "bad").chat("x")
    assert e.value.status_code == 401


def test_a_timeout_is_still_BaalebosConnectionError(monkeypatch):
    monkeypatch.setattr(requests, "post", Recorder([requests.Timeout("slow")]))
    with pytest.raises(BaalebosConnectionError):
        BaalebosAI(API, "k").chat("x")


def test_the_cli_entry_point_is_still_ai_main():
    from baalebos_ai.cli import main
    assert callable(main)
