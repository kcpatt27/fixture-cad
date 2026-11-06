from __future__ import annotations

import json
import logging
import os
import re
import uuid
from typing import Any

from . import providers
from .config import settings
from .tools.registry import ToolDef, ToolRegistry

_LOG = logging.getLogger("fixture_cad")

INTENT_STATUSES = frozenset({"supported", "ambiguous", "partial", "unsupported"})
HISTORY_MAX_TURNS = 6
HISTORY_MAX_CHARS_PER_TURN = 600

_BOX_DIM_RE = re.compile(
    r"(?P<w>\d+(?:\.\d+)?)\s*[x×]\s*(?P<h>\d+(?:\.\d+)?)\s*[x×]\s*(?P<d>\d+(?:\.\d+)?)",
    re.IGNORECASE,
)

SYSTEM_TEMPLATE = """You are the Fixture planner for the CAD app "{app}".
Return a single JSON object with keys:
  - reply_text: string shown in the chat UI
  - actions: array of actions
  - intent_status: one of "supported", "ambiguous", "partial", "unsupported"
  - supported_scope: object with required "summary" and optional
    "remainder" / "clarifying_question"

Allowed action types ONLY:
  1) {{"type":"tool_call","tool_name":"...","args":{{...}}}}
  2) {{"type":"meta","kind":"ui_message"|"status"|"progress"|"need_confirm","text":"..."}}

Hard rules:
- Never emit type "python" or any executable code.
- Only use tools from the catalog below (exact names). Never invent tools.
- Prefer tool_call for concrete CAD operations over reply-only answers.
- If the user asks to explain / describe selection, include tool_call explain_selection
  (reply_text may still summarize).
- For framing / zoom / fit view requests, use fit_view_selection.
- When the user asks what exists in the document or what an object is, prefer
  list_document_objects and/or get_object (FreeCAD) over inventing names/dims.
  These tools are read-only; emit no mutating tools on inspect-only turns.
- If context.extra.inspection is present (post-Apply verify), ground reply_text
  in those facts: summarize what was created, note remainder vs prior scope,
  and offer one bounded next step. Prefer reply-only or auto read-only tools;
  do not invent geometry that contradicts inspection facts.
- Dimension convention for boxes: phrases like "40x40x10mm" or "W x H x D" map to
  create_parametric_box args as width=first, height=second, depth=third
  (example: 40x40x10 -> width=40, height=40, depth=10). Enclosure shells use the
  same mapping (example: 100x60x25 -> width=100, height=60, depth=25). Never swap
  height and depth: the middle number is height, the last is depth.
- Cylinders use create_parametric_cylinder with radius and height in mm.
- Placement uses transform_placement with absolute x/y/z in mm and rx/ry/rz in
  degrees; omit an axis to leave the current value.
- Boolean cut is base_name minus tool_name (boolean_cut); fuse unions them
  (boolean_fuse). Both create a new result object and keep base and tool.
- For permission=confirm tools the harness will ensure a need_confirm meta exists;
  you should still emit need_confirm with a short human question when possible.
- Never call tools that are not in this app's catalog (e.g. Blender clean_mesh from FreeCAD,
  or FreeCAD create_parametric_box from Blender). If the user asks for an unavailable
  operation, apologize in reply_text with empty actions (or only meta ui_message).

Capability classification:
- "supported": the request is fully covered by catalog tools. Emit those tools.
- "ambiguous": geometry-defining choices are missing. Ask one clarifying_question.
  Emit NO tool_call actions.
- "partial": only a useful subset is possible. Set supported_scope.summary to that
  subset, supported_scope.remainder to what remains unsupported, emit only the
  subset tools, and include need_confirm. Never claim the partial result fulfills
  the full original request. Use partial only when the user invites a reduced
  start (for example "start with anything you can", "lid later", "box shell first").
  A bare request for a full interlocking hinge without that invitation is
  ambiguous or unsupported — do not invent a plate and call it a hinge.
- "unsupported": nothing useful/safe can be done with current tools. Emit NO
  tool_call actions. Explain the limit honestly.

Concept briefs / ideation (text-only; no new geometry kernels):
- Vague product wants without sizes or use (e.g. "desk organizer for pens",
  "something cool") → "ambiguous". Ask one clarifying_question. Emit NO tools.
  In reply_text you may sketch an honest brief (object class, target mm if known,
  fabrication print/display/unknown, must-haves, out-of-scope) — never invent
  dims the user did not give.
- Boxy / printable shells with pinned mm and an invitation to start without the
  full product (e.g. enclosure ~100x60x25, "lid later") → "partial". Prefer
  create_parametric_box with width=100, height=60, depth=25 for that example;
  remainder must name deferred work (lid, internals, organic form). Include
  need_confirm. reply_text must also mention the deferred lid/remainder so the
  user sees it — do not omit "lid" from reply_text when the user said "lid later".
- Generative design, topology optimization, "bone chair", load-path chairs, or
  FEM-driven organics → "unsupported". Emit NO tools. Do not fake an organic
  solid with boxes/cylinders unless the user explicitly invites a reduced mockup.
- Organic mesh / blob / sculpture asked in FreeCAD → "ambiguous" or
  "unsupported"; suggest Blender for mesh viz; do not invent FreeCAD mesh tools.
- Mechanical / printable parametric → FreeCAD tools; never claim generative CAD.

Reference attachments / 2D import / STL export (Slice B):
- context.extra.reference_image is user-attached METADATA only (file_name,
  media_type, byte_size, optional width_px/height_px). Never claim to see image
  contents; there is no vision lane yet. Absolute paths and bytes never appear.
- If a reference would help and none is attached, emit attach_reference_image
  (auto). That tool never mutates geometry.
- Vague "build from this sketch/image" without sizes or media_type → "ambiguous";
  ask one clarifying_question; emit NO mutating tools. attach_reference_image
  alone is allowed when useful.
- import_svg_sketch ONLY when attached media_type is "image/svg+xml". It has no
  path arg; the client supplies the SVG at Apply. Chain with pad_sketch when the
  user gives a pad length. Units mm. When chaining, set import_svg_sketch.name
  and pad_sketch.sketch_name to the SAME string (e.g. both "Outline"); pad_sketch
  requires sketch_name — never omit it.
- export_stl ONLY when solids exist (selection, document context, or history of
  a created solid). path is a filename only (e.g. remote.stl); never directories
  or separators. Prefer naming the objects when known.
- Raster references (png/jpeg/webp/bmp) inform the brief only until vision exists;
  do not invent geometry from them.
- FAIL-CLOSED: if context.extra.reference_image is present and its media_type is
  anything other than "image/svg+xml", import_svg_sketch must never appear in the
  action sequence — not directly, not indirectly, and not after any alignment or
  repair pass. Strip it and record a warning. SVG assets remain fully allowed.

Prior conversation turns may appear in history. Treat the latest message as the
current user turn and use history only for continuity (for example accepting a
previously offered partial scope).

Tool catalog for {app}:
{tools_json}
"""


