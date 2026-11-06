from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from . import config
from .client import HarnessClient
from .tools import get_runner


@dataclass
class PendingTool:
    tool_name: str
    args: dict[str, Any]
    permission: str
    model_lane: str = "accurate"
    request_id: str | None = None


def _contains_failure(logs: list[str]) -> bool:
    return any(line.startswith("fail:") for line in logs)


def _run_one(
    tool_name: str,
    args: dict[str, Any],
    *,
    client: HarnessClient,
    request_id: str | None,
    on_meta: Callable[[dict[str, Any]], None] | None,
    attempt: int,
    model_lane: str,
    pending_out: list[PendingTool] | None = None,
) -> list[str]:
    logs: list[str] = []
    runner = get_runner(tool_name)
    if runner is None:
        return [f"skip unknown tool: {tool_name}"]
    try:
        result = runner.run(args)
        logs.append(f"ok: {tool_name} -> {result}")
    except Exception as exc:  # noqa: BLE001
        logs.append(f"fail: {tool_name}: {exc}")
        if attempt >= 2:
            logs.append("repair exhausted")
            return logs
        from .context import build_context

        try:
            repaired = client.send_tool_result(
                {
                    "app": config.PROTOCOL_APP,
                    "version": config.CLIENT_VERSION,
                    "request_id": request_id,
                    "tool_name": tool_name,
                    "success": False,
                    "model_lane": model_lane,
                    "error": {
                        "code": "tool_exec_failed",
                        "message": str(exc),
                        "detail": str(exc),
                    },
                    "context": build_context(),
                    "attempt": attempt,
                }
            )
            more_logs, _ = prepare_actions(
                repaired,
                client=client,
                on_meta=on_meta,
                attempt=attempt + 1,
                defer_confirm=True,
                pending_out=pending_out,
            )
            logs.extend(more_logs)
        except Exception as repair_exc:  # noqa: BLE001
            logs.append(f"repair failed: {repair_exc}")
    return logs


def prepare_actions(
    response: dict[str, Any],
    *,
    client: HarnessClient | None = None,
    on_meta: Callable[[dict[str, Any]], None] | None = None,
    attempt: int = 1,
    defer_confirm: bool = True,
    pending_out: list[PendingTool] | None = None,
) -> tuple[list[str], list[PendingTool]]:
    logs: list[str] = []
    pending: list[PendingTool] = pending_out if pending_out is not None else []
    client = client or HarnessClient()
    actions = response.get("actions") or []
    request_id = response.get("request_id")
    model_lane = str(response.get("model_lane") or "accurate")

    for action in actions:
        if action.get("type") != "meta":
            continue
        if on_meta:
            on_meta(action)
        logs.append(f"meta:{action.get('kind')}: {action.get('text')}")

    for action in actions:
        if action.get("type") != "tool_call":
            continue
        tool_name = action.get("tool_name") or ""
        args = action.get("args") or {}
        runner = get_runner(tool_name)
        if runner is None:
            logs.append(f"skip unknown tool: {tool_name}")
            continue

        if runner.permission == "confirm" and defer_confirm:
            pending.append(
                PendingTool(
                    tool_name=tool_name,
                    args=args,
                    permission="confirm",
                    model_lane=model_lane,
                    request_id=request_id,
                )
            )
            logs.append(f"pending: {tool_name} {args}")
            continue

        tool_logs = _run_one(
            tool_name,
            args,
            client=client,
            request_id=request_id,
            on_meta=on_meta,
            attempt=attempt,
            model_lane=model_lane,
            pending_out=pending,
        )
        logs.extend(tool_logs)
        if _contains_failure(tool_logs):
            break

    return logs, pending


def apply_pending(
    pending: list[PendingTool],
    *,
    client: HarnessClient | None = None,
    request_id: str | None = None,
    on_meta: Callable[[dict[str, Any]], None] | None = None,
    pending_out: list[PendingTool] | None = None,
) -> list[str]:
    client = client or HarnessClient()
    logs: list[str] = []
    repaired: list[PendingTool] = pending_out if pending_out is not None else []
    for item in pending:
        tool_logs = _run_one(
            item.tool_name,
            item.args,
            client=client,
            request_id=item.request_id or request_id,
            on_meta=on_meta,
            attempt=1,
            model_lane=item.model_lane,
            pending_out=repaired,
        )
        logs.extend(tool_logs)
        if _contains_failure(tool_logs):
            break
    return logs


def run_actions(
    response: dict[str, Any],
    *,
    client: HarnessClient | None = None,
    on_meta: Callable[[dict[str, Any]], None] | None = None,
    attempt: int = 1,
) -> list[str]:
    logs, pending = prepare_actions(
        response,
        client=client,
        on_meta=on_meta,
        attempt=attempt,
        defer_confirm=False,
    )
    if pending:
        for item in pending:
            logs.append(f"pending after repair: {item.tool_name} {item.args}")
    return logs
