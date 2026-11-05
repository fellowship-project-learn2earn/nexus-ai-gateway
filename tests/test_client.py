import pytest
import requests
from conftest import FakeResponse, Recorder

from baalebos_ai import (
    BaalebosAI,
    BaalebosAPIError,
    BaalebosAuthError,
    BaalebosConfigError,
    BaalebosConnectionError,
    BaalebosError,
    BaalebosRateLimitError,
    BaalebosRequestError,
    BaalebosStructuredOutputError,
    BaalebosUnavailableError,
    auth,
    check_status,
)

API = "https://gw.test/webhook/baalebos-ai"
SIGNUP = API + "-signup"


def client(monkeypatch, script, **kw):
    rec = Recorder(script)
    monkeypatch.setattr(requests, "post", rec)
    return BaalebosAI(api_url=API, **kw), rec


def test_chat_returns_text_and_sends_expected_request(monkeypatch, ok):
    c, rec = client(monkeypatch, [ok("hi there")], api_key="k1")
    assert c.chat("hello", mode="manual", model="mistral-small") == "hi there"
    url, kw = rec.calls[0]
    assert url == API
    assert kw["headers"]["x-api-key"] == "k1"
    assert kw["json"] == {"message": "hello", "mode": "manual", "temperature": 0.7, "model": "mistral-small"}


def test_temperature_default_explicit_and_omitted(monkeypatch, ok):
    c, rec = client(monkeypatch, [ok()], api_key="k")
    c.chat("x")
    c.chat("x", temperature=0.1)
    c.chat("x", temperature=None)
    sent = [call[1]["json"] for call in rec.calls]
    assert sent[0]["temperature"] == 0.7 and sent[1]["temperature"] == 0.1 and "temperature" not in sent[2]


def test_models_list_is_forwarded(monkeypatch, ok):
    c, rec = client(monkeypatch, [ok()], api_key="k")
    c.chat("x", mode="fallback", models=["a", "b"])
    assert rec.calls[0][1]["json"]["models"] == ["a", "b"]


@pytest.mark.parametrize(
    "body",
    [
        {"text": "t"},
        {"output": "t"},
        {"data": {"choices": [{"message": {"content": "t"}}]}},
    ],
)
def test_every_response_shape_the_gateway_has_used_is_understood(monkeypatch, body):
    c, _ = client(monkeypatch, [FakeResponse(200, body)], api_key="k")
    assert c.chat("x") == "t"


def test_malformed_nested_shape_is_an_error_not_a_crash(monkeypatch):
    c, _ = client(monkeypatch, [FakeResponse(200, {"data": {"choices": []}})], api_key="k")
    with pytest.raises(BaalebosAPIError, match="no text"):
        c.chat("x")


def test_constructing_a_client_does_no_network_io(monkeypatch):
    c, rec = client(monkeypatch, [FakeResponse(200, {"api_key": "n"})])
    assert rec.calls == []
    assert c._api_key is None


def test_a_malformed_url_is_a_config_error():
    with pytest.raises(BaalebosConfigError, match="http"):
        BaalebosAI(api_url="gateway.baalebo.xyz/webhook/baalebos-ai")


def test_first_chat_registers_then_later_clients_reuse_the_saved_key(monkeypatch, ok):
    c, rec = client(monkeypatch, [FakeResponse(200, {"api_key": "auto"}), ok("a"), ok("b")])
    assert c.chat("q1") == "a"
    assert rec.urls[:2] == [SIGNUP, API]
    assert rec.calls[1][1]["headers"]["x-api-key"] == "auto"
    c2 = BaalebosAI(api_url=API)
    monkeypatch.setattr(requests, "post", Recorder([ok("b")]))
    assert c2.chat("q2") == "b"
    assert auth.load_saved_key() == "auto"


