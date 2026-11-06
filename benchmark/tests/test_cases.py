from __future__ import annotations

import json
from pathlib import Path

import pytest

from fixture_bench import cases


def test_load_cases_rejects_missing_required_keys(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    case_dir = tmp_path / "cases"
    (case_dir / "freecad").mkdir(parents=True)
    (case_dir / "freecad" / "bad.json").write_text(
        json.dumps({"app": "freecad", "expect": {}}),
        encoding="utf-8",
    )
    monkeypatch.setattr(cases, "cases_dir", lambda: case_dir)

    with pytest.raises(ValueError, match="missing required keys"):
        cases.load_cases(app="freecad")
