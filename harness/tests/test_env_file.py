from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from fixture_cad.config import load_env_file


def test_load_env_file_sets_unset_keys(tmp_path: Path, monkeypatch: Any) -> None:
    path = tmp_path / ".env"
    path.write_text(
        "# comment\n\n"
        "FIXTURE_TEST_KEY=abc\n"
        'FIXTURE_TEST_QUOTED="x y"\n'
        "FIXTURE_TEST_EXISTING=new\n"
        "FIXTURE_TEST_EMPTY=\n",
        encoding="utf-8",
    )
    monkeypatch.delenv("FIXTURE_TEST_KEY", raising=False)
    monkeypatch.delenv("FIXTURE_TEST_QUOTED", raising=False)
    monkeypatch.setenv("FIXTURE_TEST_EXISTING", "old")
    monkeypatch.delenv("FIXTURE_TEST_EMPTY", raising=False)

    count = load_env_file(path)

    assert os.environ["FIXTURE_TEST_KEY"] == "abc"
    assert os.environ["FIXTURE_TEST_QUOTED"] == "x y"
    assert os.environ["FIXTURE_TEST_EXISTING"] == "old"
    assert os.environ["FIXTURE_TEST_EMPTY"] == ""
    assert count == 3  # EXISTING was already set and is skipped


def test_load_env_file_missing_returns_zero(tmp_path: Path) -> None:
    assert load_env_file(tmp_path / "nope.env") == 0