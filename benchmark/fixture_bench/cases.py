from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def cases_dir() -> Path:
    return repo_root() / "benchmark" / "cases"


def results_dir() -> Path:
    return repo_root() / "benchmark" / "results"


def load_cases(
    *,
    app: str | None = None,
    case_id: str | None = None,
    tags: set[str] | None = None,
) -> list[dict[str, Any]]:
    root = cases_dir()
    paths: list[Path] = []
    if app in (None, "freecad"):
        paths.extend(sorted((root / "freecad").glob("*.json")))
    if app in (None, "blender"):
        paths.extend(sorted((root / "blender").glob("*.json")))

    cases: list[dict[str, Any]] = []
    for path in paths:
        data = json.loads(path.read_text(encoding="utf-8"))
        required = {"id", "app", "message", "mode", "context", "expect"}
        missing = required - set(data)
        if missing:
            raise ValueError(f"{path}: missing required keys {sorted(missing)}")
        if data["app"] not in {"freecad", "blender"}:
            raise ValueError(f"{path}: unsupported app {data['app']!r}")
        if not isinstance(data["expect"], dict):
            raise ValueError(f"{path}: expect must be an object")
        data["_path"] = str(path)
        if case_id and data.get("id") != case_id:
            continue
        if tags:
            case_tags = set(data.get("tags") or [])
            if not tags.issubset(case_tags):
                continue
        cases.append(data)
    return cases
