"""Head-to-head capture: Fixture vs freecad-ai on the shared case suite.

Ours: `fixture_bench.runner.run_case` (identical postprocess to `/chat`).
Theirs: freecad-ai's own client + prompt + 56-tool registry (planner turn only;
we never execute their tools here).

Output: `benchmark/results/<UTC>/{ours.jsonl, freecad_ai.jsonl, meta.json}`.
Competitor scoring is a separate semantic pass; this runner captures raw tool
calls, text, latency, and errors so scoring can be re-run without re-billing.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from fixture_bench.cases import load_cases, results_dir
from fixture_bench.report import new_run_dir
from fixture_bench.runner import run_case

# Importing settings loads the repo .env before any provider call.
from fixture_cad.config import settings  # noqa: F401
from fixture_cad.tools.registry import ToolRegistry

from competitors.freecad_ai_planner import FreeCadAiPlanner


def _parse_refs(path: str) -> list[str]:
    lines = Path(path).read_text(encoding="utf-8").splitlines()
    return [
        line.strip()
        for line in lines
        if line.strip() and not line.lstrip().startswith("#")
    ]


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


async def run_ours(cases: list[dict], models: list[str], registry: ToolRegistry) -> list[dict]:
    rows: list[dict] = []
    for model in models:
        for case in cases:
            row = await run_case(case, model=model, registry=registry)
            row["system"] = "fixture"
            rows.append(row)
    return rows


def run_competitor(cases: list[dict], models: list[str], *, single_shot: bool = False) -> list[dict]:
    rows: list[dict] = []
    for model in models:
        try:
            planner = FreeCadAiPlanner(model)
        except Exception as exc:  # adapter or import failure: record, continue
            for case in cases:
                rows.append(
                    {
                        "case_id": case["id"],
                        "app": case["app"],
                        "model": model,
                        "system": "freecad-ai",
                        "error": f"adapter init: {exc}",
                    }
                )
            continue
        for case in cases:
            started = time.perf_counter()
            base = {
                "case_id": case["id"],
                "app": case["app"],
                "model": model,
                "system": "freecad-ai",
            }
            try:
                result = planner.plan(case["message"], case.get("context"), single_shot=single_shot)
                rows.append(
                    {
                        **base,
                        "text": result["text"],
                        "tool_calls": result["tool_calls"],
                        "tool_count": result["tool_count"],
                        "latency_s": time.perf_counter() - started,
                        "error": None,
                    }
                )
            except Exception as exc:
                rows.append(
                    {
                        **base,
                        "text": "",
                        "tool_calls": [],
                        "latency_s": time.perf_counter() - started,
                        "error": str(exc),
                    }
                )
    return rows


async def _run_async(args: argparse.Namespace) -> int:
    models = _parse_refs(args.models_file)
    tags = set(args.tag) if args.tag else None
    cases = load_cases(app=args.app, case_id=args.case, tags=tags)
    if args.limit:
        cases = cases[: args.limit]
    if not cases:
        print("No cases matched", file=sys.stderr)
        return 2

    systems = {s.strip() for s in args.systems.split(",") if s.strip()}
    ours: list[dict] = []
    theirs: list[dict] = []
    if "ours" in systems:
        print(f"Fixture side: {len(models)} models x {len(cases)} cases", flush=True)
        ours = await run_ours(cases, models, ToolRegistry.load())
    if "theirs" in systems:
        print(f"freecad-ai side: {len(models)} models x {len(cases)} cases", flush=True)
        theirs = run_competitor(cases, models, single_shot=args.single_shot)

    out = new_run_dir(results_dir())
    out.mkdir(parents=True, exist_ok=True)
    if ours:
        _write_jsonl(out / "ours.jsonl", ours)
    if theirs:
        _write_jsonl(out / "freecad_ai.jsonl", theirs)
    meta = {
        "kind": "headtohead",
        "started": datetime.now(timezone.utc).isoformat(),
        "models": models,
        "models_file": str(args.models_file),
        "systems": sorted(systems),
        "app": args.app,
        "tags": sorted(tags) if tags else None,
        "case_count": len(cases),
        "case_ids": [c["id"] for c in cases],
        "freecad_ai_commit": args.freecad_ai_commit,
        "single_shot": bool(args.single_shot),
    }
    (out / "meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    print(f"saved -> {out}", flush=True)
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Fixture vs freecad-ai capture")
    parser.add_argument("--models-file", required=True)
    parser.add_argument("--app", choices=["freecad", "blender"], default=None)
    parser.add_argument("--case", default=None)
    parser.add_argument("--tag", action="append", default=[])
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--systems", default="ours,theirs")
    parser.add_argument(
        "--single-shot",
        action="store_true",
        help="Ask the competitor for a complete plan in one response (planner-parity mode)",
    )
    parser.add_argument("--freecad-ai-commit", default=None)
    return asyncio.run(_run_async(parser.parse_args(argv)))


if __name__ == "__main__":
    raise SystemExit(main())