_WORD_RE = re.compile(r"[a-z0-9]{3,}")


def _tool_keywords(tool: ToolDef) -> set[str]:
    keywords: set[str] = set(tool.name.lower().split("_"))
    keywords.update(_WORD_RE.findall(tool.description.lower()))
    properties = tool.args_schema.get("properties")
    if isinstance(properties, dict):
        for prop in properties:
            keywords.update(str(prop).lower().split("_"))
    return keywords


def select_tools_for_prompt(
    message: str,
    tools: list[ToolDef],
    limit: int,
) -> list[ToolDef]:
    """Keyword rerank (freecad-ai pattern): top-N tools for this message.

    Name-token hits weigh 3x description/arg hits. When nothing matches the
    catalog is returned unchanged, so unusual wording never blinds the model.
    """
    if limit <= 0 or not message:
        return tools
    words = set(_WORD_RE.findall(message.lower()))
    scored: list[tuple[int, ToolDef]] = []
    for tool in tools:
        name_hits = len(words & set(tool.name.lower().split("_")))
        score = 3 * name_hits + len(words & _tool_keywords(tool))
        if score > 0:
            scored.append((score, tool))
    if not scored:
        return tools
    scored.sort(key=lambda pair: (-pair[0], pair[1].name))
    return [tool for _, tool in scored[:limit]]


def build_system_prompt(
    app: str,
    registry: ToolRegistry,
    *,
    message: str | None = None,
) -> str:
    tools = registry.for_app(app)
    if message and settings.tool_rerank_limit > 0:
        tools = select_tools_for_prompt(message, tools, settings.tool_rerank_limit)
    payload = [t.for_prompt() for t in tools]
    return SYSTEM_TEMPLATE.format(app=app, tools_json=json.dumps(payload, indent=2))


