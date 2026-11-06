from __future__ import annotations

import asyncio
from typing import Any

import pytest

from fixture_cad import openrouter, providers


def test_parse_bare_ref_is_ollama() -> None:
    ref = providers.parse_model_ref("qwen2.5:14b-instruct-q4_K_M")
    assert ref.provider == "ollama"
    assert ref.model == "qwen2.5:14b-instruct-q4_K_M"


def test_parse_ollama_prefix() -> None:
    ref = providers.parse_model_ref("ollama:qwen2.5:7b")
    assert ref.provider == "ollama"
    assert ref.model == "qwen2.5:7b"


def test_parse_openrouter_prefix_keeps_slash_model() -> None:
    ref = providers.parse_model_ref("openrouter:anthropic/claude-sonnet-5.5")
    assert ref.provider == "openrouter"
    assert ref.model == "anthropic/claude-sonnet-5.5"


def test_parse_rejects_empty_ref() -> None:
    with pytest.raises(providers.ProviderError):
        providers.parse_model_ref("  ")
    with pytest.raises(providers.ProviderError):
        providers.parse_model_ref("openrouter:")


def test_chat_dispatches_bare_ref_to_ollama(monkeypatch: Any) -> None:
    captured: dict[str, Any] = {}

    async def fake_chat(
        messages: list[dict[str, str]], *, model: str, format_json: bool
    ) -> str:
        captured["model"] = model
        captured["format_json"] = format_json
        return "{}"

    monkeypatch.setattr(providers.ollama, "chat", fake_chat)
    out = asyncio.run(providers.chat([], model="qwen2.5:7b", format_json=False))
    assert out == "{}"
    assert captured == {"model": "qwen2.5:7b", "format_json": False}


def test_chat_dispatches_openrouter_prefix(monkeypatch: Any) -> None:
    captured: dict[str, Any] = {}

    async def fake_chat(
        messages: list[dict[str, str]], *, model: str, format_json: bool
    ) -> str:
        captured["model"] = model
        captured["format_json"] = format_json
        return '{"ok":true}'

    monkeypatch.setattr(openrouter, "chat", fake_chat)
    out = asyncio.run(
        providers.chat([], model="openrouter:meta-llama/llama-4", format_json=True)
    )
    assert out == '{"ok":true}'
    assert captured == {"model": "meta-llama/llama-4", "format_json": True}


def _patch_client(monkeypatch: Any, captured: dict[str, Any], response: Any) -> None:
    class FakeAsyncClient:
        def __init__(self, *, timeout: float) -> None:
            captured["timeout"] = timeout

        async def __aenter__(self) -> FakeAsyncClient:
            return self

        async def __aexit__(self, *_args: object) -> None:
            return None

        async def post(
            self, url: str, *, json: dict[str, Any], headers: dict[str, str]
        ) -> Any:
            captured["url"] = url
            captured["payload"] = json
            captured["headers"] = headers
            return response

    monkeypatch.setattr(openrouter.httpx, "AsyncClient", FakeAsyncClient)


def test_openrouter_request_shape(monkeypatch: Any) -> None:
    captured: dict[str, Any] = {}

    class FakeResponse:
        status_code = 200
        text = ""

        def json(self) -> dict[str, Any]:
            return {"choices": [{"message": {"content": '{"reply_text":"hi"}'}}]}

    monkeypatch.setattr(openrouter.settings, "openrouter_api_key", "sk-test")
    monkeypatch.setattr(openrouter.settings, "openrouter_url", "https://or.test/api/v1")
    monkeypatch.setattr(openrouter.settings, "openrouter_referer", "https://fixture.local")
    monkeypatch.setattr(openrouter.settings, "openrouter_title", "Fixture")
    _patch_client(monkeypatch, captured, FakeResponse())

    out = asyncio.run(
        openrouter.chat(
            [{"role": "user", "content": "hi"}],
            model="anthropic/claude-sonnet-5.5",
            format_json=True,
        )
    )
    assert out == '{"reply_text":"hi"}'
    assert captured["url"] == "https://or.test/api/v1/chat/completions"
    assert captured["headers"]["Authorization"] == "Bearer sk-test"
    assert captured["headers"]["HTTP-Referer"] == "https://fixture.local"
    assert captured["headers"]["X-Title"] == "Fixture"
    assert captured["payload"]["model"] == "anthropic/claude-sonnet-5.5"
    assert captured["payload"]["response_format"] == {"type": "json_object"}


