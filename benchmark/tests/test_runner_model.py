from __future__ import annotations

import asyncio
from typing import Any

from fixture_bench import runner
from fixture_cad.tools.registry import ToolRegistry


def test_run_case_passes_explicit_model(monkeypatch: Any) -> None:
    captured: dict[str, Any] = {}

    async def fake_chat(
        _messages: list[dict[str, str]],
        *,
        model: str,
        format_json: bool,
    ) -> str:
        captured["model"] = model
        captured["format_json"] = format_json
        return '{"reply_text":"ok","actions":[]}'

    monkeypatch.setattr(runner.providers, "chat", fake_chat)
    result = asyncio.run(
        runner.run_case(
            {
                "id": "test-explicit-model",
                "app": "freecad",
                "message": "say hello",
                "mode": "chat",
                "context": {"selected_objects": []},
                "expect": {},
            },
            model="test-model",
            registry=ToolRegistry.load(),
        )
    )

    assert result["error"] is None
    assert captured == {"model": "test-model", "format_json": True}
