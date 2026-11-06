"""Pure tests for FreeCAD post-Apply verify helpers."""

from __future__ import annotations

import sys
from pathlib import Path

CLIENT_ROOT = Path(__file__).resolve().parents[1]
if str(CLIENT_ROOT) not in sys.path:
    sys.path.insert(0, str(CLIENT_ROOT))

from fixture.verify import (  # noqa: E402
    choose_tip_names,
    filter_verify_response,
    format_verify_history_text,
    parse_created_names,
)


def test_parse_created_names_partdesign_chain() -> None:
    logs = [
        "ok: create_body -> created PartDesign Body BracketBody",
        "ok: new_sketch -> created sketch Profile in BracketBody on XY",
        "ok: sketch_rectangle -> added rectangle to Profile x=0 y=0 width=40 height=20",
        "ok: pad_sketch -> created pad Pad from Profile length=10 midplane=False reversed=False",
    ]
    assert parse_created_names(logs) == [
        "BracketBody",
        "Profile",
        "Pad",
    ]


def test_choose_tip_prefers_pad_over_body() -> None:
    assert choose_tip_names(["BracketBody", "Profile", "Pad"]) == ["Pad"]


def test_choose_tip_prefers_pocket_over_pad() -> None:
    assert choose_tip_names(["Body", "Pad", "Pocket"]) == ["Pocket"]


def test_filter_verify_drops_confirm_tools() -> None:
    response = {
        "reply_text": "Created a pad.",
        "actions": [
            {"type": "meta", "kind": "status", "text": "ok"},
            {
                "type": "tool_call",
                "tool_name": "create_parametric_box",
                "args": {"width": 1, "height": 1, "depth": 1},
            },
            {"type": "tool_call", "tool_name": "fit_view_selection", "args": {}},
            {"type": "tool_call", "tool_name": "list_document_objects", "args": {}},
        ],
    }
    filtered = filter_verify_response(response)
    names = [
        a.get("tool_name")
        for a in filtered["actions"]
        if a.get("type") == "tool_call"
    ]
    assert "create_parametric_box" not in names
    assert "fit_view_selection" in names
    assert "list_document_objects" in names
    assert filtered["reply_text"] == "Created a pad."


def test_format_verify_history_clips() -> None:
    text = format_verify_history_text(
        {"tips": ["Pad"], "detail": "x" * 800},
        fit_result="view fitted",
    )
    assert "Pad" in text
    assert len(text) <= 600
