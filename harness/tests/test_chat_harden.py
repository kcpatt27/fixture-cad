"""Unit tests for harness plan post-processing (no Ollama)."""

from __future__ import annotations

from fixture_cad.chat import (
    apply_intent_gate,
    build_system_prompt,
    build_user_prompt,
    ensure_need_confirm,
    finalize_plan,
    normalize_intent_fields,
    sanitize_actions,
)
from fixture_cad.tools.registry import ToolRegistry


def test_ensure_need_confirm_injects() -> None:
    reg = ToolRegistry.load()
    actions = [
        {
            "type": "tool_call",
            "tool_name": "create_parametric_box",
            "args": {"width": 40, "height": 40, "depth": 10},
        }
    ]
    out = ensure_need_confirm(actions, registry=reg)
    assert out[0]["type"] == "meta"
    assert out[0]["kind"] == "need_confirm"
    assert out[1]["tool_name"] == "create_parametric_box"


def test_ensure_need_confirm_noop_when_present() -> None:
    reg = ToolRegistry.load()
    actions = [
        {"type": "meta", "kind": "need_confirm", "text": "ok?"},
        {
            "type": "tool_call",
            "tool_name": "create_parametric_box",
            "args": {"width": 1, "height": 1, "depth": 1},
        },
    ]
    out = ensure_need_confirm(actions, registry=reg)
    assert sum(1 for a in out if a.get("kind") == "need_confirm") == 1


def test_strip_python_and_finalize() -> None:
    reg = ToolRegistry.load()
    plan = finalize_plan(
        reply_text="hi",
        raw_actions=[
            {"type": "python", "code": "print(1)"},
            {
                "type": "tool_call",
                "tool_name": "create_parametric_box",
                "args": {"width": 2, "height": 2, "depth": 2},
            },
        ],
        app="freecad",
        registry=reg,
        request_id="t",
        intent_status="supported",
        supported_scope={"summary": "Create a small box."},
    )
    assert "python" not in [a.get("type") for a in plan["actions"]]
    assert any(a.get("kind") == "need_confirm" for a in plan["actions"])
    assert any(a.get("tool_name") == "create_parametric_box" for a in plan["actions"])
    assert plan["intent_status"] == "supported"
    assert plan["supported_scope"]["summary"] == "Create a small box."


def test_unknown_tool_dropped() -> None:
    reg = ToolRegistry.load()
    actions, warnings = sanitize_actions(
        [{"type": "tool_call", "tool_name": "clean_mesh", "args": {}}],
        app="freecad",
        registry=reg,
    )
    assert actions == []
    assert warnings


def test_build_user_prompt_includes_history_before_message() -> None:
    prompt = build_user_prompt(
        "yes, make the base plate",
        {"selected_objects": []},
        "chat",
        history=[
            {"role": "user", "text": "make a hinge; start with anything you can"},
            {"role": "assistant", "text": "I can start with a rectangular base plate."},
        ],
    )
    assert prompt.index("history:") < prompt.index("message: yes, make the base plate")
    assert "rectangular base plate" in prompt


def test_build_user_prompt_clips_history_turns() -> None:
    long_text = "x" * 700
    prompt = build_user_prompt(
        "continue",
        {"selected_objects": []},
        "chat",
        history=[{"role": "user", "text": long_text}],
    )
    assert "x" * 600 not in prompt
    assert "…" in prompt


def test_fail_closed_missing_intent_strips_tools() -> None:
    reg = ToolRegistry.load()
    plan = finalize_plan(
        reply_text="I'll make a hinge",
        raw_actions=[
            {
                "type": "tool_call",
                "tool_name": "create_parametric_box",
                "args": {"width": 30, "height": 15, "depth": 2},
            }
        ],
        app="freecad",
        registry=reg,
        request_id="t",
        intent_status=None,
        supported_scope=None,
    )
    assert plan["intent_status"] == "ambiguous"
    assert not any(a.get("type") == "tool_call" for a in plan["actions"])
    assert "clarifying_question" in plan["supported_scope"]


def test_ambiguous_and_unsupported_strip_tools() -> None:
    reg = ToolRegistry.load()
    for status in ("ambiguous", "unsupported"):
        plan = finalize_plan(
            reply_text="Need more detail" if status == "ambiguous" else "Cannot do that",
            raw_actions=[
                {
                    "type": "tool_call",
                    "tool_name": "create_parametric_box",
                    "args": {"width": 10, "height": 10, "depth": 10},
                }
            ],
            app="freecad",
            registry=reg,
            request_id="t",
            intent_status=status,
            supported_scope={
                "summary": "Limit",
                "clarifying_question": "Which plate size?" if status == "ambiguous" else None,
            },
        )
        assert plan["intent_status"] == status
        assert not any(a.get("type") == "tool_call" for a in plan["actions"])


