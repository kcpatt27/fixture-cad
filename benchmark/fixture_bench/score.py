"""Score Path A planner cases against expects (tools, intent, reply/scope)."""

from __future__ import annotations

from typing import Any


def _tool_calls(actions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [a for a in actions if a.get("type") == "tool_call"]


def _metas(actions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [a for a in actions if a.get("type") == "meta"]


def _get_arg(tool_calls: list[dict[str, Any]], tool: str, arg: str) -> Any:
    for call in tool_calls:
        if call.get("tool_name") == tool:
            args = call.get("args") or {}
            if arg in args:
                return args[arg]
    return None


def _check_op(actual: Any, op: str, expected: Any) -> bool:
    if actual is None:
        return False
    if op == "eq":
        try:
            return float(actual) == float(expected) if isinstance(expected, (int, float)) else actual == expected
        except (TypeError, ValueError):
            return actual == expected
    if op == "approx":
        try:
            return abs(float(actual) - float(expected)) <= 1e-6
        except (TypeError, ValueError):
            return False
    if op == "gte":
        return float(actual) >= float(expected)
    if op == "lte":
        return float(actual) <= float(expected)
    if op == "in":
        return actual in expected
    if op == "contains":
        return expected in actual
    return False


def _normalize_intent_expect(raw: Any) -> list[str] | None:
    if raw is None:
        return None
    if isinstance(raw, str):
        return [raw]
    if isinstance(raw, list) and all(isinstance(x, str) for x in raw):
        return list(raw)
    return None


def _scope_blob(scope: Any) -> str:
    if not isinstance(scope, dict):
        return ""
    parts = [
        str(scope.get("summary") or ""),
        str(scope.get("remainder") or ""),
        str(scope.get("clarifying_question") or ""),
    ]
    return " ".join(parts).lower()


def score_case(
    *,
    case: dict[str, Any],
    raw_parsed: dict[str, Any] | None,
    raw_text: str,
    sanitized: dict[str, Any],
    sanitize_warnings: list[str],
    latency_s: float,
    error: str | None = None,
) -> dict[str, Any]:
    expect = case.get("expect") or {}
    checks: dict[str, bool] = {}
    notes: list[str] = []

    intent_expect = _normalize_intent_expect(expect.get("intent_status"))
    forbid_all = bool(expect.get("forbid_all_tools"))
    reply_substr = [s.lower() for s in (expect.get("required_reply_substr") or []) if isinstance(s, str)]
    scope_substr = [s.lower() for s in (expect.get("required_scope_substr") or []) if isinstance(s, str)]
    require_confirm = bool(expect.get("require_need_confirm"))
    require_any_tool = bool(expect.get("require_any_tool"))

    optional_keys = []
    if intent_expect is not None:
        optional_keys.append("intent_ok")
    if forbid_all:
        optional_keys.append("forbid_all_tools")
    if require_any_tool:
        optional_keys.append("any_tool")
    if reply_substr:
        optional_keys.append("reply_substr")
    if scope_substr:
        optional_keys.append("scope_substr")

    weights = {
        "parse_ok": 1.0,
        "no_python": 1.0,
        "valid_actions": 1.0,
        "tool_hit": 1.5,
        "tool_miss": 1.0,
        "args_ok": 1.5,
        "need_confirm": 1.0 if require_confirm else 0.0,
        "intent_ok": 1.0 if intent_expect is not None else 0.0,
        "forbid_all_tools": 1.0 if forbid_all else 0.0,
        "any_tool": 1.0 if require_any_tool else 0.0,
        "reply_substr": 1.0 if reply_substr else 0.0,
        "scope_substr": 1.0 if scope_substr else 0.0,
    }
    max_score = sum(weights.values())

    if error:
        for key in (
            "parse_ok",
            "no_python",
            "valid_actions",
            "tool_hit",
            "tool_miss",
            "args_ok",
            "need_confirm",
            *optional_keys,
        ):
            checks[key] = False
        return {
            "case_id": case["id"],
            "app": case["app"],
            "checks": checks,
            "score": 0.0,
            "max_score": round(max_score, 2),
            "latency_s": latency_s,
            "error": error,
            "notes": [error],
            "reply_text": "",
            "actions": [],
            "raw_preview": raw_text[:400],
        }

    parse_ok = raw_parsed is not None and isinstance(raw_parsed.get("actions"), list)
    # Soft harness fallback still counts as parse fail for benchmarking
    if sanitized.get("actions") and any(
        a.get("type") == "meta" and a.get("text") == "model_parse_failed"
        for a in sanitized.get("actions") or []
    ):
        parse_ok = False
    checks["parse_ok"] = parse_ok

    raw_actions = (raw_parsed or {}).get("actions") if isinstance(raw_parsed, dict) else None
    if not isinstance(raw_actions, list):
        raw_actions = []
    no_python = not any(
        isinstance(a, dict) and a.get("type") == "python" for a in raw_actions
    )
    checks["no_python"] = no_python
    if not no_python:
        notes.append("raw contained python action")

    san_actions = sanitized.get("actions") or []
    well_typed = all(
        isinstance(a, dict) and a.get("type") in {"tool_call", "meta"} for a in san_actions
    )
    checks["valid_actions"] = well_typed and parse_ok
    if sanitize_warnings:
        notes.extend(sanitize_warnings[:3])

    tools_present = {c.get("tool_name") for c in _tool_calls(san_actions)}
    raw_tools = {
        a.get("tool_name")
        for a in raw_actions
        if isinstance(a, dict) and a.get("type") == "tool_call"
    }
    required = list(expect.get("required_tools") or [])
    forbidden = list(expect.get("forbidden_tools") or [])
    tool_hit = all(t in tools_present for t in required) if required else True
    tool_miss = not any(t in (tools_present | raw_tools) for t in forbidden) if forbidden else True
    checks["tool_hit"] = tool_hit and parse_ok
    checks["tool_miss"] = tool_miss and parse_ok
    if not tool_hit:
        notes.append(f"missing tools {required}; got {sorted(x for x in tools_present if x)}")
    if not tool_miss:
        notes.append(
            f"forbidden tools among raw={sorted(x for x in raw_tools if x)} "
            f"san={sorted(x for x in tools_present if x)}"
        )

    arg_checks = list(expect.get("arg_checks") or [])
    args_ok = True
    for spec in arg_checks:
        actual = _get_arg(_tool_calls(san_actions), spec["tool"], spec["arg"])
        if not _check_op(actual, spec.get("op", "eq"), spec.get("value")):
            args_ok = False
            notes.append(
                f"arg fail {spec['tool']}.{spec['arg']} op={spec.get('op')} "
                f"expected={spec.get('value')} got={actual}"
            )
    checks["args_ok"] = args_ok and parse_ok

    has_confirm = any(m.get("kind") == "need_confirm" for m in _metas(san_actions))
    if require_confirm:
        checks["need_confirm"] = has_confirm and parse_ok
        if not has_confirm:
            notes.append("missing need_confirm meta")
    else:
        checks["need_confirm"] = True  # N/A → pass

    if intent_expect is not None:
        actual_intent = sanitized.get("intent_status")
        intent_ok = actual_intent in intent_expect and parse_ok
        checks["intent_ok"] = intent_ok
        if not intent_ok:
            notes.append(f"intent_status want {intent_expect}; got {actual_intent!r}")

    if forbid_all:
        no_tools = not tools_present and parse_ok
        checks["forbid_all_tools"] = no_tools
        if tools_present:
            notes.append(f"forbid_all_tools failed; got {sorted(x for x in tools_present if x)}")

    if require_any_tool:
        any_tool = bool(tools_present) and parse_ok
        checks["any_tool"] = any_tool
        if not tools_present:
            notes.append("require_any_tool failed; sanitized tools empty")

    reply_text = str(sanitized.get("reply_text") or "")
    reply_l = reply_text.lower()
    if reply_substr:
        reply_ok = all(s in reply_l for s in reply_substr) and parse_ok
        checks["reply_substr"] = reply_ok
        if not reply_ok:
            notes.append(f"missing reply substrings {reply_substr}")

    if scope_substr:
        blob = _scope_blob(sanitized.get("supported_scope"))
        scope_ok = all(s in blob for s in scope_substr) and parse_ok
        checks["scope_substr"] = scope_ok
        if not scope_ok:
            notes.append(f"missing scope substrings {scope_substr}; blob={blob[:120]!r}")

    score = sum(weights[k] for k, ok in checks.items() if ok and k in weights)

    return {
        "case_id": case["id"],
        "app": case["app"],
        "checks": checks,
        "score": round(score, 2),
        "max_score": round(max_score, 2),
        "latency_s": round(latency_s, 3),
        "error": None,
        "notes": notes,
        "reply_text": reply_text,
        "actions": san_actions,
        "raw_preview": raw_text[:400],
        "intent_status": sanitized.get("intent_status"),
        "supported_scope": sanitized.get("supported_scope"),
    }
