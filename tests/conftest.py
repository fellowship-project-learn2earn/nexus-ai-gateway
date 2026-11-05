import json
from types import SimpleNamespace

import pytest

import baalebos_ai.client as client_module


class FakeResponse:
    def __init__(self, status=200, body=None, text=None):
        self.status_code = status
        self._body = body
        self.text = text if text is not None else (json.dumps(body) if body is not None else "")

    def json(self):
        if self._body is None:
            raise ValueError("no json")
        return self._body


class Recorder:
    """Stands in for requests.post/get. Each entry in `script` is a FakeResponse or an exception,
    consumed in order; a callable entry is called with (url, kwargs)."""

    def __init__(self, script):
        self.script = list(script)
        self.calls = []

    def __call__(self, url, **kwargs):
        self.calls.append((url, kwargs))
        step = self.script.pop(0) if len(self.script) > 1 else self.script[0]
        if callable(step):
            step = step(url, kwargs)
        if isinstance(step, Exception):
            raise step
        return step

    @property
    def urls(self):
        return [c[0] for c in self.calls]


@pytest.fixture(autouse=True)
def isolated(monkeypatch, tmp_path):
    monkeypatch.setenv("BAALEBOS_CONFIG_DIR", str(tmp_path / "cfg"))
    monkeypatch.delenv("BAALEBOS_API_KEY", raising=False)
    monkeypatch.delenv("BAALEBOS_API_URL", raising=False)
    state = SimpleNamespace(sleeps=[], async_sleeps=[])

    async def fake_async_sleep(delay):
        state.async_sleeps.append(delay)

    monkeypatch.setattr(client_module, "_sleep", state.sleeps.append)
    monkeypatch.setattr(client_module, "_async_sleep", fake_async_sleep)
    return state


@pytest.fixture
def sleeps(isolated):
    return isolated.sleeps


@pytest.fixture
def async_sleeps(isolated):
    return isolated.async_sleeps


@pytest.fixture
def ok():
    return lambda text="hello": FakeResponse(200, {"text": text, "success": True})
