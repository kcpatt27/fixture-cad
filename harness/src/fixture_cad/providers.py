from __future__ import annotations

from dataclasses import dataclass

from . import ollama


class ProviderError(Exception):
    """Provider-neutral model call failure.

    ``unreachable`` marks transport failures (connection refused/timeout) so the
    HTTP layer can answer 503 rather than 502. ``provider`` names the failing
    backend ("ollama" or "openrouter") for error codes such as
    ``openrouter_unreachable``.
    """

    def __init__(
        self,
        message: str,
        *,
        unreachable: bool = False,
        provider: str = "ollama",
    ) -> None:
        super().__init__(message)
        self.unreachable = unreachable
        self.provider = provider


@dataclass(frozen=True)
class ModelRef:
    provider: str
    model: str


_PROVIDER_PREFIXES = ("ollama:", "openrouter:")


def parse_model_ref(ref: str) -> ModelRef:
    """Split a lane model ref into (provider, model).

    ``openrouter:anthropic/claude-sonnet-5.5`` selects OpenRouter.
    ``ollama:qwen2.5:14b`` or a bare ``qwen2.5:14b`` selects Ollama; bare refs
    stay valid because Ollama tags themselves contain colons.
    """
    if not isinstance(ref, str) or not ref.strip():
        raise ProviderError("model reference must be a non-empty string", provider="unknown")
    text = ref.strip()
    for prefix in _PROVIDER_PREFIXES:
        if text.startswith(prefix):
            name = text[len(prefix) :].strip()
            if not name:
                raise ProviderError(
                    f"model reference {text!r} has an empty model name",
                    provider=prefix[:-1],
                )
            return ModelRef(provider=prefix[:-1], model=name)
    return ModelRef(provider="ollama", model=text)


def provider_of(model: str) -> str:
    return parse_model_ref(model).provider


async def chat(
    messages: list[dict[str, str]],
    *,
    model: str,
    format_json: bool = True,
) -> str:
    ref = parse_model_ref(model)
    if ref.provider == "openrouter":
        # Local import keeps the provider modules import-cycle free.
        from . import openrouter

        return await openrouter.chat(messages, model=ref.model, format_json=format_json)
    try:
        return await ollama.chat(messages, model=ref.model, format_json=format_json)
    except ollama.OllamaError as exc:
        raise ProviderError(
            str(exc),
            unreachable=exc.unreachable,
            provider="ollama",
        ) from exc


def parse_fallback_models(raw: str | None) -> list[str]:
    """Parse FIXTURE_FALLBACK_MODELS: comma-separated refs, empty entries dropped."""
    if not raw:
        return []
    return [part.strip() for part in raw.split(",") if part.strip()]


async def chat_chain(
    messages: list[dict[str, str]],
    *,
    models: list[str],
    format_json: bool = True,
) -> tuple[str, str]:
    """Call the first model that answers; return (content, model_used).

    On the freecad-ai fallback-profile pattern, a provider failure (unreachable,
    auth, rate limit, model missing) advances to the next ref. The last error
    is re-raised when every model fails, so the HTTP layer reports a real cause.
    """
    if not models:
        raise ProviderError("no model configured", provider="unknown")
    last: ProviderError | None = None
    for ref in models:
        try:
            content = await chat(messages, model=ref, format_json=format_json)
            return content, ref
        except ProviderError as exc:
            last = exc
    assert last is not None
    raise last