def test_openrouter_omits_response_format_when_not_requested(monkeypatch: Any) -> None:
    captured: dict[str, Any] = {}

    class FakeResponse:
        status_code = 200
        text = ""

        def json(self) -> dict[str, Any]:
            return {"choices": [{"message": {"content": "plain"}}]}

    monkeypatch.setattr(openrouter.settings, "openrouter_api_key", "sk-test")
    _patch_client(monkeypatch, captured, FakeResponse())
    asyncio.run(openrouter.chat([], model="x/y", format_json=False))
    assert "response_format" not in captured["payload"]


def test_openrouter_missing_key_fails_closed(monkeypatch: Any) -> None:
    monkeypatch.setattr(openrouter.settings, "openrouter_api_key", "")
    with pytest.raises(providers.ProviderError) as excinfo:
        asyncio.run(openrouter.chat([], model="x/y"))
    assert excinfo.value.provider == "openrouter"
    assert excinfo.value.unreachable is False


def test_openrouter_http_error_is_not_unreachable(monkeypatch: Any) -> None:
    class FakeResponse:
        status_code = 429
        text = ""

        def json(self) -> dict[str, Any]:
            return {"error": {"message": "rate limited"}}

    monkeypatch.setattr(openrouter, "_RATE_LIMIT_DELAYS", ())
    monkeypatch.setattr(openrouter.settings, "openrouter_api_key", "sk-test")
    captured: dict[str, Any] = {}
    _patch_client(monkeypatch, captured, FakeResponse())
    with pytest.raises(providers.ProviderError) as excinfo:
        asyncio.run(openrouter.chat([], model="x/y"))
    assert "rate limited" in str(excinfo.value)
    assert excinfo.value.unreachable is False


def test_openrouter_transport_error_is_unreachable(monkeypatch: Any) -> None:
    class FakeAsyncClient:
        def __init__(self, *, timeout: float) -> None:
            pass

        async def __aenter__(self) -> FakeAsyncClient:
            return self

        async def __aexit__(self, *_args: object) -> None:
            return None

        async def post(self, *_args: object, **_kwargs: object) -> Any:
            raise openrouter.httpx.ConnectError("connection refused")

    monkeypatch.setattr(openrouter.settings, "openrouter_api_key", "sk-test")
    monkeypatch.setattr(openrouter.httpx, "AsyncClient", FakeAsyncClient)
    with pytest.raises(providers.ProviderError) as excinfo:
        asyncio.run(openrouter.chat([], model="x/y"))
    assert excinfo.value.unreachable is True


def test_openrouter_joins_content_parts(monkeypatch: Any) -> None:
    class FakeResponse:
        status_code = 200
        text = ""

        def json(self) -> dict[str, Any]:
            return {
                "choices": [
                    {
                        "message": {
                            "content": [
                                {"type": "text", "text": '{"a":'},
                                {"type": "text", "text": "1}"},
                            ]
                        }
                    }
                ]
            }

    monkeypatch.setattr(openrouter.settings, "openrouter_api_key", "sk-test")
    captured: dict[str, Any] = {}
    _patch_client(monkeypatch, captured, FakeResponse())
    assert asyncio.run(openrouter.chat([], model="x/y")) == '{"a":1}'


