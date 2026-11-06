"""Client-deterministic post-Apply verification (FreeCAD)."""

from __future__ import annotations

import json
import re
from typing import Any

from .tools import get_runner
from .tools.get_object import collect_object_facts, format_object_facts
from .tools.list_document_objects import collect_document_objects, format_object_list

INSPECTION_MAX_CHARS = 2400

VERIFY_MESSAGE = (
    "Using the inspection facts in context.extra.inspection, summarize what was "
    "actually created, note any mismatch vs prior supported_scope remainder, and "
    "offer one bounded next step. Do not invent geometry that contradicts the facts."
)

# Prefer solid tip features over containers / sketches.
_TIP_PRIORITY = (
    "pocket",
    "pad",
    "fillet",
    "box",
    "body",
    "sketch",
)

_NAME_PATTERNS = (
    re.compile(r"created pocket (\S+)"),
    re.compile(r"created pad (\S+)"),
    re.compile(r"created PartDesign Body (\S+)"),
    re.compile(r"created sketch (\S+)"),
    re.compile(r"created (\S+) \d"),  # create_parametric_box
    re.compile(r"filleted (\S+) radius="),
    re.compile(r"→ (\S+)$"),
    re.compile(r"added rectangle to (\S+)"),
)


def parse_created_names(logs: list[str]) -> list[str]:
    """Extract object names mentioned in successful Apply logs (order preserved)."""
    names: list[str] = []
    seen: set[str] = set()
    for line in logs:
        if not line.startswith("ok:"):
            continue
        payload = line.split("->", 1)[-1].strip() if "->" in line else line
        for pattern in _NAME_PATTERNS:
            match = pattern.search(payload)
            if match:
                name = match.group(1).strip()
                if name and name not in seen:
                    seen.add(name)
                    names.append(name)
                break
    return names


def choose_tip_names(names: list[str]) -> list[str]:
    """Pick one tip name for selection/fit, preferring Pad/Pocket over Body."""
    if not names:
        return []
    lowered = [(n, n.lower()) for n in names]

    def score(item: tuple[str, str]) -> tuple[int, int]:
        name, low = item
        for idx, key in enumerate(_TIP_PRIORITY):
            if key in low:
                return (idx, -len(name))
        return (len(_TIP_PRIORITY), -len(name))

    best = sorted(lowered, key=score)[0][0]
    # Prefer the last occurrence of the best class in the batch.
    best_key = next((k for k in _TIP_PRIORITY if k in best.lower()), "")
    for name in reversed(names):
        if best_key and best_key in name.lower():
            return [name]
    return [names[-1]]


def select_objects_by_name(names: list[str]) -> list[str]:
    """Clear Gui selection and select named objects. Returns selected names."""
    if not names:
        return []
    try:
        import FreeCAD
        import FreeCADGui as Gui

        doc = FreeCAD.ActiveDocument
        if doc is None:
            return []
        Gui.Selection.clearSelection()
        selected: list[str] = []
        for name in names:
            obj = doc.getObject(name)
            if obj is None:
                continue
            Gui.Selection.addSelection(doc.Name, obj.Name)
            selected.append(obj.Name)
        return selected
    except Exception:  # noqa: BLE001
        return []


def _truncate_inspection(payload: dict[str, Any]) -> dict[str, Any]:
    raw = json.dumps(payload, ensure_ascii=True, separators=(",", ":"))
    if len(raw) <= INSPECTION_MAX_CHARS:
        return payload
    # Drop list entries first, then shrink detail text.
    slim = dict(payload)
    if isinstance(slim.get("objects"), list) and len(slim["objects"]) > 5:
        slim["objects"] = slim["objects"][:5]
        slim["truncated"] = True
    detail = slim.get("detail")
    if isinstance(detail, str) and len(detail) > 800:
        slim["detail"] = detail[:799] + "…"
    raw2 = json.dumps(slim, ensure_ascii=True, separators=(",", ":"))
    if len(raw2) <= INSPECTION_MAX_CHARS:
        return slim
    slim["detail"] = (str(slim.get("detail") or ""))[:400] + "…"
    slim.pop("objects", None)
    slim["truncated"] = True
    return slim


