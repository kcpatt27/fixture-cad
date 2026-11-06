from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any

CLIENT_ROOT = Path(__file__).resolve().parents[1]
if str(CLIENT_ROOT) not in sys.path:
    sys.path.insert(0, str(CLIENT_ROOT))

from fixture import action_runner  # noqa: E402


def test_apply_pending_stops_stale_chain_after_failure(monkeypatch: Any) -> None:
    called: list[str] = []

    def fake_run_one(tool_name: str, _args: dict[str, Any], **_kwargs: Any) -> list[str]:
        called.append(tool_name)
        return [f"fail: {tool_name}: test failure"]

    monkeypatch.setattr(action_runner, "_run_one", fake_run_one)
    pending = [
        action_runner.PendingTool("create_body", {}, "confirm"),
        action_runner.PendingTool("new_sketch", {}, "confirm"),
        action_runner.PendingTool("sketch_rectangle", {}, "confirm"),
        action_runner.PendingTool("pad_sketch", {}, "confirm"),
        action_runner.PendingTool("new_sketch", {}, "confirm"),
        action_runner.PendingTool("sketch_rectangle", {}, "confirm"),
        action_runner.PendingTool("pocket_sketch", {}, "confirm"),
    ]

    logs = action_runner.apply_pending(pending, client=object())
    assert called == ["create_body"]
    assert logs == ["fail: create_body: test failure"]


def _fake_runner(
    name: str,
    permission: str,
    calls: list[str],
    *,
    fail: bool = False,
) -> SimpleNamespace:
    def run(_args: dict[str, Any]) -> str:
        calls.append(name)
        if fail:
            raise RuntimeError("tool exploded")
        return "ok"

    return SimpleNamespace(name=name, permission=permission, run=run)


def _repaired_response() -> dict[str, Any]:
    return {
        "request_id": "repair-1",
        "model_lane": "accurate",
        "actions": [
            {
                "type": "tool_call",
                "tool_name": "create_parametric_box",
                "args": {"width": 10, "height": 20, "depth": 30},
            }
        ],
    }


def test_repair_confirm_tier_is_staged_not_executed(monkeypatch: Any) -> None:
    calls: list[str] = []
    runners = {
        "explode": _fake_runner("explode", "auto", calls, fail=True),
        "create_parametric_box": _fake_runner(
            "create_parametric_box", "confirm", calls
        ),
    }
    monkeypatch.setattr(action_runner, "get_runner", lambda name: runners.get(name))
    monkeypatch.setattr("fixture.context.build_context", lambda: {})
    client = SimpleNamespace(send_tool_result=lambda _payload: _repaired_response())
    response = {
        "request_id": "req-1",
        "model_lane": "accurate",
        "actions": [{"type": "tool_call", "tool_name": "explode", "args": {}}],
    }

    _logs, pending = action_runner.prepare_actions(
        response, client=client, defer_confirm=True
    )

    assert calls == ["explode"]
    assert [p.tool_name for p in pending] == ["create_parametric_box"]
    assert pending[0].request_id == "repair-1"


def test_apply_repair_confirm_tier_is_staged_not_executed(monkeypatch: Any) -> None:
    calls: list[str] = []
    runners = {
        "explode": _fake_runner("explode", "confirm", calls, fail=True),
        "create_parametric_box": _fake_runner(
            "create_parametric_box", "confirm", calls
        ),
    }
    monkeypatch.setattr(action_runner, "get_runner", lambda name: runners.get(name))
    monkeypatch.setattr("fixture.context.build_context", lambda: {})
    client = SimpleNamespace(send_tool_result=lambda _payload: _repaired_response())
    pending = [action_runner.PendingTool("explode", {}, "confirm", "accurate", "req-1")]
    repaired: list[action_runner.PendingTool] = []

    action_runner.apply_pending(pending, client=client, pending_out=repaired)

    assert calls == ["explode"]
    assert [p.tool_name for p in repaired] == ["create_parametric_box"]
    assert repaired[0].request_id == "repair-1"