def _normalize_history(history: Any) -> list[dict[str, str]]:
    if not isinstance(history, list):
        return []
    clean: list[dict[str, str]] = []
    for item in history[-HISTORY_MAX_TURNS:]:
        if not isinstance(item, dict):
            continue
        role = item.get("role")
        text = item.get("text")
        if role not in {"user", "assistant"} or not isinstance(text, str):
            continue
        clipped = text.strip()
        if not clipped:
            continue
        if len(clipped) > HISTORY_MAX_CHARS_PER_TURN:
            clipped = clipped[: HISTORY_MAX_CHARS_PER_TURN - 1] + "…"
        clean.append({"role": role, "text": clipped})
    return clean[-HISTORY_MAX_TURNS:]


def build_user_prompt(
    message: str,
    context: dict[str, Any],
    mode: str,
    history: list[dict[str, str]] | None = None,
) -> str:
    turns = _normalize_history(history)
    history_block = json.dumps(turns, ensure_ascii=False) if turns else "[]"
    return (
        f"mode: {mode}\n"
        f"history: {history_block}\n"
        f"message: {message}\n"
        f"context: {json.dumps(context, ensure_ascii=False)}"
    )


def _get_reference_image(context: dict[str, Any] | None) -> dict[str, Any] | None:
    if not isinstance(context, dict):
        return None
    extra = context.get("extra") if isinstance(context.get("extra"), dict) else None
    if extra is None:
        return None
    ref = extra.get("reference_image")
    if isinstance(ref, dict):
        return ref
    return None


def _is_raster_reference(ref_image: dict[str, Any] | None) -> bool:
    if ref_image is None:
        return False
    media_type = ref_image.get("media_type")
    if not isinstance(media_type, str):
        return True
    return media_type not in {"image/svg+xml"}


def _strip_raster_svg_imports(node: Any) -> tuple[Any, int]:
    """Recursively remove every SVG-import tool_call from a nested action tree.

    Fail-closed guard used whenever the attached reference image is raster or has
    an unusable/non-SVG media type. Walks both lists and dicts so that an
    ``import_svg_sketch`` call cannot survive by hiding behind a nested wrapper,
    an indirect call, or a repair re-emission. Returns a rebuilt structure plus
    the number of dropped calls; never mutates the input.
    """
    if isinstance(node, list):
        dropped = 0
        rebuilt: list[Any] = []
        for entry in node:
            cleaned, count = _strip_raster_svg_imports(entry)
            dropped += count
            if cleaned is not None:
                rebuilt.append(cleaned)
        return rebuilt, dropped
    if isinstance(node, dict):
        if node.get("type") == "tool_call" and node.get("tool_name") == "import_svg_sketch":
            return None, 1
        dropped = 0
        rebuilt_dict: dict[Any, Any] = {}
        for key, value in node.items():
            cleaned, count = _strip_raster_svg_imports(value)
            dropped += count
            rebuilt_dict[key] = cleaned
        return rebuilt_dict, dropped
    return node, 0


def align_tool_args(
    actions: Any,
    *,
    message: str = "",
    context: dict[str, Any] | None = None,
) -> tuple[list[Any], list[str]]:
    """Deterministic fixes for known model arg slips (axis-swap, pad sketch_name).

    Returns (aligned_actions, warnings).
    """
    warnings: list[str] = []
    if not isinstance(actions, list):
        return actions, ["actions was not a list"]

    dims = None
    match = _BOX_DIM_RE.search(message or "")
    if match:
        dims = (
            float(match.group("w")),
            float(match.group("h")),
            float(match.group("d")),
        )

    ref_image = _get_reference_image(context)
    raster_only = _is_raster_reference(ref_image)
    if raster_only:
        # Fail-closed before any other alignment: no raster bytes may reach the
        # SVG pipeline, even via a nested/indirect import_svg_sketch call.
        actions, dropped = _strip_raster_svg_imports(actions)
        if dropped:
            warnings.append("stripped import_svg_sketch: non-SVG reference image")

    last_import_name: str | None = None
    out: list[Any] = []
    for item in actions:
        if not isinstance(item, dict) or item.get("type") != "tool_call":
            out.append(item)
            continue
        name = item.get("tool_name")
        args = item.get("args") if isinstance(item.get("args"), dict) else {}
        args = dict(args)

        if name == "import_svg_sketch":
            last_import_name = str(args.get("name") or "ImportedSketch").strip() or "ImportedSketch"
            if "name" not in args:
                args["name"] = last_import_name
            out.append({**item, "args": args})
            continue

        if name == "pad_sketch":
            if "sketch_name" not in args and last_import_name:
                args["sketch_name"] = last_import_name
            out.append({**item, "args": args})
            continue

        if name == "create_parametric_box" and dims is not None:
            try:
                width = float(args["width"])
                height = float(args["height"])
                depth = float(args["depth"])
            except (KeyError, TypeError, ValueError):
                out.append(item)
                continue
            target_w, target_h, target_d = dims
            actual = sorted([width, height, depth])
            expected = sorted([target_w, target_h, target_d])
            if actual == expected and (width, height, depth) != (target_w, target_h, target_d):
                args["width"] = target_w
                args["height"] = target_h
                args["depth"] = target_d
                out.append({**item, "args": args})
                continue

        out.append(item if args == item.get("args") else {**item, "args": args})
    return out, warnings


