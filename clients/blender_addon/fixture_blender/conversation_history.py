"""Bounded conversation turns for chat history payloads (pure helpers)."""

from __future__ import annotations

from typing import Any

HISTORY_MAX_TURNS = 6
HISTORY_MAX_CHARS_PER_TURN = 600
HISTORY_MAX_TOTAL_CHARS = 2400

_INTENT_LABELS = {
    "supported": "supported",
    "ambiguous": "ambiguous — needs clarification",
    "partial": "partial — reduced scope",
    "unsupported": "unsupported",
}


def clip_turn_text(text: str) -> str:
    clipped = (text or "").strip()
    if not clipped:
        return ""
    if len(clipped) > HISTORY_MAX_CHARS_PER_TURN:
        return clipped[: HISTORY_MAX_CHARS_PER_TURN - 1] + "…"
    return clipped


def append_structured_turn(
    turns: list[dict[str, str]],
    *,
    role: str,
    text: str,
) -> list[dict[str, str]]:
    """Append a user/assistant turn and compact to N1 budgets."""
    if role not in {"user", "assistant"}:
        return list(turns)
    clipped = clip_turn_text(text)
    if not clipped:
        return list(turns)
    next_turns = list(turns)
    next_turns.append({"role": role, "text": clipped})
    return compact_history(next_turns)


def compact_history(turns: list[dict[str, str]]) -> list[dict[str, str]]:
    """Keep at most six turns and ≤2400 total chars, dropping oldest first.

    When dropping for the character budget, preserve the latest clarification
    pair (last user + last assistant) when both exist.
    """
    clean: list[dict[str, str]] = []
    for item in turns:
        if not isinstance(item, dict):
            continue
        role = item.get("role")
        text = item.get("text")
        if role not in {"user", "assistant"} or not isinstance(text, str):
            continue
        clipped = clip_turn_text(text)
        if not clipped:
            continue
        clean.append({"role": role, "text": clipped})

    clean = clean[-HISTORY_MAX_TURNS:]
    total = sum(len(t["text"]) for t in clean)
    if total <= HISTORY_MAX_TOTAL_CHARS:
        return clean

    preserve: list[dict[str, str]] = []
    if len(clean) >= 2 and clean[-1]["role"] == "assistant" and clean[-2]["role"] == "user":
        preserve = [clean[-2], clean[-1]]
        head = clean[:-2]
    else:
        head = clean

    while head and sum(len(t["text"]) for t in head) + sum(len(t["text"]) for t in preserve) > HISTORY_MAX_TOTAL_CHARS:
        head.pop(0)

    merged = head + preserve
    while len(merged) > HISTORY_MAX_TURNS:
        if len(merged) > len(preserve):
            merged.pop(0)
        else:
            break
    while merged and sum(len(t["text"]) for t in merged) > HISTORY_MAX_TOTAL_CHARS:
        if len(merged) > len(preserve):
            merged.pop(0)
        else:
            oldest = merged[0]
            budget = HISTORY_MAX_TOTAL_CHARS - sum(len(t["text"]) for t in merged[1:])
            if budget < 1:
                merged.pop(0)
            else:
                oldest["text"] = clip_turn_text(oldest["text"][:budget])
                break
    return merged


def history_for_request(turns: list[dict[str, str]]) -> list[dict[str, str]]:
    """Prior turns only (current message is sent separately)."""
    return compact_history(turns)


def format_intent_presentation(
    intent_status: Any,
    supported_scope: Any,
) -> list[str]:
    """Compact transcript lines for intent / scope (not stored in history)."""
    lines: list[str] = []
    status = intent_status if intent_status in _INTENT_LABELS else None
    if status:
        lines.append(f"intent: {_INTENT_LABELS[status]}")
    scope = supported_scope if isinstance(supported_scope, dict) else {}
    summary = scope.get("summary")
    if isinstance(summary, str) and summary.strip():
        lines.append(f"scope: {summary.strip()}")
    remainder = scope.get("remainder")
    if isinstance(remainder, str) and remainder.strip():
        lines.append(f"remainder: {remainder.strip()}")
    clarify = scope.get("clarifying_question")
    if isinstance(clarify, str) and clarify.strip():
        lines.append(f"clarify: {clarify.strip()}")
    return lines


def pending_scope_summary(
    intent_status: Any,
    supported_scope: Any,
    tools_summary: str,
) -> str:
    """Pending panel text preferring supported_scope.summary when present."""
    scope = supported_scope if isinstance(supported_scope, dict) else {}
    summary = scope.get("summary")
    parts: list[str] = []
    if intent_status == "partial":
        parts.append("Partial scope")
    if isinstance(summary, str) and summary.strip():
        parts.append(summary.strip())
    remainder = scope.get("remainder")
    if isinstance(remainder, str) and remainder.strip():
        parts.append(f"Not included: {remainder.strip()}")
    if tools_summary:
        parts.append(f"Tools: {tools_summary}")
    return " — ".join(parts) if parts else tools_summary