def test_openrouter_retries_without_json_mode(monkeypatch: Any) -> None:
    """Models that support tools but not response_format (e.g. ling-3.1) get one retry."""
    payloads: list[dict[str, Any]] = []

    class FirstResponse:
        status_code = 404
        text = ""

        def json(self) -> dict[str, Any]:
            return {
                "error": {
                    "message": "No endpoints found that support response_format type json_object"
                }
            }

    class SecondResponse:
        status_code = 200
        text = ""

        def json(self) -> dict[str, Any]:
            return {"choices": [{"message": {"content": '{"ok":true}'}}]}

    class FakeAsyncClient:
        def __init__(self, *, timeout: float) -> None:
            pass

        async def __aenter__(self) -> FakeAsyncClient:
            return self

        async def __aexit__(self, *_args: object) -> None:
            return None

        async def post(
            self, url: str, *, json: dict[str, Any], headers: dict[str, str]
        ) -> Any:
            payloads.append(dict(json))
            return FirstResponse() if len(payloads) == 1 else SecondResponse()

    monkeypatch.setattr(openrouter.settings, "openrouter_api_key", "sk-test")
    monkeypatch.setattr(openrouter.httpx, "AsyncClient", FakeAsyncClient)
    out = asyncio.run(openrouter.chat([], model="inclusionai/ling-3.1-flash"))
    assert out == '{"ok":true}'
    assert "response_format" in payloads[0]
    assert "response_format" not in payloads[1]


def test_openrouter_retries_without_json_mode_for_structured_outputs_wording(
    monkeypatch: Any,
) -> None:
    """OpenRouter's hyphenated structured-outputs rejection must trigger the retry."""
    payloads: list[dict[str, Any]] = []

    class FirstResponse:
        status_code = 400
        text = ""

        def json(self) -> dict[str, Any]:
            return {
                "error": {
                    "message": "Provider returned error",
                    "code": 400,
                    "metadata": {
                        "raw": '{"message":"model: inclusionai/ling-3.1-flash does not support feature: structured-outputs"}'
                    },
                }
            }

    class SecondResponse:
        status_code = 200
        text = ""

        def json(self) -> dict[str, Any]:
            return {"choices": [{"message": {"content": '{"ok":true}'}}]}

    class FakeAsyncClient:
        def __init__(self, *, timeout: float) -> None:
            pass

        async def __aenter__(self) -> FakeAsyncClient:
            return self

        async def __aexit__(self, *_args: object) -> None:
            return None

        async def post(
            self, url: str, *, json: dict[str, Any], headers: dict[str, str]
        ) -> Any:
            payloads.append(dict(json))
            return FirstResponse() if len(payloads) == 1 else SecondResponse()

    monkeypatch.setattr(openrouter.settings, "openrouter_api_key", "sk-test")
    monkeypatch.setattr(openrouter.httpx, "AsyncClient", FakeAsyncClient)
    out = asyncio.run(openrouter.chat([], model="inclusionai/ling-3.1-flash"))
    assert out == '{"ok":true}'
    assert "response_format" in payloads[0]
    assert "response_format" not in payloads[1]


def test_chat_normalizes_ollama_error(monkeypatch: Any) -> None:
    async def fake_chat(
        messages: list[dict[str, str]], *, model: str, format_json: bool
    ) -> str:
        raise providers.ollama.OllamaError("ollama down", unreachable=True)

    monkeypatch.setattr(providers.ollama, "chat", fake_chat)
    with pytest.raises(providers.ProviderError) as excinfo:
        asyncio.run(providers.chat([], model="qwen2.5:7b"))
    assert excinfo.value.provider == "ollama"
    assert excinfo.value.unreachable is True


def test_parse_fallback_models() -> None:
    assert providers.parse_fallback_models(None) == []
    assert providers.parse_fallback_models("") == []
    assert providers.parse_fallback_models(" openrouter:a/b , ,ollama:c ") == [
        "openrouter:a/b",
        "ollama:c",
    ]


def test_chat_chain_falls_back_to_next_model(monkeypatch: Any) -> None:
    calls: list[str] = []

    async def fake_chat(
        messages: list[dict[str, str]], *, model: str, format_json: bool
    ) -> str:
        calls.append(model)
        if model == "bad":
            raise providers.ProviderError("down", unreachable=True, provider="ollama")
        return '{"ok":true}'

    monkeypatch.setattr(providers, "chat", fake_chat)
    content, used = asyncio.run(
        providers.chat_chain([], models=["bad", "good"], format_json=True)
    )
    assert content == '{"ok":true}'
    assert used == "good"
    assert calls == ["bad", "good"]