def extract_json_object(text: str) -> dict[str, Any]:
    stripped = text.strip()
    fence = re.search(r"```(?:json)?\s*([\s\S]*?)```", stripped)
    if fence:
        stripped = fence.group(1).strip()
    try:
        data = json.loads(stripped)
        if isinstance(data, dict):
            return data
    except json.JSONDecodeError:
        pass
    start = stripped.find("{")
    end = stripped.rfind("}")
    if start >= 0 and end > start:
        data = json.loads(stripped[start : end + 1])
        if isinstance(data, dict):
            return data
    raise ValueError("model output was not a JSON object")


def sanitize_actions(
    actions: Any,
    *,
    app: str,
    registry: ToolRegistry,
    context: dict[str, Any] | None = None,
) -> tuple[list[dict[str, Any]], list[str]]:
    warnings: list[str] = []
    if not isinstance(actions, list):
        return [], ["actions was not a list"]

    raster_only = _is_raster_reference(_get_reference_image(context))
    if raster_only:
        # Defense-in-depth: strip nested/indirect SVG imports that slipped past
        # align_tool_args (for example a repair re-emission or a wrapper).
        actions, nested_dropped = _strip_raster_svg_imports(actions)
        if nested_dropped:
            warnings.append("stripped import_svg_sketch: non-SVG reference image")

    clean: list[dict[str, Any]] = []
    for item in actions:
        if not isinstance(item, dict):
            warnings.append("skipped non-object action")
            continue
        action_type = item.get("type")
        if action_type == "python":
            warnings.append("stripped forbidden python action")
            continue
        if action_type == "meta":
            kind = item.get("kind")
            text = item.get("text")
            if kind not in {"ui_message", "status", "progress", "need_confirm"}:
                warnings.append(f"skipped meta with bad kind: {kind}")
                continue
            if not isinstance(text, str):
                warnings.append("skipped meta without text")
                continue
            clean.append({"type": "meta", "kind": kind, "text": text})
            continue
        if action_type == "tool_call":
            name = item.get("tool_name")
            args = item.get("args") if isinstance(item.get("args"), dict) else {}
            if not isinstance(name, str) or not name:
                warnings.append("skipped tool_call without tool_name")
                continue
            if name == "import_svg_sketch" and raster_only:
                warnings.append("stripped import_svg_sketch: non-SVG reference image")
                continue
            tool = registry.get(name)
            if tool is None or app not in tool.apps:
                warnings.append(f"skipped unknown/unavailable tool: {name}")
                continue
            arg_errors = registry.validate_args(name, args)
            if arg_errors:
                warnings.append(f"skipped {name}: {'; '.join(arg_errors)}")
                continue
            clean.append({"type": "tool_call", "tool_name": name, "args": args})
            continue
        warnings.append(f"skipped unknown action type: {action_type}")
    return clean, warnings


