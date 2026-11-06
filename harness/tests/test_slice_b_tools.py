from __future__ import annotations

import json
from pathlib import Path

from jsonschema import Draft202012Validator
from referencing import Registry, Resource
from referencing.jsonschema import DRAFT202012

from fixture_cad.chat import sanitize_actions
from fixture_cad.tools.registry import ToolRegistry

ROOT = Path(__file__).resolve().parents[2]
SCHEMAS = ROOT / "docs" / "schemas"

SLICE_B_TOOLS = {
    "attach_reference_image",
    "import_svg_sketch",
    "export_stl",
}


def _chat_request_validator() -> Draft202012Validator:
    store: dict = {}
    for path in SCHEMAS.glob("*.json"):
        data = json.loads(path.read_text(encoding="utf-8"))
        store[path.name] = data
        schema_id = data.get("$id")
        if isinstance(schema_id, str):
            store[schema_id] = data
    registry = Registry()
    for key, doc in store.items():
        registry = registry.with_resource(
            key, Resource.from_contents(doc, default_specification=DRAFT202012)
        )
    return Draft202012Validator(store["chat-request.json"], registry=registry)


def _base_request(**extra_overrides: object) -> dict:
    payload: dict = {
        "app": "freecad",
        "version": "0.1.0",
        "context": {
            "active_document": "Unnamed",
            "workbench_or_mode": "PartDesign",
            "selected_objects": [],
            "extra": {},
        },
        "message": "hello",
        "mode": "chat",
    }
    if extra_overrides:
        payload["context"]["extra"] = dict(extra_overrides)
    return payload


def test_slice_b_tools_are_freecad_only() -> None:
    registry = ToolRegistry.load()
    freecad = {tool.name for tool in registry.for_app("freecad")}
    blender = {tool.name for tool in registry.for_app("blender")}
    assert SLICE_B_TOOLS <= freecad
    assert SLICE_B_TOOLS.isdisjoint(blender)
    attach = registry.get("attach_reference_image")
    assert attach is not None and attach.permission == "auto"
    assert registry.get("import_svg_sketch") is not None
    assert registry.get("import_svg_sketch").permission == "confirm"
    assert registry.get("export_stl") is not None
    assert registry.get("export_stl").permission == "confirm"


def test_slice_b_tools_survive_sanitizer() -> None:
    registry = ToolRegistry.load()
    actions, warnings = sanitize_actions(
        [
            {"type": "tool_call", "tool_name": "attach_reference_image", "args": {}},
            {
                "type": "tool_call",
                "tool_name": "import_svg_sketch",
                "args": {"name": "Outline"},
            },
            {
                "type": "tool_call",
                "tool_name": "export_stl",
                "args": {"path": "remote.stl", "object_names": ["Box"]},
            },
        ],
        app="freecad",
        registry=registry,
    )
    assert warnings == []
    assert [action["tool_name"] for action in actions] == [
        "attach_reference_image",
        "import_svg_sketch",
        "export_stl",
    ]


def test_export_stl_rejects_path_with_separator() -> None:
    registry = ToolRegistry.load()
    actions, warnings = sanitize_actions(
        [
            {
                "type": "tool_call",
                "tool_name": "export_stl",
                "args": {"path": "a/b.stl"},
            }
        ],
        app="freecad",
        registry=registry,
    )
    assert actions == []
    assert any("export_stl" in warning for warning in warnings)


def test_import_svg_sketch_rejects_unknown_props() -> None:
    registry = ToolRegistry.load()
    actions, warnings = sanitize_actions(
        [
            {
                "type": "tool_call",
                "tool_name": "import_svg_sketch",
                "args": {"path": "/tmp/x.svg"},
            }
        ],
        app="freecad",
        registry=registry,
    )
    assert actions == []
    assert any("import_svg_sketch" in warning for warning in warnings)


def test_reference_image_schema_accepts_bounded_payload() -> None:
    validator = _chat_request_validator()
    payload = _base_request(
        reference_image={
            "file_name": "remote-outline.svg",
            "media_type": "image/svg+xml",
            "byte_size": 420,
            "width_px": 200,
            "height_px": 120,
        }
    )
    assert list(validator.iter_errors(payload)) == []


def test_reference_image_schema_rejects_oversize_and_separators() -> None:
    validator = _chat_request_validator()
    oversize = _base_request(
        reference_image={
            "file_name": "big.png",
            "media_type": "image/png",
            "byte_size": 8388609,
        }
    )
    assert list(validator.iter_errors(oversize))

    with_sep = _base_request(
        reference_image={
            "file_name": "dir/remote.png",
            "media_type": "image/png",
            "byte_size": 100,
        }
    )
    assert list(validator.iter_errors(with_sep))


def _raster_context(media_type: str) -> dict:
    return {
        "extra": {
            "reference_image": {
                "file_name": "sketch.png",
                "media_type": media_type,
                "byte_size": 1024,
            }
        }
    }


def _svg_context() -> dict:
    return {
        "extra": {
            "reference_image": {
                "file_name": "outline.svg",
                "media_type": "image/svg+xml",
                "byte_size": 2048,
            }
        }
    }


def _import_svg_sketch_actions(name: str = "Outline") -> list[dict]:
    return [
        {
            "type": "tool_call",
            "tool_name": "import_svg_sketch",
            "args": {"name": name},
        }
    ]


def test_sanitize_actions_strips_import_svg_sketch_for_raster_png() -> None:
    registry = ToolRegistry.load()
    actions, warnings = sanitize_actions(
        _import_svg_sketch_actions(),
        app="freecad",
        registry=registry,
        context=_raster_context("image/png"),
    )
    assert actions == []
    assert any("import_svg_sketch" in w for w in warnings)


def test_sanitize_actions_strips_import_svg_sketch_for_raster_jpeg() -> None:
    registry = ToolRegistry.load()
    actions, warnings = sanitize_actions(
        _import_svg_sketch_actions(),
        app="freecad",
        registry=registry,
        context=_raster_context("image/jpeg"),
    )
    assert actions == []
    assert any("import_svg_sketch" in w for w in warnings)


def test_sanitize_actions_allows_import_svg_sketch_for_svg() -> None:
    registry = ToolRegistry.load()
    actions, warnings = sanitize_actions(
        _import_svg_sketch_actions(),
        app="freecad",
        registry=registry,
        context=_svg_context(),
    )
    assert len(actions) == 1
    assert actions[0]["tool_name"] == "import_svg_sketch"
    assert warnings == []


def test_sanitize_actions_strips_import_svg_sketch_when_media_type_absent() -> None:
    registry = ToolRegistry.load()
    actions, warnings = sanitize_actions(
        _import_svg_sketch_actions(),
        app="freecad",
        registry=registry,
        context={
            "extra": {
                "reference_image": {
                    "file_name": "sketch.png",
                    "byte_size": 1024,
                }
            }
        },
    )
    assert actions == []
    assert any("import_svg_sketch" in w for w in warnings)
