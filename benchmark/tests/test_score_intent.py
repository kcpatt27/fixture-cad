"""Unit tests for N1 intent-aware scoring (no Ollama)."""

from __future__ import annotations

from fixture_bench.score import score_case


def _base_case(**expect):
    return {
        "id": "t",
        "app": "freecad",
        "expect": expect,
    }


def test_intent_status_and_forbid_all_tools() -> None:
    scored = score_case(
        case=_base_case(
            intent_status="ambiguous",
            forbid_all_tools=True,
            required_tools=[],
            forbidden_tools=[],
        ),
        raw_parsed={"reply_text": "Need size", "actions": []},
        raw_text="{}",
        sanitized={
            "reply_text": "Need size",
            "actions": [],
            "intent_status": "ambiguous",
            "supported_scope": {
                "summary": "Need clarification",
                "clarifying_question": "What plate size?",
            },
        },
        sanitize_warnings=[],
        latency_s=0.1,
    )
    assert scored["checks"]["intent_ok"] is True
    assert scored["checks"]["forbid_all_tools"] is True
    assert scored["score"] == scored["max_score"]


def test_partial_scope_substr_and_tools() -> None:
    scored = score_case(
        case=_base_case(
            intent_status="partial",
            required_tools=["create_body"],
            forbidden_tools=["clean_mesh"],
            require_need_confirm=True,
            required_scope_substr=["remain"],
        ),
        raw_parsed={
            "reply_text": "I can start with a plate",
            "actions": [
                {"type": "tool_call", "tool_name": "create_body", "args": {"name": "Body"}},
            ],
        },
        raw_text="{}",
        sanitized={
            "reply_text": "I can start with a plate",
            "actions": [
                {"type": "meta", "kind": "need_confirm", "text": "Apply plate?"},
                {"type": "tool_call", "tool_name": "create_body", "args": {"name": "Body"}},
            ],
            "intent_status": "partial",
            "supported_scope": {
                "summary": "Create a plate",
                "remainder": "Barrels remain unsupported",
            },
        },
        sanitize_warnings=[],
        latency_s=0.2,
    )
    assert scored["checks"]["intent_ok"] is True
    assert scored["checks"]["scope_substr"] is True
    assert scored["checks"]["tool_hit"] is True
    assert scored["checks"]["need_confirm"] is True


def test_forbid_all_tools_fails_when_tools_present() -> None:
    scored = score_case(
        case=_base_case(forbid_all_tools=True),
        raw_parsed={"reply_text": "ok", "actions": []},
        raw_text="{}",
        sanitized={
            "reply_text": "ok",
            "actions": [
                {
                    "type": "tool_call",
                    "tool_name": "create_parametric_box",
                    "args": {"width": 1, "height": 1, "depth": 1},
                }
            ],
            "intent_status": "supported",
            "supported_scope": {"summary": "box"},
        },
        sanitize_warnings=[],
        latency_s=0.1,
    )
    assert scored["checks"]["forbid_all_tools"] is False


def test_error_path_uses_case_max_score() -> None:
    scored = score_case(
        case=_base_case(intent_status="ambiguous", require_need_confirm=True),
        raw_parsed=None,
        raw_text="",
        sanitized={"reply_text": "", "actions": []},
        sanitize_warnings=[],
        latency_s=0.1,
        error="provider down",
    )
    assert scored["max_score"] == 9.0
    assert scored["score"] == 0.0