def test_explicit_and_env_keys_never_register(monkeypatch, ok):
    c, rec = client(monkeypatch, [ok()], api_key="mine")
    c.chat("x")
    assert SIGNUP not in rec.urls
    monkeypatch.setenv("BAALEBOS_API_KEY", "envkey")
    c, rec = client(monkeypatch, [ok()])
    c.chat("x")
    assert SIGNUP not in rec.urls and rec.calls[0][1]["headers"]["x-api-key"] == "envkey"


def test_stale_auto_key_is_replaced_transparently(monkeypatch, ok):
    auth.save_key("stale")
    c, rec = client(monkeypatch, [FakeResponse(401), FakeResponse(200, {"api_key": "renewed"}), ok("worked")])
    assert c.chat("x") == "worked"
    assert rec.urls == [API, SIGNUP, API]
    assert rec.calls[2][1]["headers"]["x-api-key"] == "renewed"
    assert auth.load_saved_key() == "renewed"


def test_supplied_key_is_never_silently_swapped(monkeypatch):
    c, rec = client(monkeypatch, [FakeResponse(401)], api_key="mine")
    with pytest.raises(BaalebosAuthError) as e:
        c.chat("x")
    assert e.value.status_code == 401 and SIGNUP not in rec.urls


def test_still_401_after_reregistering_raises(monkeypatch):
    auth.save_key("stale")
    c, _ = client(monkeypatch, [FakeResponse(401), FakeResponse(200, {"api_key": "new"}), FakeResponse(401)])
    with pytest.raises(BaalebosAuthError):
        c.chat("x")


@pytest.mark.parametrize(
    "resp, exc, status, needle",
    [
        (FakeResponse(429, {"message": "daily limit reached"}), BaalebosRateLimitError, 429, "daily limit reached"),
        (FakeResponse(400, {"message": "message is required"}), BaalebosRequestError, 400, "message is required"),
        (FakeResponse(413, {"message": "too long"}), BaalebosRequestError, 413, "too long"),
        (FakeResponse(404, text="Not Found"), BaalebosUnavailableError, 404, "404"),
        (FakeResponse(500, {"message": "boom"}), BaalebosUnavailableError, 500, "boom"),
        (FakeResponse(418, text="teapot"), BaalebosAPIError, 418, "418"),
    ],
)
def test_error_mapping(monkeypatch, resp, exc, status, needle):
    c, _ = client(monkeypatch, [resp], api_key="k")
    with pytest.raises(exc, match=needle) as e:
        c.chat("x")
    assert e.value.status_code == status


def test_retries_transient_failures_with_backoff(monkeypatch, ok, sleeps):
    c, rec = client(monkeypatch, [FakeResponse(502), FakeResponse(503), ok("finally")], api_key="k")
    assert c.chat("x") == "finally"
    assert len(rec.calls) == 3 and sleeps == [0.5, 1.0]


def test_gives_up_after_max_retries(monkeypatch):
    c, rec = client(monkeypatch, [FakeResponse(503, {"message": "key service temporarily unavailable"})], api_key="k")
    with pytest.raises(BaalebosUnavailableError, match="temporarily unavailable"):
        c.chat("x")
    assert len(rec.calls) == 3  # 1 try + 2 retries


def test_retries_connection_failures(monkeypatch, ok):
    script = [requests.ConnectionError("reset"), requests.ConnectTimeout("slow connect"), ok("back")]
    c, rec = client(monkeypatch, script, api_key="k")
    assert c.chat("x") == "back"
    assert len(rec.calls) == 3


def test_a_read_timeout_is_not_replayed(monkeypatch):
    """The request may already have been processed (and counted); replaying could double-spend quota."""
    c, rec = client(monkeypatch, [requests.ReadTimeout("slow")], api_key="k", timeout=5)
    with pytest.raises(BaalebosConnectionError, match="timed out after 5s"):
        c.chat("x")
    assert len(rec.calls) == 1


def test_persistent_network_failure_is_a_connection_error(monkeypatch):
    c, _ = client(monkeypatch, [requests.ConnectionError("down")], api_key="k")
    with pytest.raises(BaalebosConnectionError, match="Could not reach"):
        c.chat("x")


