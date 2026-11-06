from __future__ import annotations

from typing import Any

from fixture_cad.chat import ensure_need_confirm, sanitize_actions
from fixture_cad.tools.registry import ToolRegistry

N3_TOOLS = {
    "create_parametric_cylinder",
    "transform_placement",
    "boolean_cut",
    "boolean_fuse",
    "add_chamfer",
}


def test_n3_tools_are_freecad_only() -> None:
    registry = ToolRegistry.load()
    freecad = {tool.name for tool in registry.for_app("freecad")}
    blender = {tool.name for tool in registry.for_app("blender")}
    assert N3_TOOLS <= freecad
    assert N3_TOOLS.isdisjoint(blender)


def test_n3_cylinder_and_place_survive_sanitizer() -> None:
    registry = ToolRegistry.load()
    actions, warnings = sanitize_actions(
        [
            {
                "type": "tool_call",
                "tool_name": "create_parametric_cylinder",
                "args": {"radius": 5, "height": 20, "name": "Pin"},
            },
            {
                "type": "tool_call",
                "tool_name": "transform_placement",
                "args": {"object_name": "Pin", "x": 10, "y": 0, "z": 0},
            },
        ],
        app="freecad",
        registry=registry,
    )
    assert warnings == []
    assert [action["tool_name"] for action in actions] == [
        "create_parametric_cylinder",
        "transform_placement",
    ]


def test_n3_boolean_and_chamfer_survive_sanitizer() -> None:
    registry = ToolRegistry.load()
    actions, warnings = sanitize_actions(
        [
            {
                "type": "tool_call",
                "tool_name": "boolean_cut",
                "args": {"base_name": "Plate", "tool_name": "Cutter", "name": "CutPlate"},
            },
            {
                "type": "tool_call",
                "tool_name": "boolean_fuse",
                "args": {"base_name": "A", "tool_name": "B"},
            },
            {
                "type": "tool_call",
                "tool_name": "add_chamfer",
                "args": {"size": 1, "object_name": "Plate"},
            },
        ],
        app="freecad",
        registry=registry,
    )
    assert warnings == []
    assert [action["tool_name"] for action in actions] == [
        "boolean_cut",
        "boolean_fuse",
        "add_chamfer",
    ]


def test_n3_bad_args_are_dropped() -> None:
    registry = ToolRegistry.load()
    actions, warnings = sanitize_actions(
        [
            {
                "type": "tool_call",
                "tool_name": "create_parametric_cylinder",
                "args": {"radius": -1, "height": 10},
            },
            {
                "type": "tool_call",
                "tool_name": "transform_placement",
                "args": {"object_name": "Box"},
            },
            {
                "type": "tool_call",
                "tool_name": "add_chamfer",
                "args": {"size": 0},
            },
        ],
        app="freecad",
        registry=registry,
    )
    assert actions == []
    assert len(warnings) >= 3


def test_n3_chain_gets_one_confirmation_boundary() -> None:
    registry = ToolRegistry.load()
    chain: list[dict[str, Any]] = [
        {
            "type": "tool_call",
            "tool_name": "create_parametric_box",
            "args": {"width": 40, "height": 20, "depth": 4, "name": "LeafA"},
        },
        {
            "type": "tool_call",
            "tool_name": "create_parametric_box",
            "args": {"width": 40, "height": 20, "depth": 4, "name": "LeafB"},
        },
        {
            "type": "tool_call",
            "tool_name": "transform_placement",
            "args": {"object_name": "LeafB", "z": 8},
        },
        {
            "type": "tool_call",
            "tool_name": "create_parametric_cylinder",
            "args": {"radius": 3, "height": 16, "name": "Pin"},
        },
        {
            "type": "tool_call",
            "tool_name": "add_chamfer",
            "args": {"size": 0.5, "object_name": "LeafA"},
        },
    ]
    actions = ensure_need_confirm(chain, registry=registry)
    confirms = [action for action in actions if action.get("kind") == "need_confirm"]
    assert len(confirms) == 1
    assert actions[0]["kind"] == "need_confirm"