def test_partial_requires_remainder_and_confirm() -> None:
    reg = ToolRegistry.load()
    plan = finalize_plan(
        reply_text="I can start with a base plate only.",
        raw_actions=[
            {
                "type": "tool_call",
                "tool_name": "create_body",
                "args": {"name": "Body"},
            },
            {
                "type": "tool_call",
                "tool_name": "new_sketch",
                "args": {"body_name": "Body", "plane": "XY", "name": "Sketch"},
            },
            {
                "type": "tool_call",
                "tool_name": "sketch_rectangle",
                "args": {
                    "sketch_name": "Sketch",
                    "x": 0,
                    "y": 0,
                    "width": 30,
                    "height": 15,
                },
            },
            {
                "type": "tool_call",
                "tool_name": "pad_sketch",
                "args": {"sketch_name": "Sketch", "length": 2, "name": "Pad"},
            },
        ],
        app="freecad",
        registry=reg,
        request_id="t",
        intent_status="partial",
        supported_scope={
            "summary": "Create a 30×15×2 mm rectangular plate.",
            "remainder": "Interlocking barrels, pin, and second leaf remain unsupported.",
        },
    )
    assert plan["intent_status"] == "partial"
    assert any(a.get("type") == "tool_call" for a in plan["actions"])
    assert any(a.get("kind") == "need_confirm" for a in plan["actions"])
    assert "remainder" in plan["supported_scope"]


def test_partial_without_remainder_fails_closed() -> None:
    reg = ToolRegistry.load()
    plan = finalize_plan(
        reply_text="partial without remainder",
        raw_actions=[
            {
                "type": "tool_call",
                "tool_name": "fit_view_selection",
                "args": {},
            }
        ],
        app="freecad",
        registry=reg,
        request_id="t",
        intent_status="partial",
        supported_scope={"summary": "Fit the view."},
    )
    assert plan["intent_status"] == "ambiguous"
    assert not any(a.get("type") == "tool_call" for a in plan["actions"])


def test_normalize_intent_fields_defaults() -> None:
    status, scope, warnings = normalize_intent_fields(
        intent_status="nope",
        supported_scope={"summary": "  "},
    )
    assert status == "ambiguous"
    assert scope["summary"]
    assert "clarifying_question" in scope
    assert warnings


def test_apply_intent_gate_supported_passthrough() -> None:
    actions = [{"type": "tool_call", "tool_name": "fit_view_selection", "args": {}}]
    status, scope, out, warnings = apply_intent_gate(
        actions,
        intent_status="supported",
        supported_scope={"summary": "Fit view."},
    )
    assert status == "supported"
    assert out == actions
    assert warnings == []


def test_system_prompt_includes_ideation_policy() -> None:
    reg = ToolRegistry.load()
    prompt = build_system_prompt("freecad", reg)
    assert "Concept briefs / ideation" in prompt
    assert "bone chair" in prompt
    assert "create_parametric_box" in prompt
    assert "suggest Blender" in prompt
    assert "reference_image" in prompt
    assert "import_svg_sketch" in prompt


def test_align_box_dims_permutation() -> None:
    from fixture_cad.chat import align_tool_args

    actions, _ = align_tool_args(
        [
            {
                "type": "tool_call",
                "tool_name": "create_parametric_box",
                "args": {"width": 100, "height": 25, "depth": 60},
            }
        ],
        message="Start a printable enclosure about 100x60x25 mm, lid later",
    )
    args = actions[0]["args"]
    assert args == {"width": 100, "height": 60, "depth": 25}


def test_align_pad_sketch_name_from_import() -> None:
    from fixture_cad.chat import align_tool_args

    actions, _ = align_tool_args(
        [
            {
                "type": "tool_call",
                "tool_name": "import_svg_sketch",
                "args": {"name": "Outline"},
            },
            {
                "type": "tool_call",
                "tool_name": "pad_sketch",
                "args": {"length": 8},
            },
        ],
        message="Trace and pad 8 mm",
    )
    assert actions[1]["args"]["sketch_name"] == "Outline"