def test_network_errors_are_summarised_not_dumped(monkeypatch):
    noisy = requests.ConnectionError("HTTPConnectionPool(host='x'): Max retries exceeded (Caused by NewConnectionError)")
    c, _ = client(monkeypatch, [noisy], api_key="k")
    with pytest.raises(BaalebosConnectionError) as e:
        c.chat("x")
    msg = str(e.value)
    assert "could not connect" in msg and "HTTPConnectionPool" not in msg and "NewConnectionError" not in msg


def test_does_not_retry_client_errors(monkeypatch):
    c, rec = client(monkeypatch, [FakeResponse(429, {"message": "limit"})], api_key="k")
    with pytest.raises(BaalebosRateLimitError):
        c.chat("x")
    assert len(rec.calls) == 1


def test_non_json_success_response(monkeypatch):
    c, _ = client(monkeypatch, [FakeResponse(200, text="<html>")], api_key="k")
    with pytest.raises(BaalebosUnavailableError):
        c.chat("x")


def test_success_without_text_is_an_api_error(monkeypatch):
    c, _ = client(monkeypatch, [FakeResponse(200, {"success": True})], api_key="k")
    with pytest.raises(BaalebosAPIError, match="no text"):
        c.chat("x")


def test_every_error_is_a_baalebos_error():
    for e in (
        BaalebosConfigError, BaalebosConnectionError, BaalebosAPIError, BaalebosAuthError,
        BaalebosRateLimitError, BaalebosRequestError, BaalebosUnavailableError, BaalebosStructuredOutputError,
    ):
        assert issubclass(e, BaalebosError)


def test_chat_json_parses_fenced_output(monkeypatch):
    c, rec = client(monkeypatch, [FakeResponse(200, {"text": '```json\n{"a": 1}\n```'})], api_key="k")
    assert c.chat_json("Return {a: int}", "go", required_keys=["a"]) == {"a": 1}
    sent = rec.calls[0][1]["json"]
    assert "Return {a: int}" in sent["message"] and "go" in sent["message"] and "ONLY the JSON" in sent["message"]
    assert sent["temperature"] == 0.2  # structured output defaults to a low temperature


def test_chat_json_asks_again_when_first_answer_is_not_json(monkeypatch):
    script = [FakeResponse(200, {"text": "Sorry, no."}), FakeResponse(200, {"text": '{"a": 2}'})]
    c, rec = client(monkeypatch, script, api_key="k")
    assert c.chat_json("s", "u") == {"a": 2}
    assert len(rec.calls) == 2


def test_chat_json_raises_after_max_attempts(monkeypatch):
    c, rec = client(monkeypatch, [FakeResponse(200, {"text": "nope"})], api_key="k")
    with pytest.raises(BaalebosStructuredOutputError):
        c.chat_json("s", "u", max_attempts=3)
    assert len(rec.calls) == 3


def test_chat_json_enforces_required_keys(monkeypatch):
    c, _ = client(monkeypatch, [FakeResponse(200, {"text": '{"a": 1}'})], api_key="k")
    with pytest.raises(BaalebosStructuredOutputError, match="'b'"):
        c.chat_json("s", "u", required_keys=["a", "b"], max_attempts=1)


def test_check_status_hits_the_health_endpoint(monkeypatch):
    seen = []
    monkeypatch.setattr(requests, "get", lambda url, **kw: seen.append(url) or FakeResponse(200, {"status": "ok"}))
    assert check_status(API) == {"status": "ok"}
    assert seen == [API + "-health"]


def test_check_status_failures(monkeypatch):
    monkeypatch.setattr(requests, "get", lambda url, **kw: FakeResponse(404))
    with pytest.raises(BaalebosUnavailableError):
        check_status(API)
    monkeypatch.setattr(requests, "get", lambda url, **kw: (_ for _ in ()).throw(requests.ConnectionError("x")))
    with pytest.raises(BaalebosConnectionError):
        check_status(API)
