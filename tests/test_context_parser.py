import context_parser
from context_parser import (
    DEFAULT_CONTEXT,
    _extract_json_object,
    _sanitize_context,
    parse_interview_context,
)


def test_extract_plain_json():
    assert _extract_json_object('{"a": 1}') == {"a": 1}


def test_extract_embedded_json():
    raw = 'Sure! Here is the result:\n{"a": 1, "b": 2}\nThanks'
    assert _extract_json_object(raw) == {"a": 1, "b": 2}


def test_extract_invalid_returns_none():
    assert _extract_json_object("not json at all") is None
    assert _extract_json_object("") is None


def test_sanitize_empty_returns_defaults():
    r = _sanitize_context(None)
    assert r == DEFAULT_CONTEXT
    assert len(r["competencies"]) == 3


def test_sanitize_pads_competencies():
    r = _sanitize_context({"competencies": ["X"]})
    assert len(r["competencies"]) == 3
    assert r["competencies"][0] == "X"


def test_sanitize_truncates_competencies():
    r = _sanitize_context({"competencies": ["A", "B", "C", "D", "E"]})
    assert r["competencies"] == ["A", "B", "C"]


def test_sanitize_fills_missing_fields():
    r = _sanitize_context({"competencies": ["A", "B", "C"]})
    assert r["custom_question_title"] == DEFAULT_CONTEXT["custom_question_title"]
    assert r["expected_time"] == DEFAULT_CONTEXT["expected_time"]


def test_parse_no_input_skips_llm(monkeypatch):
    def boom(*a, **k):
        raise AssertionError("LLMClient must not be constructed for empty input")

    monkeypatch.setattr(context_parser, "LLMClient", boom)
    assert parse_interview_context("", "") == DEFAULT_CONTEXT


def test_parse_llm_failure_falls_back(monkeypatch):
    class BoomClient:
        def __init__(self, *a, **k):
            pass

        def set_system_prompt(self, *a, **k):
            pass

        def chat(self, *a, **k):
            raise RuntimeError("network down")

    monkeypatch.setattr(context_parser, "LLMClient", BoomClient)
    assert parse_interview_context("Some JD", "Some resume") == DEFAULT_CONTEXT


def test_parse_uses_llm_json(monkeypatch):
    payload = (
        '{"competencies": ["Graphs", "DP", "Systems"], '
        '"custom_question_title": "T", "custom_question_description": "D", '
        '"expected_time": "O(n)", "expected_space": "O(1)"}'
    )

    class OkClient:
        def __init__(self, *a, **k):
            pass

        def set_system_prompt(self, *a, **k):
            pass

        def chat(self, *a, **k):
            return payload

    monkeypatch.setattr(context_parser, "LLMClient", OkClient)
    r = parse_interview_context("JD", "Resume")
    assert r["competencies"] == ["Graphs", "DP", "Systems"]
    assert r["custom_question_title"] == "T"
