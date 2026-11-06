"""Semantic scorer for the freecad-ai side of the head-to-head.

The competitor has a different tool catalog, no intent-status contract, and no
confirm tier we can compare, so this scores the checks that transfer:

- required/forbidden tools via a documented semantic mapping
- forbid_all_tools / require_any_tool
- required_reply_substr

Everything else (exact args, need_confirm, intent_status) is reported as
``n/a`` rather than counted as a miss. ``execute_code`` calls are recorded as a
codegen-fallback signal, never as a tool hit.

Usage:
  python -m competitors.freecad_ai_score --run benchmark/results/<UTC>
"""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path

from fixture_bench.cases import load_cases

# our tool -> acceptable competitor tool names (semantic, not exact)
DIRECT_MAP: dict[str, list[str]] = {
    "create_body": ["create_body"],
    "new_sketch": ["create_sketch"],
    "sketch_rectangle": ["create_sketch"],
    "pad_sketch": ["pad_sketch"],
    "pocket_sketch": ["pocket_sketch"],
    "add_fillet": ["fillet_edges"],
    "add_chamfer": ["chamfer_edges"],
    "transform_placement": ["transform_object"],
    "export_stl": ["export_model"],
    "fit_view_selection": ["zoom_object", "set_view"],
    "explain_selection": ["describe_model", "measure", "list_faces", "list_edges"],
    "list_document_objects": ["get_document_state", "list_documents"],
    "get_object": ["get_document_state", "measure", "describe_model", "list_faces"],
    # no FreeCAD-side equivalent in their catalog:
    "clean_mesh": [],
    "import_svg_sketch": [],
    "attach_reference_image": [],
}

# our tool -> (competitor tool, arg value matchers). Values are matched against
# any string argument whose key is in ARG_KEYS.
SPECIAL_MAP: dict[str, tuple[str, set[str], dict[str, set[str]]]] = {
    "create_parametric_box": ("create_primitive", {"shape_type"}, {"shape_type": {"box", "cube"}}),
    "create_parametric_cylinder": (
        "create_primitive",
        {"shape_type"},
        {"shape_type": {"cylinder", "cyl"}},
    ),
    "boolean_cut": ("boolean_operation", {"mode", "operation", "op", "type", "kind"}, {"mode": {"cut", "subtract", "difference"}, "operation": {"cut", "subtract", "difference"}, "op": {"cut"}, "type": {"cut"}, "kind": {"cut"}}),
    "boolean_fuse": ("boolean_operation", {"mode", "operation", "op", "type", "kind"}, {"mode": {"fuse", "union", "add"}, "operation": {"fuse", "union", "add"}, "op": {"fuse"}, "type": {"fuse"}, "kind": {"fuse"}}),
}


def _call_matches(call: dict, tool: str) -> bool:
    name = call.get("name", "")
    args = call.get("args") or {}
    if tool in DIRECT_MAP:
        return name in DIRECT_MAP[tool]
    if tool in SPECIAL_MAP:
        spec_name, _, value_sets = SPECIAL_MAP[tool]
        if name != spec_name:
            return False
        for key, allowed in value_sets.items():
            value = args.get(key)
            if isinstance(value, str) and value.strip().lower() in allowed:
                return True
        # fallback: scan all string args (their key naming may differ)
        for value in args.values():
            if isinstance(value, str) and value.strip().lower() in {
                v for allow in value_sets.values() for v in allow
            }:
                return True
        return False
    return False


def _mapped(tool: str) -> bool:
    return bool(DIRECT_MAP.get(tool)) or tool in SPECIAL_MAP


def score_case(case: dict, calls: list[dict], text: str) -> dict:
    expect = case.get("expect") or {}
    applicable = 0
    satisfied = 0
    notes: list[str] = []
    na_tools: list[str] = []
    used_execute_code = any(c.get("name") == "execute_code" for c in calls)
    names = [c.get("name", "") for c in calls]

    def check(ok: bool, note: str) -> None:
        nonlocal applicable, satisfied
        applicable += 1
        if ok:
            satisfied += 1
        else:
            notes.append(note)

    for tool in expect.get("required_tools") or []:
        if not _mapped(tool):
            na_tools.append(tool)
            continue
        check(any(_call_matches(c, tool) for c in calls), f"missing {tool}")

    for tool in expect.get("forbidden_tools") or []:
        if not _mapped(tool):
            continue
        check(not any(_call_matches(c, tool) for c in calls), f"forbidden {tool} present")

    if expect.get("forbid_all_tools"):
        check(not calls, "tools present but none expected")
    if expect.get("require_any_tool"):
        check(bool(calls), "no tool calls")

    for needle in expect.get("required_reply_substr") or []:
        check(needle.lower() in (text or "").lower(), f"missing reply substring {needle!r}")

    passed = applicable > 0 and satisfied == applicable
    return {
        "case_id": case["id"],
        "app": case["app"],
        "applicable": applicable,
        "satisfied": satisfied,
        "passed": passed,
        "na_tools": sorted(set(na_tools)),
        "used_execute_code": used_execute_code,
        "notes": notes,
        "tool_names": names,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", required=True, help="results dir with freecad_ai.jsonl")
    args = parser.parse_args(argv)

    run = Path(args.run)
    rows = [
        json.loads(line)
        for line in (run / "freecad_ai.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    cases = {c["id"]: c for c in load_cases()}

    scored: list[dict] = []
    for row in rows:
        case = cases.get(row["case_id"])
        if case is None or row.get("error"):
            continue
        result = score_case(case, row.get("tool_calls") or [], row.get("text") or "")
        result["model"] = row["model"]
        scored.append(result)

    by_model: dict[str, list[dict]] = defaultdict(list)
    for item in scored:
        by_model[item["model"]].append(item)

    print("| model | comparable cases | semantic pass | applicable checks | no-check cases | n/a tool cases | execute_code |")
    print("|---|---:|---:|---:|---:|---:|---:|")
    for model, items in sorted(by_model.items()):
        comparable = [i for i in items if i["applicable"] > 0]
        passes = sum(1 for i in comparable if i["passed"])
        applic = sum(i["applicable"] for i in comparable)
        na = sum(1 for i in items if i["na_tools"])
        no_check = len(items) - len(comparable)
        code = sum(1 for i in items if i["used_execute_code"])
        pct = 100.0 * passes / len(comparable) if comparable else 0.0
        print(
            f"| `{model}` | {len(comparable)} | {pct:.1f}% ({passes}) | {applic} | "
            f"{no_check} | {na} | {code} |"
        )

    out = run / "freecad_ai_scored.jsonl"
    with out.open("w", encoding="utf-8") as handle:
        for item in scored:
            handle.write(json.dumps(item, ensure_ascii=False) + "\n")
    print(f"\nsaved -> {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())