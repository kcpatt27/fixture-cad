from __future__ import annotations

import asyncio
import json
from typing import Any

from fixture_cad import chat as chat_planner
from fixture_cad import main
from fixture_cad import ollama
from fixture_cad.config import Settings
from fixture_cad.model_lanes import resolve_model
from fixture_cad.tools.registry import ToolRegistry


def _settings() -> Settings:
    value = Settings()
    value.accurate_model = "accurate-model"
    value.fast_model = "fast-model"
    return value


def test_omitted_lane_defaults_to_accurate() -> None:
    selection = resolve_model(None, mode="chat", settings=_settings())
    assert selection.lane == "accurate"
    assert selection.model == "accurate-model"


def test_manual_lanes_override_mode() -> None:
    settings = _settings()
    assert resolve_model("fast", mode="tool", settings=settings).model == "fast-model"
    assert resolve_model("accurate", mode="chat", settings=settings).model == "accurate-model"


def test_auto_routes_chat_fast_and_other_modes_accurate() -> None:
    settings = _settings()
    assert resolve_model("auto", mode="chat", settings=settings).lane == "fast"
    assert resolve_model("auto", mode="explain", settings=settings).lane == "accurate"
    assert resolve_model("auto", mode="tool", settings=settings).lane == "accurate"


def test_ollama_chat_uses_explicit_model(monkeypatch: Any) -> None:
    captured: dict[str, Any] = {}

    class FakeResponse:
        status_code = 200
        text = ""

        def json(self) -> dict[str, Any]:
            return {"message": {"content": "{}"}}

    class FakeAsyncClient:
        def __init__(self, *, timeout: float) -> None:
            captured["timeout"] = timeout

        async def __aenter__(self) -> FakeAsyncClient:
            return self

        async def __aexit__(self, *_args: object) -> None:
            return None

        async def post(self, url: str, *, json: dict[str, Any]) -> FakeResponse:
            captured["url"] = url
            captured["payload"] = json
            return FakeResponse()

    monkeypatch.setattr(ollama.httpx, "AsyncClient", FakeAsyncClient)
    asyncio.run(ollama.chat([], model="fast-model"))
    assert captured["payload"]["model"] == "fast-model"


def test_repair_keeps_resolved_lane(monkeypatch: Any) -> None:
    captured: dict[str, Any] = {}

    async def fake_chat(
        _messages: list[dict[str, str]],
        *,
        model: str,
        format_json: bool,
    ) -> str:
        captured["model"] = model
        captured["format_json"] = format_json
        return '{"reply_text":"repaired","actions":[]}'

    monkeypatch.setattr(chat_planner.providers, "chat", fake_chat)
    result = asyncio.run(
        chat_planner.plan_repair(
            app="freecad",
            tool_name="create_parametric_box",
            error={"message": "failed"},
            context={"selected_objects": []},
            registry=ToolRegistry.load(),
            model_lane="fast",
            model="fast-model",
            request_id="repair-1",
        )
    )
    assert captured["model"] == "fast-model"
    assert result["model_lane"] == "fast"
    assert result["model"] == "fast-model"


def test_successful_tool_result_reports_selected_model() -> None:
    response = asyncio.run(
        main.tools_result(
            {
                "app": "freecad",
                "version": "0.1.0",
                "tool_name": "create_parametric_box",
                "success": True,
                "model_lane": "fast",
                "attempt": 1,
            }
        )
    )
    body = json.loads(response.body)
    assert body["model_lane"] == "fast"
    assert body["model"] == main.settings.fast_model