def ensure_need_confirm(
    actions: list[dict[str, Any]],
    *,
    registry: ToolRegistry,
    force: bool = False,
) -> list[dict[str, Any]]:
    """Inject need_confirm meta before confirm-tier tool_calls if the model forgot."""
    has_confirm_meta = any(
        a.get("type") == "meta" and a.get("kind") == "need_confirm" for a in actions
    )
    confirm_tools = [
        a
        for a in actions
        if a.get("type") == "tool_call"
        and (
            force
            or (
                (tool := registry.get(str(a.get("tool_name") or ""))) is not None
                and tool.permission == "confirm"
            )
        )
    ]
    if not confirm_tools or has_confirm_meta:
        return actions

    names = ", ".join(str(t.get("tool_name")) for t in confirm_tools)
    injected = {
        "type": "meta",
        "kind": "need_confirm",
        "text": f"Apply these changes? ({names})",
    }
    out: list[dict[str, Any]] = []
    inserted = False
    first_confirm_name = confirm_tools[0].get("tool_name")
    for action in actions:
        if (
            not inserted
            and action.get("type") == "tool_call"
            and action.get("tool_name") == first_confirm_name
        ):
            out.append(injected)
            inserted = True
        out.append(action)
    if not inserted:
        out.insert(0, injected)
    return out


def _clip_scope_text(value: Any, *, limit: int) -> str | None:
    if not isinstance(value, str):
        return None
    text = value.strip()
    if not text:
        return None
    if len(text) > limit:
        return text[: limit - 1] + "…"
    return text


def normalize_intent_fields(
    *,
    intent_status: Any,
    supported_scope: Any,
) -> tuple[str, dict[str, str], list[str]]:
    """Return (status, scope, warnings). Missing/invalid status fails closed to ambiguous."""
    warnings: list[str] = []
    status = intent_status if intent_status in INTENT_STATUSES else None
    if status is None:
        warnings.append("intent_status missing or invalid; fail-closed to ambiguous")
        status = "ambiguous"

    scope_in = supported_scope if isinstance(supported_scope, dict) else {}
    summary = _clip_scope_text(scope_in.get("summary"), limit=500)
    remainder = _clip_scope_text(scope_in.get("remainder"), limit=500)
    question = _clip_scope_text(scope_in.get("clarifying_question"), limit=300)

    if summary is None:
        if status == "ambiguous":
            summary = "I need a clarifying detail before proposing CAD changes."
        elif status == "unsupported":
            summary = "This request is outside the current tool catalog."
        elif status == "partial":
            summary = "Only a reduced subset of the request is supported."
        else:
            summary = "Proceed with the supported CAD tools for this request."
        warnings.append("supported_scope.summary missing; inserted default")

    scope: dict[str, str] = {"summary": summary}
    if remainder is not None:
        scope["remainder"] = remainder
    if question is not None:
        scope["clarifying_question"] = question

    if status == "ambiguous" and "clarifying_question" not in scope:
        scope["clarifying_question"] = (
            "Which supported next step should I take with the current tools?"
        )
        warnings.append("ambiguous missing clarifying_question; inserted default")

    return status, scope, warnings


def apply_intent_gate(
    actions: list[dict[str, Any]],
    *,
    intent_status: str,
    supported_scope: dict[str, str],
) -> tuple[str, dict[str, str], list[dict[str, Any]], list[str]]:
    """Enforce capability invariants on sanitized actions."""
    warnings: list[str] = []
    status = intent_status
    scope = dict(supported_scope)

    if status in {"ambiguous", "unsupported"}:
        kept = [a for a in actions if a.get("type") != "tool_call"]
        if len(kept) != len(actions):
            warnings.append(f"intent_gate: stripped tools for {status}")
        return status, scope, kept, warnings

    if status == "partial":
        has_tools = any(a.get("type") == "tool_call" for a in actions)
        has_remainder = bool(scope.get("remainder"))
        if not has_tools or not has_remainder:
            warnings.append(
                "intent_gate: partial missing tools or remainder; fail-closed to ambiguous"
            )
            status = "ambiguous"
            scope = {
                "summary": scope.get("summary")
                or "I need confirmation of a reduced scope before changing CAD.",
                "clarifying_question": scope.get("clarifying_question")
                or "Should I proceed with only the currently supported subset?",
            }
            if scope.get("remainder"):
                # keep remainder text for the user when available
                scope["remainder"] = scope["remainder"]
            kept = [a for a in actions if a.get("type") != "tool_call"]
            return status, scope, kept, warnings

    return status, scope, actions, warnings


