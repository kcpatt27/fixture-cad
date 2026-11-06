from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any

CLIENT_ROOT = Path(__file__).resolve().parents[1]
if str(CLIENT_ROOT) not in sys.path:
    sys.path.insert(0, str(CLIENT_ROOT))

from fixture_blender import action_runner  # noqa: E402


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
                "tool_name": "clean_mesh",
                "args": {"object_name": "Scan"},
            }
        ],
    }


def test_repair_confirm_tier_is_staged_not_executed(monkeypatch: Any) -> None:
    calls: list[str] = []
    runners = {
        "explode": _fake_runner("explode", "auto", calls, fail=True),
        "clean_mesh": _fake_runner("clean_mesh", "confirm", calls),
    }
    monkeypatch.setattr(action_runner, "get_runner", lambda name: runners.get(name))
    monkeypatch.setattr("fixture_blender.context.build_context", lambda: {})
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
    assert [p.tool_name for p in pending] == ["clean_mesh"]
    assert pending[0].request_id == "repair-1"


def test_apply_repair_confirm_tier_is_staged_not_executed(monkeypatch: Any) -> None:
    calls: list[str] = []
    runners = {
        "explode": _fake_runner("explode", "confirm", calls, fail=True),
        "clean_mesh": _fake_runner("clean_mesh", "confirm", calls),
    }
    monkeypatch.setattr(action_runner, "get_runner", lambda name: runners.get(name))
    monkeypatch.setattr("fixture_blender.context.build_context", lambda: {})
    client = SimpleNamespace(send_tool_result=lambda _payload: _repaired_response())
    pending = [action_runner.PendingTool("explode", {}, "confirm", "accurate", "req-1")]
    repaired: list[action_runner.PendingTool] = []

    action_runner.apply_pending(pending, client=client, pending_out=repaired)

    assert calls == ["explode"]
    assert [p.tool_name for p in repaired] == ["clean_mesh"]
    assert repaired[0].request_id == "repair-1"
