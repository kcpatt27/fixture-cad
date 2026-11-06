"""Pure tests for bounded conversation history helpers."""

from __future__ import annotations

from fixture.conversation_history import (
    HISTORY_MAX_TOTAL_CHARS,
    HISTORY_MAX_TURNS,
    append_structured_turn,
    compact_history,
    format_intent_presentation,
    history_for_request,
)


def test_append_ignores_non_dialogue_roles() -> None:
    turns = append_structured_turn([], role="user", text="hello")
    turns = append_structured_turn(turns, role="tool", text="should skip")
    turns = append_structured_turn(turns, role="assistant", text="hi")
    assert turns == [
        {"role": "user", "text": "hello"},
        {"role": "assistant", "text": "hi"},
    ]


def test_six_turn_retention() -> None:
    turns: list[dict[str, str]] = []
    for i in range(8):
        turns = append_structured_turn(turns, role="user", text=f"u{i}")
        turns = append_structured_turn(turns, role="assistant", text=f"a{i}")
    assert len(turns) == HISTORY_MAX_TURNS
    assert turns[0]["text"] == "u5"
    assert turns[-1]["text"] == "a7"


def test_total_char_budget_drops_oldest_keeps_clarification_pair() -> None:
    filler = "f" * 500
    turns = [
        {"role": "user", "text": filler},
        {"role": "assistant", "text": filler},
        {"role": "user", "text": filler},
        {"role": "assistant", "text": filler},
        {"role": "user", "text": "accept the base plate"},
        {"role": "assistant", "text": "I can create a 30x15x2 plate."},
    ]
    compacted = compact_history(turns)
    total = sum(len(t["text"]) for t in compacted)
    assert total <= HISTORY_MAX_TOTAL_CHARS
    assert compacted[-2]["text"] == "accept the base plate"
    assert "30x15x2" in compacted[-1]["text"]


def test_history_for_request_is_prior_only() -> None:
    prior = [
        {"role": "user", "text": "make a hinge"},
        {"role": "assistant", "text": "I can start with a plate."},
    ]
    assert history_for_request(prior) == prior


def test_format_intent_presentation() -> None:
    lines = format_intent_presentation(
        "partial",
        {
            "summary": "Create a rectangular plate.",
            "remainder": "Barrels remain unsupported.",
            "clarifying_question": "Accept the plate?",
        },
    )
    assert lines[0].startswith("intent: partial")
    assert "scope: Create a rectangular plate." in lines
    assert "remainder: Barrels remain unsupported." in lines
    assert "clarify: Accept the plate?" in lines