def test_finalize_injects_lid_in_reply_when_user_said_lid_later() -> None:
    reg = ToolRegistry.load()
    plan = finalize_plan(
        reply_text="I can start with a 100x60x25 mm box shell.",
        raw_actions=[
            {
                "type": "tool_call",
                "tool_name": "create_parametric_box",
                "args": {"width": 100, "height": 60, "depth": 25},
            }
        ],
        app="freecad",
        registry=reg,
        request_id="t",
        intent_status="partial",
        supported_scope={
            "summary": "Create a 100x60x25 mm box shell.",
            "remainder": "Lid remains unsupported.",
        },
        message="Start a printable enclosure about 100x60x25 mm, lid later",
    )
    assert "lid" in plan["reply_text"].lower()
    box = next(a for a in plan["actions"] if a.get("tool_name") == "create_parametric_box")
    assert box["args"]["height"] == 60
    assert box["args"]["depth"] == 25


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


def test_align_tool_args_strips_import_svg_sketch_for_raster_png() -> None:
    from fixture_cad.chat import align_tool_args

    ctx = _raster_context("image/png")
    out, _ = align_tool_args(_import_svg_sketch_actions(), context=ctx)
    assert out == []


def test_align_tool_args_strips_import_svg_sketch_for_raster_jpeg() -> None:
    from fixture_cad.chat import align_tool_args

    ctx = _raster_context("image/jpeg")
    out, _ = align_tool_args(_import_svg_sketch_actions(), context=ctx)
    assert out == []


def test_align_tool_args_strips_import_svg_sketch_for_raster_webp() -> None:
    from fixture_cad.chat import align_tool_args

    ctx = _raster_context("image/webp")
    out, _ = align_tool_args(_import_svg_sketch_actions(), context=ctx)
    assert out == []


def test_align_tool_args_strips_import_svg_sketch_for_raster_bmp() -> None:
    from fixture_cad.chat import align_tool_args

    ctx = _raster_context("image/bmp")
    out, _ = align_tool_args(_import_svg_sketch_actions(), context=ctx)
    assert out == []


def test_align_tool_args_allows_import_svg_sketch_for_svg() -> None:
    from fixture_cad.chat import align_tool_args

    ctx = _svg_context()
    out, _ = align_tool_args(_import_svg_sketch_actions(), context=ctx)
    assert len(out) == 1
    assert out[0]["tool_name"] == "import_svg_sketch"
    assert out[0]["args"]["name"] == "Outline"


def test_align_tool_args_allows_import_svg_sketch_when_no_reference_image() -> None:
    from fixture_cad.chat import align_tool_args

    out, _ = align_tool_args(_import_svg_sketch_actions(), context={})
    assert len(out) == 1
    assert out[0]["tool_name"] == "import_svg_sketch"


def test_align_tool_args_allows_import_svg_sketch_when_context_is_none() -> None:
    from fixture_cad.chat import align_tool_args

    out, _ = align_tool_args(_import_svg_sketch_actions(), context=None)
    assert len(out) == 1
    assert out[0]["tool_name"] == "import_svg_sketch"


def test_align_tool_args_strips_import_svg_sketch_but_keeps_other_tools_for_raster() -> None:
    from fixture_cad.chat import align_tool_args

    ctx = _raster_context("image/png")
    actions = [
        * _import_svg_sketch_actions(),
        {
            "type": "tool_call",
            "tool_name": "create_parametric_box",
            "args": {"width": 10, "height": 10, "depth": 10},
        },
    ]
    out, _ = align_tool_args(actions, context=ctx)
    assert len(out) == 1
    assert out[0]["tool_name"] == "create_parametric_box"


def test_align_tool_args_no_sketch_name_injection_for_pad_after_stripped_import() -> None:
    from fixture_cad.chat import align_tool_args

    ctx = _raster_context("image/png")
    actions = [
        * _import_svg_sketch_actions("Outline"),
        {
            "type": "tool_call",
            "tool_name": "pad_sketch",
            "args": {"length": 8},
        },
    ]
    out, _ = align_tool_args(actions, context=ctx)
    assert len(out) == 1
    assert out[0]["tool_name"] == "pad_sketch"
    assert "sketch_name" not in out[0]["args"]


def test_sanitize_actions_strips_import_svg_sketch_for_raster_png() -> None:
    from fixture_cad.chat import sanitize_actions
    from fixture_cad.tools.registry import ToolRegistry

    reg = ToolRegistry.load()
    ctx = _raster_context("image/png")
    actions, warnings = sanitize_actions(
        _import_svg_sketch_actions(),
        app="freecad",
        registry=reg,
        context=ctx,
    )
    assert actions == []
    assert any("import_svg_sketch" in w for w in warnings)