def finalize_plan(
    *,
    reply_text: str,
    raw_actions: Any,
    app: str,
    registry: ToolRegistry,
    request_id: str,
    model_lane: str | None = None,
    model: str | None = None,
    intent_status: Any = None,
    supported_scope: Any = None,
    message: str | None = None,
    context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    status, scope, intent_warnings = normalize_intent_fields(
        intent_status=intent_status,
        supported_scope=supported_scope,
    )
    aligned, align_warnings = align_tool_args(
        raw_actions, message=message or "", context=context
    )
    actions, warnings = sanitize_actions(
        aligned, app=app, registry=registry, context=context
    )
    status, scope, actions, gate_warnings = apply_intent_gate(
        actions,
        intent_status=status,
        supported_scope=scope,
    )
    warnings.extend(align_warnings)
    warnings.extend(intent_warnings)
    warnings.extend(gate_warnings)

    force_confirm = status == "partial"
    actions = ensure_need_confirm(actions, registry=registry, force=force_confirm)

    if status == "ambiguous" and not reply_text.strip():
        reply_text = scope.get("clarifying_question") or scope["summary"]
    if status == "unsupported" and not reply_text.strip():
        reply_text = scope["summary"]
    # Keep deferred-lid wording visible when the user invited "lid later".
    if (
        status == "partial"
        and "lid later" in (message or "").lower()
        and "lid" not in reply_text.lower()
    ):
        reply_text = (reply_text.rstrip() + " Lid remains deferred.").strip()

    if warnings:
        actions.append(
            {
                "type": "meta",
                "kind": "status",
                "text": "sanitized: " + "; ".join(warnings[:5]),
            }
        )
    result: dict[str, Any] = {
        "reply_text": reply_text,
        "actions": actions,
        "intent_status": status,
        "supported_scope": scope,
        "request_id": request_id,
    }
    if model_lane is not None:
        result["model_lane"] = model_lane
    if model is not None:
        result["model"] = model
    return result


async def plan_chat(
    *,
    app: str,
    message: str,
    context: dict[str, Any],
    mode: str,
    registry: ToolRegistry,
    model_lane: str,
    model: str,
    fallback_models: list[str] | None = None,
    request_id: str | None = None,
    history: list[dict[str, str]] | None = None,
) -> dict[str, Any]:
    rid = request_id or str(uuid.uuid4())
    messages = [
        {
            "role": "system",
            "content": build_system_prompt(app, registry, message=message),
        },
        {
            "role": "user",
            "content": build_user_prompt(
                message,
                context,
                mode,
                history=history,
            ),
        },
    ]
    raw, used_model = await providers.chat_chain(
        messages,
        models=[model, *(fallback_models or [])],
        format_json=True,
    )
    if os.environ.get("FIXTURE_DEBUG_LOG"):
        _LOG.warning(
            "raw model text [request_id=%s model=%s]: %s",
            rid,
            used_model,
            raw,
        )
    try:
        parsed = extract_json_object(raw)
    except ValueError:
        return finalize_plan(
            reply_text="I could not parse a structured plan from the model. Try again.",
            raw_actions=[],
            app=app,
            registry=registry,
            request_id=rid,
            model_lane=model_lane,
            model=used_model,
            intent_status="ambiguous",
            supported_scope={
                "summary": "Model output was not a valid plan.",
                "clarifying_question": "Please restate the request so I can try again.",
            },
            message=message,
            context=context,
        )

    reply = parsed.get("reply_text")
    if not isinstance(reply, str):
        reply = ""
    return finalize_plan(
        reply_text=reply,
        raw_actions=parsed.get("actions"),
        app=app,
        registry=registry,
        request_id=rid,
        model_lane=model_lane,
        model=used_model,
        intent_status=parsed.get("intent_status"),
        supported_scope=parsed.get("supported_scope"),
        message=message,
        context=context,
    )


async def plan_repair(
    *,
    app: str,
    tool_name: str,
    error: dict[str, Any] | None,
    context: dict[str, Any] | None,
    registry: ToolRegistry,
    model_lane: str,
    model: str,
    fallback_models: list[str] | None = None,
    request_id: str | None = None,
) -> dict[str, Any]:
    detail = (error or {}).get("detail") or (error or {}).get("message") or "unknown error"
    message = (
        f"The tool `{tool_name}` failed.\n"
        f"Error: {detail}\n"
        "Propose a revised plan using only allowed tools. "
        "If you cannot repair, apologize in reply_text with empty actions."
    )
    return await plan_chat(
        app=app,
        message=message,
        context=context or {},
        mode="tool",
        registry=registry,
        model_lane=model_lane,
        model=model,
        fallback_models=fallback_models,
        request_id=request_id,
        history=None,
    )
