from __future__ import annotations

import os
from pathlib import Path


def _package_dir() -> Path:
    return Path(__file__).resolve().parent


def _repo_root() -> Path:
    # harness/src/fixture_cad -> repo root
    return _package_dir().parents[2]


def _dotenv_path() -> Path:
    root = _repo_root()
    if (root / "docs").is_dir():
        return root / ".env"
    return Path.cwd() / ".env"


def load_env_file(path: Path) -> int:
    """Load a minimal .env file (stdlib, no dependency).

    ``KEY=VALUE`` lines; blank lines and ``#`` comments skipped; single or
    double quotes stripped; no variable expansion. Real environment variables
    always win. Returns the number of keys set.
    """
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return 0
    set_count = 0
    for line in lines:
        text = line.strip()
        if not text or text.startswith("#") or "=" not in text:
            continue
        key, _, value = text.partition("=")
        key = key.strip()
        if not key or key in os.environ:
            continue
        os.environ[key] = value.strip().strip('"').strip("'")
        set_count += 1
    return set_count


# Local convenience: repo-root .env (gitignored). Real env vars win.
# An installed wheel falls back to the current working directory.
load_env_file(_dotenv_path())


def _default_docs(subdir: str) -> Path:
    repo_docs = _repo_root() / "docs" / subdir
    if repo_docs.is_dir():
        return repo_docs
    packaged = _package_dir() / "data" / subdir
    if packaged.is_dir():
        return packaged
    return repo_docs


class Settings:
    host: str = os.environ.get("FIXTURE_HOST", "127.0.0.1")
    port: int = int(os.environ.get("FIXTURE_PORT", "8766"))
    ollama_url: str = os.environ.get("FIXTURE_OLLAMA_URL", "http://127.0.0.1:11434").rstrip(
        "/"
    )
    ollama_model: str = os.environ.get(
        "FIXTURE_OLLAMA_MODEL", "qwen2.5:14b-instruct-q4_K_M"
    )
    ollama_fast_model: str = os.environ.get(
        "FIXTURE_OLLAMA_FAST_MODEL", "qwen2.5:7b-instruct-q8_0"
    )
    # Provider-aware lane refs: "openrouter:<model>" or "ollama:<model>".
    # An unprefixed ref is treated as an Ollama tag, so existing configs keep working.
    accurate_model: str = os.environ.get("FIXTURE_ACCURATE_MODEL") or ollama_model
    fast_model: str = os.environ.get("FIXTURE_FAST_MODEL") or ollama_fast_model
    openrouter_api_key: str = os.environ.get("FIXTURE_OPENROUTER_API_KEY", "")
    openrouter_url: str = os.environ.get(
        "FIXTURE_OPENROUTER_URL", "https://openrouter.ai/api/v1"
    ).rstrip("/")
    openrouter_referer: str = os.environ.get("FIXTURE_OPENROUTER_REFERER", "")
    openrouter_title: str = os.environ.get("FIXTURE_OPENROUTER_TITLE", "Fixture")
    # Comma-separated model refs tried, in order, when the primary lane model
    # fails (freecad-ai "fallback profiles" pattern). Empty disables fallback.
    fallback_models: str = os.environ.get("FIXTURE_FALLBACK_MODELS", "")
    # >0 prunes the tool catalog sent to the model to the N best keyword matches
    # (freecad-ai "tool reranking" pattern). 0 keeps the full catalog.
    tool_rerank_limit: int = int(os.environ.get("FIXTURE_TOOL_RERANK", "0"))
    tools_dir: Path = Path(os.environ.get("FIXTURE_TOOLS_DIR", str(_default_docs("tools"))))
    schemas_dir: Path = Path(
        os.environ.get("FIXTURE_SCHEMAS_DIR", str(_default_docs("schemas")))
    )
    request_timeout: float = float(os.environ.get("FIXTURE_TIMEOUT", "300"))


settings = Settings()
