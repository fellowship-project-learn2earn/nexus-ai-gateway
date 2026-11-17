import io
import json

import pytest
import requests
from conftest import FakeResponse, Recorder

from baalebos_ai import __version__
from baalebos_ai.cli import main

API = "https://gw.test/webhook/baalebos-ai"


@pytest.fixture(autouse=True)
def cli_env(monkeypatch):
    monkeypatch.setenv("BAALEBOS_API_URL", API)
    monkeypatch.setenv("BAALEBOS_API_KEY", "k")


def run(monkeypatch, script, argv, stdin=None):
    rec = Recorder(script)
    monkeypatch.setattr(requests, "post", rec)
    if stdin is not None:
        monkeypatch.setattr("sys.stdin", io.StringIO(stdin))
    return main(argv), rec


def test_version(capsys):
    with pytest.raises(SystemExit) as e:
        main(["--version"])
    assert e.value.code == 0
    assert __version__ in capsys.readouterr().out


def test_prints_the_answer(monkeypatch, ok, capsys):
    rc, rec = run(monkeypatch, [ok("42")], ["what", "is", "6x7"])
    assert rc == 0 and "42" in capsys.readouterr().out
    assert rec.calls[0][1]["json"]["message"] == "what is 6x7"


def test_no_prompt_is_a_usage_error(monkeypatch, capsys):
    monkeypatch.setattr("sys.stdin", io.StringIO(""))
    assert main([]) == 2
    assert "prompt" in capsys.readouterr().err


def test_piped_input_is_appended_to_the_prompt(monkeypatch, ok):
    rc, rec = run(monkeypatch, [ok()], ["explain this"], stdin="Traceback: boom\n")
    assert rc == 0
    assert rec.calls[0][1]["json"]["message"] == "explain this\n\nTraceback: boom"


def test_piped_input_alone_is_enough(monkeypatch, ok):
    rc, rec = run(monkeypatch, [ok()], [], stdin="just stdin")
    assert rc == 0 and rec.calls[0][1]["json"]["message"] == "just stdin"


def test_no_stdin_flag_ignores_piped_input(monkeypatch, ok):
    rc, rec = run(monkeypatch, [ok()], ["only this", "--no-stdin"], stdin="ignored")
    assert rec.calls[0][1]["json"]["message"] == "only this"


def test_mode_and_model_flags(monkeypatch, ok):
    rc, rec = run(monkeypatch, [ok()], ["hi", "--mode", "manual", "--model", "mistral-small"])
    assert rec.calls[0][1]["json"] == {
        "message": "hi", "mode": "manual", "temperature": 0.7, "model": "mistral-small",
    }


def test_mode_is_free_form_so_the_documented_fast_and_smart_still_work(monkeypatch, ok):
    """The published CLI documents `--mode fast`; the gateway treats unknown modes as auto."""
    for mode in ("fast", "smart"):
        rc, rec = run(monkeypatch, [ok()], ["hi", "--mode", mode])
        assert rc == 0 and rec.calls[0][1]["json"]["mode"] == mode


def test_raw_prints_full_json(monkeypatch, capsys):
    rc, _ = run(monkeypatch, [FakeResponse(200, {"text": "t", "usedModel": "groq-llama-3.3-70b"})], ["hi", "--raw"])
    assert json.loads(capsys.readouterr().out)["usedModel"] == "groq-llama-3.3-70b"


@pytest.mark.parametrize(
    "resp, needle",
    [
        (FakeResponse(429, {"message": "daily limit reached"}), "Limit reached"),
        (FakeResponse(404, text="x"), "Gateway unavailable"),
        (FakeResponse(401), "Authentication problem"),
        (FakeResponse(400, {"message": "bad"}), "Bad request"),
    ],
)
def test_errors_give_exit_code_1_and_a_helpful_message(monkeypatch, capsys, resp, needle):
    rc, _ = run(monkeypatch, [resp], ["hi"])
    assert rc == 1 and needle in capsys.readouterr().err


def test_status_flag(monkeypatch, capsys):
    monkeypatch.setattr(requests, "get", lambda url, **kw: FakeResponse(200, {"status": "ok"}))
    assert main(["--status"]) == 0
    assert "ok" in capsys.readouterr().out
    monkeypatch.setattr(requests, "get", lambda url, **kw: FakeResponse(404))
    assert main(["--status"]) == 1
    assert "unreachable" in capsys.readouterr().err
