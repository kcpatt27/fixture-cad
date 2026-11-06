from __future__ import annotations

import time
from typing import Any

from fixture_cad import providers
from fixture_cad.chat import (
    build_system_prompt,
    build_user_prompt,
    extract_json_object,
    finalize_plan,
)
from fixture_cad.tools.registry import ToolRegistry

from .score import score_case


async def run_case(
    case: dict[str, Any],
    *,
    model: str,
    registry: ToolRegistry,
) -> dict[str, Any]:
    """Run one benchmark case against a specific Ollama model (same postprocess as harness)."""
    started = time.perf_counter()
    raw_text = ""
    raw_parsed: dict[str, Any] | None = None
    sanitized: dict[str, Any] = {"reply_text": "", "actions": []}
    warnings: list[str] = []
    error: str | None = None

    try:
        messages = [
            {
                "role": "system",
                "content": build_system_prompt(
                    case["app"], registry, message=case["message"]
                ),
            },
            {
                "role": "user",
                "content": build_user_prompt(
                    case["message"],
                    case.get("context") or {},
                    case.get("mode") or "chat",
                    history=case.get("history") or [],
                ),
            },
        ]
        raw_text = await providers.chat(messages, model=model, format_json=True)
        try:
            raw_parsed = extract_json_object(raw_text)
        except ValueError:
            raw_parsed = None
            sanitized = {
                "reply_text": "",
                "actions": [
                    {"type": "meta", "kind": "status", "text": "model_parse_failed"}
                ],
                "intent_status": "ambiguous",
                "supported_scope": {
                    "summary": "Could not parse a structured plan.",
                    "clarifying_question": "Please rephrase the request.",
                },
            }
        else:
            reply = raw_parsed.get("reply_text")
            if not isinstance(reply, str):
                reply = ""
            sanitized = finalize_plan(
                reply_text=reply,
                raw_actions=raw_parsed.get("actions"),
                app=case["app"],
                registry=registry,
                request_id="bench",
                intent_status=raw_parsed.get("intent_status"),
                supported_scope=raw_parsed.get("supported_scope"),
                message=case.get("message") or "",
            )
            # Surface sanitize notes from status meta for the scorer
            for action in sanitized.get("actions") or []:
                if (
                    action.get("type") == "meta"
                    and action.get("kind") == "status"
                    and str(action.get("text", "")).startswith("sanitized:")
                ):
                    warnings.append(str(action.get("text")))
    except Exception as exc:  # noqa: BLE001
        error = str(exc)

    latency = time.perf_counter() - started
    scored = score_case(
        case=case,
        raw_parsed=raw_parsed,
        raw_text=raw_text,
        sanitized=sanitized,
        sanitize_warnings=warnings,
        latency_s=latency,
        error=error,
    )
    scored["model"] = model
    return scored