def test_sanitize_actions_strips_import_svg_sketch_for_raster_jpeg() -> None:
    from fixture_cad.chat import sanitize_actions
    from fixture_cad.tools.registry import ToolRegistry

    reg = ToolRegistry.load()
    ctx = _raster_context("image/jpeg")
    actions, warnings = sanitize_actions(
        _import_svg_sketch_actions(),
        app="freecad",
        registry=reg,
        context=ctx,
    )
    assert actions == []
    assert any("import_svg_sketch" in w for w in warnings)


def test_sanitize_actions_allows_import_svg_sketch_for_svg() -> None:
    from fixture_cad.chat import sanitize_actions
    from fixture_cad.tools.registry import ToolRegistry

    reg = ToolRegistry.load()
    ctx = _svg_context()
    actions, warnings = sanitize_actions(
        _import_svg_sketch_actions(),
        app="freecad",
        registry=reg,
        context=ctx,
    )
    assert len(actions) == 1
    assert actions[0]["tool_name"] == "import_svg_sketch"
    assert warnings == []


def test_sanitize_actions_allows_import_svg_sketch_when_no_reference_image() -> None:
    from fixture_cad.chat import sanitize_actions
    from fixture_cad.tools.registry import ToolRegistry

    reg = ToolRegistry.load()
    actions, warnings = sanitize_actions(
        _import_svg_sketch_actions(),
        app="freecad",
        registry=reg,
        context={},
    )
    assert len(actions) == 1
    assert actions[0]["tool_name"] == "import_svg_sketch"
    assert warnings == []


def test_sanitize_actions_allows_import_svg_sketch_when_context_is_none() -> None:
    from fixture_cad.chat import sanitize_actions
    from fixture_cad.tools.registry import ToolRegistry

    reg = ToolRegistry.load()
    actions, warnings = sanitize_actions(
        _import_svg_sketch_actions(),
        app="freecad",
        registry=reg,
        context=None,
    )
    assert len(actions) == 1
    assert actions[0]["tool_name"] == "import_svg_sketch"
    assert warnings == []


def test_finalize_plan_strips_import_svg_sketch_for_raster_png() -> None:
    reg = ToolRegistry.load()
    plan = finalize_plan(
        reply_text="trace the outline",
        raw_actions=_import_svg_sketch_actions(),
        app="freecad",
        registry=reg,
        request_id="t",
        intent_status="supported",
        supported_scope={"summary": "Import the sketch."},
        context=_raster_context("image/png"),
    )
    assert not any(a.get("tool_name") == "import_svg_sketch" for a in plan["actions"])


def test_finalize_plan_allows_import_svg_sketch_for_svg() -> None:
    reg = ToolRegistry.load()
    plan = finalize_plan(
        reply_text="trace the outline",
        raw_actions=_import_svg_sketch_actions(),
        app="freecad",
        registry=reg,
        request_id="t",
        intent_status="supported",
        supported_scope={"summary": "Import the sketch."},
        context=_svg_context(),
    )
    assert any(a.get("tool_name") == "import_svg_sketch" for a in plan["actions"])


def test_finalize_plan_allows_import_svg_sketch_when_no_reference_image() -> None:
    reg = ToolRegistry.load()
    plan = finalize_plan(
        reply_text="import the sketch",
        raw_actions=_import_svg_sketch_actions(),
        app="freecad",
        registry=reg,
        request_id="t",
        intent_status="supported",
        supported_scope={"summary": "Import the sketch."},
    )
    assert any(a.get("tool_name") == "import_svg_sketch" for a in plan["actions"])


def test_finalize_plan_strips_raster_import_but_keeps_other_tools() -> None:
    reg = ToolRegistry.load()
    actions = [
        * _import_svg_sketch_actions(),
        {
            "type": "tool_call",
            "tool_name": "create_parametric_box",
            "args": {"width": 10, "height": 10, "depth": 10},
        },
    ]
    plan = finalize_plan(
        reply_text="import sketch and make a box",
        raw_actions=actions,
        app="freecad",
        registry=reg,
        request_id="t",
        intent_status="supported",
        supported_scope={"summary": "Import sketch and create box."},
        context=_raster_context("image/png"),
    )
    tool_names = [a.get("tool_name") for a in plan["actions"] if a.get("type") == "tool_call"]
    assert "import_svg_sketch" not in tool_names
    assert "create_parametric_box" in tool_names


