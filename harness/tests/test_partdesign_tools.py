from __future__ import annotations

from typing import Any

from fixture_cad.chat import ensure_need_confirm, sanitize_actions
from fixture_cad.tools.registry import ToolRegistry

PARTDESIGN_TOOLS = {
    "create_body",
    "new_sketch",
    "sketch_rectangle",
    "pad_sketch",
    "pocket_sketch",
}


def _chain() -> list[dict[str, Any]]:
    return [
        {"type": "tool_call", "tool_name": "create_body", "args": {"name": "Body"}},
        {
            "type": "tool_call",
            "tool_name": "new_sketch",
            "args": {"body_name": "Body", "plane": "XY", "name": "Profile"},
        },
        {
            "type": "tool_call",
            "tool_name": "sketch_rectangle",
            "args": {
                "sketch_name": "Profile",
                "x": 0,
                "y": 0,
                "width": 40,
                "height": 20,
            },
        },
        {
            "type": "tool_call",
            "tool_name": "pad_sketch",
            "args": {"sketch_name": "Profile", "length": 10, "name": "Pad"},
        },
        {
            "type": "tool_call",
            "tool_name": "new_sketch",
            "args": {"body_name": "Body", "plane": "XY", "name": "CutProfile"},
        },
        {
            "type": "tool_call",
            "tool_name": "sketch_rectangle",
            "args": {
                "sketch_name": "CutProfile",
                "x": 10,
                "y": 5,
                "width": 20,
                "height": 10,
            },
        },
        {
            "type": "tool_call",
            "tool_name": "pocket_sketch",
            "args": {
                "sketch_name": "CutProfile",
                "length": 5,
                "reversed": True,
                "name": "Pocket",
            },
        },
    ]


def test_partdesign_tools_are_freecad_only() -> None:
    registry = ToolRegistry.load()
    freecad = {tool.name for tool in registry.for_app("freecad")}
    blender = {tool.name for tool in registry.for_app("blender")}
    assert PARTDESIGN_TOOLS <= freecad
    assert PARTDESIGN_TOOLS.isdisjoint(blender)


def test_partdesign_chain_survives_sanitizer() -> None:
    registry = ToolRegistry.load()
    actions, warnings = sanitize_actions(_chain(), app="freecad", registry=registry)
    assert warnings == []
    assert [action["tool_name"] for action in actions] == [
        "create_body",
        "new_sketch",
        "sketch_rectangle",
        "pad_sketch",
        "new_sketch",
        "sketch_rectangle",
        "pocket_sketch",
    ]


def test_partdesign_bad_pocket_length_is_dropped() -> None:
    registry = ToolRegistry.load()
    actions, warnings = sanitize_actions(
        [
            {
                "type": "tool_call",
                "tool_name": "pocket_sketch",
                "args": {"sketch_name": "CutProfile", "length": -1},
            }
        ],
        app="freecad",
        registry=registry,
    )
    assert actions == []
    assert warnings


def test_partdesign_chain_gets_one_confirmation_boundary() -> None:
    registry = ToolRegistry.load()
    actions = ensure_need_confirm(_chain(), registry=registry)
    confirms = [action for action in actions if action.get("kind") == "need_confirm"]
    assert len(confirms) == 1
    assert actions[0]["kind"] == "need_confirm"
