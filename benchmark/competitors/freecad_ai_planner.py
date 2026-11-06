"""Head-to-head adapter: drive ghbalf/freecad-ai's planner headlessly.

We import the competitor's own LLM client, tool registry, and system prompt
from a pinned clone (never vendored), then capture its first-turn tool calls
for scoring. FreeCAD modules are never imported: the planner half of their
pipeline is stdlib-only.

Set FREECAD_AI_REPO to the clone path (default: the audit clone under the
OpenCode temp dir). FREECAD_AI_CONFIG_DIR is pointed at a scratch dir so the
competitor never touches real user config.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from pathlib import Path
from typing import Any

DEFAULT_REPO = Path(
    os.environ.get(
        "FREECAD_AI_REPO",
        str(Path(tempfile.gettempdir()) / "opencode" / "freecad-ai-audit"),
    )
)
DEFAULT_CONFIG_DIR = Path(tempfile.gettempdir()) / "opencode" / "freecad-ai-bench-config"


def _ensure_configured() -> Path:
    repo = DEFAULT_REPO
    if not (repo / "freecad_ai").is_dir():
        raise RuntimeError(
            f"freecad-ai clone not found at {repo}; set FREECAD_AI_REPO"
        )
    if str(repo) not in sys.path:
        sys.path.insert(0, str(repo))
    os.environ.setdefault("FREECAD_AI_CONFIG_DIR", str(DEFAULT_CONFIG_DIR))
    return repo


class FreeCadAiPlanner:
    """First-turn planner from freecad-ai, using its own client and prompt."""

    def __init__(self, model_ref: str) -> None:
        _ensure_configured()
        from freecad_ai.core.system_prompt import build_system_prompt
        from freecad_ai.llm.client import LLMClient
        from freecad_ai.llm.providers import PROVIDERS
        from freecad_ai.tools.setup import create_default_registry

        from fixture_cad.providers import parse_model_ref

        ref = parse_model_ref(model_ref)
        preset = PROVIDERS.get(ref.provider)
        if preset is None:
            raise RuntimeError(f"freecad-ai has no provider preset for {ref.provider!r}")

        api_key = ""
        if ref.provider == "openrouter":
            # Importing fixture_cad loaded the repo .env.
            api_key = os.environ.get("FIXTURE_OPENROUTER_API_KEY", "")

        self.model_ref = model_ref
        self.provider = ref.provider
        self.model = ref.model
        self.client = LLMClient(
            provider_name=ref.provider,
            base_url=preset["base_url"],
            api_key=api_key,
            model=ref.model,
        )
        self.registry = create_default_registry(include_mcp=False)
        self.schemas = self.registry.to_openai_schema()
        self.system_prompt = build_system_prompt(
            mode="act",
            tools_enabled=True,
            include_document_context=False,
        )

    def plan(
        self,
        message: str,
        context: dict[str, Any] | None = None,
        *,
        single_shot: bool = False,
    ) -> dict[str, Any]:
        prompt = message
        if context:
            prompt = (
                f"{message}\n\nCurrent document context (JSON):\n"
                f"{json.dumps(context, ensure_ascii=False)}"
            )
        if single_shot:
            prompt += (
                "\n\nRespond with the COMPLETE sequence of tool calls for the entire "
                "request in this single response. Do not wait for tool results: include "
                "every step you would take, in order. Use multiple parallel tool calls "
                "for one-shot plans where the tools allow it."
            )
        response = self.client.send_with_tools(
            [{"role": "user", "content": prompt}],
            system=self.system_prompt,
            tools=self.schemas,
        )
        tool_calls: list[dict[str, Any]] = []
        for call in getattr(response, "tool_calls", None) or []:
            name = getattr(call, "name", None) or getattr(call, "tool_name", "")
            args = getattr(call, "arguments", None)
            if args is None:
                args = getattr(call, "args", {})
            if isinstance(args, str):
                try:
                    args = json.loads(args)
                except json.JSONDecodeError:
                    args = {"_raw": args}
            tool_calls.append({"name": name, "args": args})
        return {
            "text": getattr(response, "text", "") or getattr(response, "content", ""),
            "tool_calls": tool_calls,
            "model": self.model_ref,
            "tool_count": len(self.schemas),
        }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Probe freecad-ai's headless planner")
    parser.add_argument("--model", required=True, help="Model ref, e.g. openrouter:deepseek/deepseek-v4.1-flash")
    parser.add_argument("--message", required=True)
    parser.add_argument("--context-json", default=None)
    args = parser.parse_args(argv)

    context = json.loads(args.context_json) if args.context_json else None
    planner = FreeCadAiPlanner(args.model)
    result = planner.plan(args.message, context)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())