def gather_inspection_facts(tip_names: list[str]) -> dict[str, Any]:
    objects = collect_document_objects(max_objects=40)
    detail_parts: list[str] = []
    tip_facts: list[dict[str, Any]] = []
    for name in tip_names:
        facts = collect_object_facts(name)
        tip_facts.append(facts)
        detail_parts.append(format_object_facts(facts))
        # If tip is a Body, also inspect Tip feature when present.
        if facts.get("type") and "Body" in str(facts.get("type")):
            for line in facts.get("body") or []:
                if isinstance(line, str) and line.startswith("tip="):
                    tip_name = line.split("=", 1)[1].strip()
                    if tip_name and tip_name not in tip_names:
                        tip_facts.append(collect_object_facts(tip_name))
                        detail_parts.append(format_object_facts(tip_facts[-1]))
    payload = {
        "objects": objects,
        "tips": tip_names,
        "tip_facts": tip_facts,
        "detail": "\n".join(detail_parts),
        "object_list": format_object_list(objects),
    }
    return _truncate_inspection(payload)


def run_local_fit() -> str:
    runner = get_runner("fit_view_selection")
    if runner is None:
        return "fit_view_selection unavailable"
    try:
        return str(runner.run({}))
    except Exception as exc:  # noqa: BLE001
        return f"fit failed: {exc}"


def build_verify_transcript(inspection: dict[str, Any], *, fit_result: str) -> list[str]:
    """Deterministic chat lines shown before the grounded explain reply."""
    lines = [
        f"verify: fit -> {fit_result}",
        f"verify: tips -> {', '.join(inspection.get('tips') or []) or '(none)'}",
    ]
    detail = inspection.get("detail")
    if isinstance(detail, str) and detail.strip():
        for part in detail.strip().splitlines():
            lines.append(f"verify: {part}")
    obj_list = inspection.get("object_list")
    if isinstance(obj_list, str) and obj_list.strip() and obj_list != "No active document objects.":
        # Keep list short in transcript: first 8 lines.
        for part in obj_list.strip().splitlines()[:8]:
            lines.append(f"verify: list {part}")
    return lines


def format_verify_history_text(inspection: dict[str, Any], *, fit_result: str) -> str:
    """Compact assistant-history text for the follow-up explain turn."""
    tips = ", ".join(inspection.get("tips") or []) or "(none)"
    detail = str(inspection.get("detail") or "").strip()
    text = f"Applied successfully. Fit: {fit_result}. Tips: {tips}."
    if detail:
        text = f"{text} Facts:\n{detail}"
    if len(text) > 600:
        return text[:599] + "…"
    return text


def filter_verify_response(response: dict[str, Any]) -> dict[str, Any]:
    """Keep reply_text; drop confirm-tier / mutating tool staging from verify chat."""
    actions = response.get("actions") or []
    kept: list[dict[str, Any]] = []
    for action in actions:
        if not isinstance(action, dict):
            continue
        if action.get("type") == "meta":
            kept.append(action)
            continue
        if action.get("type") != "tool_call":
            continue
        tool_name = action.get("tool_name") or ""
        runner = get_runner(str(tool_name))
        if runner is None:
            continue
        if runner.permission == "confirm":
            continue
        # Allow only known auto read-only / view tools.
        if tool_name in {
            "explain_selection",
            "fit_view_selection",
            "list_document_objects",
            "get_object",
        }:
            kept.append(action)
    out = dict(response)
    out["actions"] = kept
    return out


def post_apply_verify(logs: list[str]) -> tuple[list[str], dict[str, Any]]:
    """
    After successful Apply: select tip, fit, inspect.

    Returns (transcript lines, inspection payload for context.extra).
    """
    if any(line.startswith("fail:") for line in logs):
        return [], {}
    names = parse_created_names(logs)
    tips = choose_tip_names(names)
    selected = select_objects_by_name(tips)
    fit_result = run_local_fit()
    inspection = gather_inspection_facts(selected or tips)
    inspection["selected"] = selected
    lines = build_verify_transcript(inspection, fit_result=fit_result)
    return lines, inspection
