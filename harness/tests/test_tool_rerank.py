from __future__ import annotations

from typing import Any

from fixture_cad.chat import build_system_prompt, select_tools_for_prompt
from fixture_cad.config import settings
from fixture_cad.tools.registry import ToolRegistry


def _tool_count(prompt: str) -> int:
    # Every tool prompt entry has a permission tier; args schemas never do.
    return prompt.count('"permission":')


def test_rerank_prefers_name_matches() -> None:
    tools = ToolRegistry.load().for_app("freecad")
    picked = select_tools_for_prompt("create a 40x40x10mm box", tools, 5)
    names = [t.name for t in picked]
    assert "create_parametric_box" in names
    assert 1 <= len(picked) <= 5


def test_rerank_fails_open_on_unknown_wording() -> None:
    tools = ToolRegistry.load().for_app("freecad")
    picked = select_tools_for_prompt("zzz qqq", tools, 3)
    assert picked == tools


def test_rerank_zero_limit_keeps_full_catalog() -> None:
    tools = ToolRegistry.load().for_app("freecad")
    picked = select_tools_for_prompt("create a box", tools, 0)
    assert picked == tools


def test_build_prompt_default_keeps_full_catalog() -> None:
    reg = ToolRegistry.load()
    assert settings.tool_rerank_limit == 0
    prompt = build_system_prompt("freecad", reg, message="create a box")
    assert _tool_count(prompt) == len(reg.for_app("freecad"))


def test_build_prompt_rerank_limits_catalog(monkeypatch: Any) -> None:
    reg = ToolRegistry.load()
    monkeypatch.setattr(settings, "tool_rerank_limit", 2)
    prompt = build_system_prompt(
        "freecad", reg, message="create a box and fillet its edges"
    )
    count = _tool_count(prompt)
    assert 1 <= count <= 2