def test_chat_chain_raises_last_error(monkeypatch: Any) -> None:
    async def fake_chat(
        messages: list[dict[str, str]], *, model: str, format_json: bool
    ) -> str:
        raise providers.ProviderError(f"fail-{model}", provider="ollama")

    monkeypatch.setattr(providers, "chat", fake_chat)
    with pytest.raises(providers.ProviderError, match="fail-second"):
        asyncio.run(providers.chat_chain([], models=["first", "second"]))


def test_openrouter_200_error_body_raises_with_detail(monkeypatch: Any) -> None:
    """OpenRouter can return HTTP 200 with an error envelope instead of choices."""
    monkeypatch.setattr(openrouter, "_RATE_LIMIT_DELAYS", ())

    class FakeResponse:
        status_code = 200
        text = ""

        def json(self) -> dict[str, Any]:
            return {
                "error": {
                    "message": "gpt-x is temporarily rate-limited upstream.",
                    "code": 429,
                    "metadata": {"raw": "add your own key to accumulate your rate limits"},
                }
            }

    monkeypatch.setattr(openrouter.settings, "openrouter_api_key", "sk-test")
    captured: dict[str, Any] = {}
    _patch_client(monkeypatch, captured, FakeResponse())
    with pytest.raises(providers.ProviderError) as excinfo:
        asyncio.run(openrouter.chat([], model="openai/gpt-6.1-sol-pro"))
    assert "rate-limited upstream" in str(excinfo.value)
    assert "add your own key" in str(excinfo.value)


def test_openrouter_retries_upstream_rate_limit_then_succeeds(monkeypatch: Any) -> None:
    monkeypatch.setattr(openrouter, "_RATE_LIMIT_DELAYS", (0.0, 0.0))
    posts: list[int] = []

    class RateLimited:
        status_code = 200
        text = ""

        def json(self) -> dict[str, Any]:
            return {"error": {"message": "rate-limited upstream", "code": 429}}

    class Ok:
        status_code = 200
        text = ""

        def json(self) -> dict[str, Any]:
            return {"choices": [{"message": {"content": '{"ok":true}'}}]}

    class FakeAsyncClient:
        def __init__(self, *, timeout: float) -> None:
            pass

        async def __aenter__(self) -> FakeAsyncClient:
            return self

        async def __aexit__(self, *_args: object) -> None:
            return None

        async def post(
            self, url: str, *, json: dict[str, Any], headers: dict[str, str]
        ) -> Any:
            posts.append(1)
            return RateLimited() if len(posts) < 3 else Ok()

    monkeypatch.setattr(openrouter.settings, "openrouter_api_key", "sk-test")
    monkeypatch.setattr(openrouter.httpx, "AsyncClient", FakeAsyncClient)
    out = asyncio.run(openrouter.chat([], model="x/y"))
    assert out == '{"ok":true}'
    assert len(posts) == 3


def test_openrouter_retries_http_429_then_succeeds(monkeypatch: Any) -> None:
    monkeypatch.setattr(openrouter, "_RATE_LIMIT_DELAYS", (0.0, 0.0))
    posts: list[int] = []

    class RateLimited:
        status_code = 429
        text = ""

        def json(self) -> dict[str, Any]:
            return {"error": {"message": "temporarily rate-limited upstream", "code": 429}}

    class Ok:
        status_code = 200
        text = ""

        def json(self) -> dict[str, Any]:
            return {"choices": [{"message": {"content": '{"ok":true}'}}]}

    class FakeAsyncClient:
        def __init__(self, *, timeout: float) -> None:
            pass

        async def __aenter__(self) -> FakeAsyncClient:
            return self

        async def __aexit__(self, *_args: object) -> None:
            return None

        async def post(
            self, url: str, *, json: dict[str, Any], headers: dict[str, str]
        ) -> Any:
            posts.append(1)
            return RateLimited() if len(posts) < 3 else Ok()

    monkeypatch.setattr(openrouter.settings, "openrouter_api_key", "sk-test")
    monkeypatch.setattr(openrouter.httpx, "AsyncClient", FakeAsyncClient)
    out = asyncio.run(openrouter.chat([], model="x/y"))
    assert out == '{"ok":true}'
    assert len(posts) == 3