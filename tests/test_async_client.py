import asyncio

import httpx
import pytest
import requests
from conftest import FakeResponse, Recorder

from baalebos_ai import (
    AsyncBaalebosAI,
    BaalebosAuthError,
    BaalebosConnectionError,
    BaalebosRateLimitError,
    BaalebosStructuredOutputError,
    BaalebosUnavailableError,
    auth,
)

API = "https://gw.test/webhook/baalebos-ai"


def make(handler, **kw):
    return AsyncBaalebosAI(api_url=API, _transport=httpx.MockTransport(handler), **kw)


def ok_handler(text="hi"):
    return lambda request: httpx.Response(200, json={"text": text})


def run(coro):
    return asyncio.run(coro)


def test_chat_sends_the_expected_request():
    seen = []

    def handler(request):
        seen.append(request)
        return httpx.Response(200, json={"text": "hello back"})

    c = make(handler, api_key="k1")
    assert run(c.chat("hello", mode="manual", model="mistral-small")) == "hello back"
    req = seen[0]
    assert str(req.url) == API and req.headers["x-api-key"] == "k1"
    import json
    assert json.loads(req.content) == {"message": "hello", "mode": "manual", "temperature": 0.7, "model": "mistral-small"}


def test_positional_temperature_matches_the_sync_client():
    import json
    seen = []
    c = make(lambda r: seen.append(json.loads(r.content)) or httpx.Response(200, json={"text": "x"}), api_key="k")
    run(c.chat("hi", "fast", 0.2))
    assert seen[0]["mode"] == "fast" and seen[0]["temperature"] == 0.2


def test_first_chat_registers_a_key_off_the_event_loop(monkeypatch):
    monkeypatch.setattr(requests, "post", Recorder([FakeResponse(200, {"api_key": "auto"})]))
    keys = []
    c = make(lambda r: keys.append(r.headers["x-api-key"]) or httpx.Response(200, json={"text": "x"}))
    assert c.api_key is None  # nothing happens in the constructor
    run(c.chat("hi"))
    assert keys == ["auto"] and c.api_key == "auto" and auth.load_saved_key() == "auto"


def test_stale_auto_key_is_replaced_transparently(monkeypatch):
    auth.save_key("stale")
    monkeypatch.setattr(requests, "post", Recorder([FakeResponse(200, {"api_key": "renewed"})]))

    def handler(request):
        if request.headers["x-api-key"] == "stale":
            return httpx.Response(401, json={"error": "unauthorized"})
        return httpx.Response(200, json={"text": "worked"})

    c = make(handler)
    assert run(c.chat("hi")) == "worked"
    assert auth.load_saved_key() == "renewed"


def test_supplied_key_is_never_swapped():
    c = make(lambda r: httpx.Response(401), api_key="mine")
    with pytest.raises(BaalebosAuthError) as e:
        run(c.chat("hi"))
    assert e.value.status_code == 401


@pytest.mark.parametrize(
    "status, body, exc",
    [
        (429, {"message": "daily limit reached"}, BaalebosRateLimitError),
        (404, {}, BaalebosUnavailableError),
        (500, {"message": "boom"}, BaalebosUnavailableError),
    ],
)
def test_error_mapping(status, body, exc):
    c = make(lambda r: httpx.Response(status, json=body), api_key="k")
    with pytest.raises(exc) as e:
        run(c.chat("hi"))
    assert e.value.status_code == status


def test_retries_transient_statuses_with_backoff(async_sleeps):
    responses = iter([httpx.Response(502), httpx.Response(503), httpx.Response(200, json={"text": "finally"})])
    c = make(lambda r: next(responses), api_key="k")
    assert run(c.chat("hi")) == "finally"
    assert async_sleeps == [0.5, 1.0]


def test_retries_connect_failures_but_not_read_timeouts():
    calls = []

    def flaky(request):
        calls.append(1)
        if len(calls) < 3:
            raise httpx.ConnectError("refused")
        return httpx.Response(200, json={"text": "back"})

    assert run(make(flaky, api_key="k").chat("hi")) == "back" and len(calls) == 3

    reads = []

    def slow(request):
        reads.append(1)
        raise httpx.ReadTimeout("slow")

    with pytest.raises(BaalebosConnectionError, match="timed out"):
        run(make(slow, api_key="k", timeout=5).chat("hi"))
    assert len(reads) == 1  # never replayed: it may already have been processed


def test_persistent_connect_failure_is_a_connection_error():
    def down(request):
        raise httpx.ConnectError("refused")

    with pytest.raises(BaalebosConnectionError, match="Could not reach"):
        run(make(down, api_key="k").chat("hi"))


def test_chat_json():
    c = make(lambda r: httpx.Response(200, json={"text": 'Sure:\n```json\n{"a": 1}\n```'}), api_key="k")
    assert run(c.chat_json("Return {a}", "go", required_keys=["a"])) == {"a": 1}
    bad = make(lambda r: httpx.Response(200, json={"text": "no json here"}), api_key="k")
    with pytest.raises(BaalebosStructuredOutputError):
        run(bad.chat_json("s", "u", max_attempts=2))


def test_status():
    c = make(lambda r: httpx.Response(200, json={"status": "ok"}), api_key="k")
    assert run(c.status()) == {"status": "ok"}
    down = make(lambda r: httpx.Response(404), api_key="k")
    with pytest.raises(BaalebosUnavailableError):
        run(down.status())


def test_concurrent_calls_share_one_client_safely():
    c = make(ok_handler("x"), api_key="k")

    async def many():
        return await asyncio.gather(*(c.chat(f"q{i}") for i in range(20)))

    assert run(many()) == ["x"] * 20
