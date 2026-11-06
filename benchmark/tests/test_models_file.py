from __future__ import annotations

import argparse
from pathlib import Path

import pytest

from fixture_bench.__main__ import _parse_models_file, _resolve_models


def _file(tmp_path: Path) -> Path:
    path = tmp_path / "models.txt"
    path.write_text(
        "# comment line\n\nqwen3.5:4b\n   \nopenrouter:openai/gpt-6-luna\n",
        encoding="utf-8",
    )
    return path


def test_parse_models_file_skips_comments_and_blanks(tmp_path: Path) -> None:
    names = _parse_models_file(str(_file(tmp_path)))
    assert names == ["qwen3.5:4b", "openrouter:openai/gpt-6-luna"]


def test_resolve_models_prefers_models_file(tmp_path: Path) -> None:
    args = argparse.Namespace(
        models=None,
        all_models=False,
        winners=False,
        winners_from=None,
        include_embed=False,
        models_file=str(_file(tmp_path)),
    )
    names = _resolve_models(args)
    assert names == ["qwen3.5:4b", "openrouter:openai/gpt-6-luna"]
    assert args._models_from_file == str(_file(tmp_path))


def test_resolve_models_file_conflicts_with_explicit_models(tmp_path: Path) -> None:
    args = argparse.Namespace(
        models="qwen3.5:4b",
        all_models=False,
        winners=False,
        winners_from=None,
        include_embed=False,
        models_file=str(_file(tmp_path)),
    )
    with pytest.raises(RuntimeError, match="only one"):
        _resolve_models(args)


def test_empty_models_file_rejected(tmp_path: Path) -> None:
    path = tmp_path / "empty.txt"
    path.write_text("# only a comment\n", encoding="utf-8")
    args = argparse.Namespace(
        models=None,
        all_models=False,
        winners=False,
        winners_from=None,
        include_embed=False,
        models_file=str(path),
    )
    with pytest.raises(RuntimeError, match="no model refs"):
        _resolve_models(args)