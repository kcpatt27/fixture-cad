from __future__ import annotations

import json
import re
from typing import Any
from urllib.error import URLError
from urllib.request import urlopen

from fixture_cad.config import settings

# Name/family hints that are not chat planners for this bench.
_SKIP_SUBSTRINGS = (
    "embed",
    "embedding",
    "nomic-embed",
    "bge-",
    "e5-",
    "mxbai-embed",
    "snowflake-arctic-embed",
)

# Ollama "7.6B" / "354.48M" / name tokens like ":7b" or "350m"
_PARAM_SIZE_RE = re.compile(
    r"(?P<num>\d+(?:\.\d+)?)\s*(?P<unit>[bmk])\b",
    re.IGNORECASE,
)
_NAME_PARAM_RE = re.compile(
    r"(?:^|[:/\-_])(?P<num>\d+(?:\.\d+)?)(?P<unit>[bm])(?:[:/\-_]|$)",
    re.IGNORECASE,
)


def _is_skip_model(name: str, family: str | None = None) -> bool:
    blob = f"{name} {family or ''}".lower()
    return any(s in blob for s in _SKIP_SUBSTRINGS)


def parse_param_count_billions(
    parameter_size: str | None = None,
    *,
    name: str | None = None,
) -> float | None:
    """Return approximate parameter count in billions, or None if unknown."""
    for raw in (parameter_size, name):
        if not isinstance(raw, str) or not raw.strip():
            continue
        pattern = _PARAM_SIZE_RE if raw is parameter_size else _NAME_PARAM_RE
        match = pattern.search(raw)
        if not match:
            continue
        num = float(match.group("num"))
        unit = match.group("unit").lower()
        if unit == "b":
            return num
        if unit == "m":
            return num / 1000.0
        if unit == "k":
            return num / 1_000_000.0
    return None


def model_size_lookup(
    *,
    include_embed: bool = False,
    ollama_url: str | None = None,
) -> dict[str, dict[str, Any]]:
    """Map model name → size fields from Ollama /api/tags."""
    out: dict[str, dict[str, Any]] = {}
    for entry in list_disk_models(include_embed=include_embed, ollama_url=ollama_url):
        name = entry["name"]
        param_s = entry.get("parameter_size")
        out[name] = {
            "size": entry.get("size"),
            "parameter_size": param_s,
            "param_b": parse_param_count_billions(
                param_s if isinstance(param_s, str) else None,
                name=name,
            ),
        }
    return out


def list_disk_models(
    *,
    include_embed: bool = False,
    ollama_url: str | None = None,
) -> list[dict[str, Any]]:
    """Return Ollama tags present on disk (from /api/tags)."""
    base = (ollama_url or settings.ollama_url).rstrip("/")
    url = f"{base}/api/tags"
    try:
        with urlopen(url, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except URLError as exc:
        raise RuntimeError(f"Cannot reach Ollama at {url}: {exc}") from exc

    models: list[dict[str, Any]] = []
    for entry in data.get("models") or []:
        name = entry.get("name") or entry.get("model")
        if not isinstance(name, str) or not name:
            continue
        details = entry.get("details") or {}
        family = details.get("family") if isinstance(details, dict) else None
        if not include_embed and _is_skip_model(name, family if isinstance(family, str) else None):
            continue
        models.append(
            {
                "name": name,
                "size": entry.get("size"),
                "family": family,
                "parameter_size": details.get("parameter_size")
                if isinstance(details, dict)
                else None,
                "quantization_level": details.get("quantization_level")
                if isinstance(details, dict)
                else None,
            }
        )
    models.sort(key=lambda m: m["name"].lower())
    return models


def list_disk_model_names(*, include_embed: bool = False) -> list[str]:
    return [m["name"] for m in list_disk_models(include_embed=include_embed)]


def list_openrouter_models(*, openrouter_url: str | None = None) -> list[dict[str, Any]]:
    """Return OpenRouter models that support tool calling + JSON output.

    Reads the public /models catalog (no API key required) and keeps entries
    whose ``supported_parameters`` cover both ``tools`` and ``response_format``,
    which is what the harness planner needs.
    """
    base = (openrouter_url or settings.openrouter_url).rstrip("/")
    url = f"{base}/models"
    try:
        with urlopen(url, timeout=20) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except URLError as exc:
        raise RuntimeError(f"Cannot reach OpenRouter at {url}: {exc}") from exc

    def per_million(pricing: dict[str, Any], key: str) -> float | None:
        value = pricing.get(key)
        if value is None:
            return None
        try:
            return round(float(value) * 1e6, 2)
        except (TypeError, ValueError):
            return None

    models: list[dict[str, Any]] = []
    for entry in data.get("data") or []:
        if not isinstance(entry, dict):
            continue
        params = entry.get("supported_parameters") or []
        if "tools" not in params or "response_format" not in params:
            continue
        model_id = entry.get("id")
        if not isinstance(model_id, str) or not model_id:
            continue
        pricing = entry.get("pricing") if isinstance(entry.get("pricing"), dict) else {}
        models.append(
            {
                "id": model_id,
                "context_length": entry.get("context_length"),
                "prompt_per_m": per_million(pricing, "prompt"),
                "completion_per_m": per_million(pricing, "completion"),
            }
        )
    models.sort(key=lambda m: m["id"].lower())
    return models
