from __future__ import annotations

import asyncio
import re
from typing import Any

import httpx

from .config import settings
from .providers import ProviderError

_JSON_MODE_REJECT_RE = re.compile(
    r"response_format|json[_ ]?mode|json[_ ]?object|structured[-_ ]?outputs?",
    re.IGNORECASE,
)

# Backoff before retrying an upstream-throttled request (OpenRouter returns
# HTTP 200 with an ``error`` body and code 429 for shared-pool rate limits).
_RATE_LIMIT_DELAYS = (3.0, 8.0)


def _headers() -> dict[str, str]:
    if not settings.openrouter_api_key:
        raise ProviderError(
            "OpenRouter API key is not configured "
            "(set FIXTURE_OPENROUTER_API_KEY)",
            provider="openrouter",
        )
    headers = {
        "Authorization": f"Bearer {settings.openrouter_api_key}",
        "Content-Type": "application/json",
    }
    if settings.openrouter_referer:
        headers["HTTP-Referer"] = settings.openrouter_referer
    if settings.openrouter_title:
        headers["X-Title"] = settings.openrouter_title
    return headers


def _extract_content(data: dict[str, Any]) -> str:
    choices = data.get("choices")
    if not isinstance(choices, list) or not choices:
        raise ProviderError(
            "OpenRouter response missing choices",
            provider="openrouter",
        )
    message = choices[0].get("message") if isinstance(choices[0], dict) else None
    content = message.get("content") if isinstance(message, dict) else None
    if isinstance(content, str):
        return content
    # Some providers return content as a list of parts; join text parts.
    if isinstance(content, list):
        parts = [
            part.get("text")
            for part in content
            if isinstance(part, dict) and isinstance(part.get("text"), str)
        ]
        joined = "".join(parts)
        if joined:
            return joined
    raise ProviderError(
        "OpenRouter response missing message.content",
        provider="openrouter",
    )


def _error_detail(response: httpx.Response) -> str:
    try:
        body = response.json()
    except ValueError:
        return response.text[:500]
    error = body.get("error") if isinstance(body, dict) else None
    if isinstance(error, dict):
        message = error.get("message")
        metadata = error.get("metadata")
        raw = metadata.get("raw") if isinstance(metadata, dict) else None
        if isinstance(message, str):
            if isinstance(raw, str) and raw not in message:
                return f"{message} — {raw}"
            return message
    return response.text[:500]


def _body_error(data: dict[str, Any]) -> tuple[int | None, str] | None:
    """Detect an error envelope delivered with HTTP 200 (OpenRouter quirk)."""
    error = data.get("error") if isinstance(data, dict) else None
    if not isinstance(error, dict):
        return None
    code = error.get("code") if isinstance(error.get("code"), int) else None
    message = error.get("message") if isinstance(error.get("message"), str) else "provider error"
    metadata = error.get("metadata")
    if isinstance(metadata, dict):
        raw = metadata.get("raw") or metadata.get("error_type")
        if isinstance(raw, str) and raw and raw not in message:
            message = f"{message} — {raw}"
    return code, message


async def chat(
    messages: list[dict[str, str]],
    *,
    model: str,
    format_json: bool = True,
) -> str:
    headers = _headers()
    payload: dict[str, Any] = {"model": model, "messages": messages}
    if format_json:
        payload["response_format"] = {"type": "json_object"}

    url = f"{settings.openrouter_url}/chat/completions"
    rate_limit_attempts = 0
    while True:
        async with httpx.AsyncClient(timeout=settings.request_timeout) as client:
            try:
                response = await client.post(url, json=payload, headers=headers)
            except httpx.HTTPError as exc:
                raise ProviderError(
                    f"OpenRouter unreachable at {url}: {exc}",
                    unreachable=True,
                    provider="openrouter",
                ) from exc

            if (
                response.status_code in {400, 404, 422}
                and "response_format" in payload
                and _JSON_MODE_REJECT_RE.search(_error_detail(response))
            ):
                # Some models support tools but not JSON mode (e.g. ling-3.1-flash).
                # Retry once without response_format; the harness JSON parser still
                # tolerates fenced/plain model output.
                payload.pop("response_format")
                try:
                    response = await client.post(url, json=payload, headers=headers)
                except httpx.HTTPError as exc:
                    raise ProviderError(
                        f"OpenRouter unreachable at {url}: {exc}",
                        unreachable=True,
                        provider="openrouter",
                    ) from exc

        if response.status_code == 429 and rate_limit_attempts < len(_RATE_LIMIT_DELAYS):
            await asyncio.sleep(_RATE_LIMIT_DELAYS[rate_limit_attempts])
            rate_limit_attempts += 1
            continue

        if response.status_code >= 400:
            raise ProviderError(
                f"OpenRouter error {response.status_code}: {_error_detail(response)}",
                provider="openrouter",
            )

        try:
            data = response.json()
        except ValueError:
            raise ProviderError(
                f"OpenRouter returned a non-JSON body: {response.text[:300]}",
                provider="openrouter",
            )

        body_error = _body_error(data)
        if body_error is not None:
            code, message = body_error
            if code == 429 and rate_limit_attempts < len(_RATE_LIMIT_DELAYS):
                await asyncio.sleep(_RATE_LIMIT_DELAYS[rate_limit_attempts])
                rate_limit_attempts += 1
                continue
            raise ProviderError(
                f"OpenRouter error {code}: {message}",
                provider="openrouter",
            )

        return _extract_content(data)