from __future__ import annotations

from typing import Any

import httpx

from .config import settings


class OllamaError(Exception):
    def __init__(self, message: str, *, unreachable: bool = False) -> None:
        super().__init__(message)
        self.unreachable = unreachable


async def chat(
    messages: list[dict[str, str]],
    *,
    model: str,
    format_json: bool = True,
) -> str:
    payload: dict[str, Any] = {
        "model": model,
        "messages": messages,
        "stream": False,
    }
    if format_json:
        payload["format"] = "json"

    url = f"{settings.ollama_url}/api/chat"
    try:
        async with httpx.AsyncClient(timeout=settings.request_timeout) as client:
            response = await client.post(url, json=payload)
    except httpx.HTTPError as exc:
        raise OllamaError(f"Ollama unreachable at {url}: {exc}", unreachable=True) from exc

    if response.status_code >= 400:
        raise OllamaError(f"Ollama error {response.status_code}: {response.text}")

    data = response.json()
    message = data.get("message") or {}
    content = message.get("content")
    if not isinstance(content, str):
        raise OllamaError("Ollama response missing message.content")
    return content


async def ping() -> bool:
    url = f"{settings.ollama_url}/api/tags"
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(url)
            return response.status_code == 200
    except httpx.HTTPError:
        return False
