"""Client-deterministic post-Apply verification (Blender)."""

from __future__ import annotations

import json
import re
from typing import Any

from .tools import get_runner

INSPECTION_MAX_CHARS = 2400

VERIFY_MESSAGE = (
    "Using the inspection facts in context.extra.inspection, summarize what was "
    "actually changed, note any mismatch vs prior supported_scope remainder, and "
    "offer one bounded next step. Do not invent geometry that contradicts the facts."
)

_CLEANED_RE = re.compile(
    r"cleaned (\S+) merged=(\d+)(?: merge_distance=([0-9.eE+-]+))?"
)


def parse_clean_mesh_result(logs: list[str]) -> dict[str, Any] | None:
    for line in logs:
        if not line.startswith("ok: clean_mesh"):
            continue
        payload = line.split("->", 1)[-1].strip() if "->" in line else line
        match = _CLEANED_RE.search(payload)
        if match:
            return {
                "name": match.group(1),
                "merged": int(match.group(2)),
                "merge_distance": float(match.group(3)) if match.group(3) else None,
            }
    return None


def gather_mesh_inspection(clean_info: dict[str, Any] | None = None) -> dict[str, Any]:
    import bpy

    from .tools.explain_selection import run as explain_run

    explain_text = explain_run({})
    selected: list[dict[str, Any]] = []
    for obj in bpy.context.selected_objects:
        entry: dict[str, Any] = {"name": obj.name, "type": obj.type}
        if obj.type == "MESH" and obj.data is not None:
            entry["vertices"] = len(obj.data.vertices)
            entry["polygons"] = len(obj.data.polygons)
        selected.append(entry)
    active = bpy.context.active_object
    payload: dict[str, Any] = {
        "selected": selected,
        "active": active.name if active else "",
        "explain": explain_text,
        "detail": explain_text,
    }
    if clean_info:
        payload["clean_mesh"] = clean_info
        tips = [clean_info["name"]]
        payload["tips"] = tips
    else:
        payload["tips"] = [e["name"] for e in selected[:3]]
    return _truncate_inspection(payload)


def _truncate_inspection(payload: dict[str, Any]) -> dict[str, Any]:
    raw = json.dumps(payload, ensure_ascii=True, separators=(",", ":"))
    if len(raw) <= INSPECTION_MAX_CHARS:
        return payload
    slim = dict(payload)
    detail = slim.get("detail")
    if isinstance(detail, str) and len(detail) > 600:
        slim["detail"] = detail[:599] + "…"
    slim["truncated"] = True
    return slim


def run_local_fit() -> str:
    runner = get_runner("fit_view_selection")
    if runner is None:
        return "fit_view_selection unavailable"
    try:
        return str(runner.run({}))
    except Exception as exc:  # noqa: BLE001
        return f"fit failed: {exc}"


def build_verify_transcript(inspection: dict[str, Any], *, fit_result: str) -> list[str]:
    lines = [
        f"verify: fit -> {fit_result}",
        f"verify: tips -> {', '.join(inspection.get('tips') or []) or '(none)'}",
    ]
    clean = inspection.get("clean_mesh")
    if isinstance(clean, dict):
        lines.append(
            f"verify: clean_mesh merged={clean.get('merged')} "
            f"on {clean.get('name')}"
        )
    detail = inspection.get("detail")
    if isinstance(detail, str) and detail.strip():
        for part in detail.strip().splitlines():
            lines.append(f"verify: {part}")
    return lines


def format_verify_history_text(inspection: dict[str, Any], *, fit_result: str) -> str:
    tips = ", ".join(inspection.get("tips") or []) or "(none)"
    detail = str(inspection.get("detail") or "").strip()
    text = f"Applied successfully. Fit: {fit_result}. Tips: {tips}."
    if detail:
        text = f"{text} Facts:\n{detail}"
    if len(text) > 600:
        return text[:599] + "…"
    return text


def filter_verify_response(response: dict[str, Any]) -> dict[str, Any]:
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
        if tool_name in {"explain_selection", "fit_view_selection"}:
            kept.append(action)
    out = dict(response)
    out["actions"] = kept
    return out


def post_apply_verify(logs: list[str]) -> tuple[list[str], dict[str, Any]]:
    if any(line.startswith("fail:") for line in logs):
        return [], {}
    clean_info = parse_clean_mesh_result(logs)
    # Prefer selecting the cleaned object for fit/explain.
    if clean_info:
        try:
            import bpy

            obj = bpy.data.objects.get(clean_info["name"])
            if obj is not None:
                bpy.ops.object.select_all(action="DESELECT")
                obj.select_set(True)
                bpy.context.view_layer.objects.active = obj
        except Exception:  # noqa: BLE001
            pass
    fit_result = run_local_fit()
    inspection = gather_mesh_inspection(clean_info)
    lines = build_verify_transcript(inspection, fit_result=fit_result)
    return lines, inspection
