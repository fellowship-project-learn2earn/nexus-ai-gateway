import pytest

from baalebos_ai.structured import (
    BaalebosStructuredOutputError,
    build_structured_prompt,
    extract_json,
    parse_structured_response,
)


@pytest.mark.parametrize(
    "raw, expected",
    [
        ('{"a": 1}', {"a": 1}),
        ('```json\n{"a": 1}\n```', {"a": 1}),
        ('```\n{"a": 1}\n```', {"a": 1}),
        ('Sure! Here you go:\n{"a": 1}\nHope that helps!', {"a": 1}),
        ('{"o": {"i": [1, 2, 3]}, "x": true}', {"o": {"i": [1, 2, 3]}, "x": True}),
        ('Result: {"o": {"i": [1, 2]}} done', {"o": {"i": [1, 2]}}),
        ('Use the format {key: value} like this: {"a": 1}', {"a": 1}),
        ('{"a": 1} -- you can also use {placeholders} here', {"a": 1}),
        ('{"fix": "def f(): return {}", "n": "empty"}', {"fix": "def f(): return {}", "n": "empty"}),
        ('{"q": "she said \\"hi\\""}', {"q": 'she said "hi"'}),
        ('Pretty:\n{\n  "name": "t",\n  "items": [\n    "a",\n    "b"\n  ]\n}\nbye', {"name": "t", "items": ["a", "b"]}),
    ],
)
def test_extracts_object(raw, expected):
    assert extract_json(raw) == expected


@pytest.mark.parametrize("raw", ["", "   ", "I'm sorry, I can't help with that.", '{"a": 1, "b": ', "[1, 2, 3]", "42"])
def test_unparseable_raises(raw):
    with pytest.raises(BaalebosStructuredOutputError):
        extract_json(raw)


def test_required_keys():
    assert parse_structured_response('{"a": 1, "b": 2}', ["a", "b"]) == {"a": 1, "b": 2}
    with pytest.raises(BaalebosStructuredOutputError, match="'b'"):
        parse_structured_response('{"a": 1}', ["a", "b"])


def test_prompt_builder_folds_system_and_user_together():
    p = build_structured_prompt('  You return {"x": ...}  ', "  Analyze this.  ")
    assert p.startswith('You return {"x": ...}')
    assert "Analyze this." in p and p.endswith("before or after it.")
