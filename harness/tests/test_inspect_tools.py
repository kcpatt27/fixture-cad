"""Harness registry coverage for N2 inspect tools."""

from __future__ import annotations

from fixture_cad.chat import sanitize_actions
from fixture_cad.tools.registry import ToolRegistry

INSPECT_TOOLS = {"list_document_objects", "get_object"}


def test_inspect_tools_are_freecad_auto_only() -> None:
    registry = ToolRegistry.load()
    freecad = {tool.name: tool for tool in registry.for_app("freecad")}
    blender = {tool.name for tool in registry.for_app("blender")}
    assert INSPECT_TOOLS <= set(freecad)
    assert INSPECT_TOOLS.isdisjoint(blender)
    for name in INSPECT_TOOLS:
        assert freecad[name].permission == "auto"


def test_get_object_requires_object_name() -> None:
    registry = ToolRegistry.load()
    actions, warnings = sanitize_actions(
        [{"type": "tool_call", "tool_name": "get_object", "args": {}}],
        app="freecad",
        registry=registry,
    )
    assert actions == []
    assert warnings


def test_list_and_get_survive_sanitizer() -> None:
    registry = ToolRegistry.load()
    actions, warnings = sanitize_actions(
        [
            {"type": "tool_call", "tool_name": "list_document_objects", "args": {}},
            {
                "type": "tool_call",
                "tool_name": "get_object",
                "args": {"object_name": "Pad"},
            },
        ],
        app="freecad",
        registry=registry,
    )
    assert warnings == []
    assert [a["tool_name"] for a in actions] == [
        "list_document_objects",
        "get_object",
    ]