def _raster_context_no_media_type() -> dict:
    return {
        "extra": {
            "reference_image": {
                "file_name": "sketch.png",
                "byte_size": 1024,
            }
        }
    }


def test_align_tool_args_strips_import_svg_sketch_for_raster_media_type_absent() -> None:
    from fixture_cad.chat import align_tool_args

    ctx = _raster_context_no_media_type()
    out, _ = align_tool_args(_import_svg_sketch_actions(), context=ctx)
    assert out == []


def test_sanitize_actions_strips_import_svg_sketch_for_raster_media_type_absent() -> None:
    from fixture_cad.chat import sanitize_actions
    from fixture_cad.tools.registry import ToolRegistry

    reg = ToolRegistry.load()
    ctx = _raster_context_no_media_type()
    actions, warnings = sanitize_actions(
        _import_svg_sketch_actions(),
        app="freecad",
        registry=reg,
        context=ctx,
    )
    assert actions == []
    assert any("import_svg_sketch" in w for w in warnings)


def test_finalize_plan_strips_import_svg_sketch_for_raster_media_type_absent() -> None:
    reg = ToolRegistry.load()
    plan = finalize_plan(
        reply_text="trace the outline",
        raw_actions=_import_svg_sketch_actions(),
        app="freecad",
        registry=reg,
        request_id="t",
        intent_status="supported",
        supported_scope={"summary": "Import the sketch."},
        context=_raster_context_no_media_type(),
    )
    assert not any(a.get("tool_name") == "import_svg_sketch" for a in plan["actions"])


def _contains_tool(node: object, tool_name: str) -> bool:
    """True if a tool_call named ``tool_name`` hides anywhere in a nested tree."""
    if isinstance(node, dict):
        if node.get("type") == "tool_call" and node.get("tool_name") == tool_name:
            return True
        return any(_contains_tool(value, tool_name) for value in node.values())
    if isinstance(node, list):
        return any(_contains_tool(entry, tool_name) for entry in node)
    return False


def _contains_svg_import(node: object) -> bool:
    return _contains_tool(node, "import_svg_sketch")


def _nested_import_svg_sketch_actions() -> list:
    """An import hidden behind nesting plus an indirect, arg-embedded call."""
    return [
        {"type": "meta", "kind": "status", "text": "planning"},
        [
            _import_svg_sketch_actions("Nested"),
            {"type": "tool_call", "tool_name": "pad_sketch", "args": {"length": 5}},
        ],
        {
            "type": "meta",
            "kind": "progress",
            "text": "retry",
            "repair": {"action": _import_svg_sketch_actions("Indirect")[0]},
        },
    ]


def test_align_tool_args_strips_nested_and_indirect_svg_import_for_raster() -> None:
    from fixture_cad.chat import align_tool_args

    out, warnings = align_tool_args(
        _nested_import_svg_sketch_actions(),
        context=_raster_context("image/png"),
    )
    assert not _contains_svg_import(out)
    assert _contains_tool(out, "pad_sketch")
    assert any("import_svg_sketch" in w for w in warnings)


def test_sanitize_actions_strips_nested_and_indirect_svg_import_for_raster() -> None:
    reg = ToolRegistry.load()
    actions, warnings = sanitize_actions(
        _nested_import_svg_sketch_actions(),
        app="freecad",
        registry=reg,
        context=_raster_context("image/png"),
    )
    assert not _contains_svg_import(actions)
    assert any("import_svg_sketch" in w for w in warnings)


def test_finalize_plan_strips_nested_and_indirect_svg_import_for_raster() -> None:
    reg = ToolRegistry.load()
    plan = finalize_plan(
        reply_text="trace the outline",
        raw_actions=_nested_import_svg_sketch_actions(),
        app="freecad",
        registry=reg,
        request_id="t",
        intent_status="supported",
        supported_scope={"summary": "Import the sketch."},
        context=_raster_context("image/png"),
    )
    assert not _contains_svg_import(plan["actions"])


def test_align_tool_args_allows_genuine_svg_reference() -> None:
    from fixture_cad.chat import align_tool_args

    actions = [
        *_import_svg_sketch_actions("Outline"),
        {"type": "tool_call", "tool_name": "pad_sketch", "args": {"length": 8}},
    ]
    out, _ = align_tool_args(actions, context=_svg_context())
    assert _contains_svg_import(out)
    assert out[1]["args"]["sketch_name"] == "Outline"
