from __future__ import annotations

import argparse
import asyncio
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

# Allow `python -m fixture_bench` from repo when PYTHONPATH includes benchmark/
_BENCH_ROOT = Path(__file__).resolve().parent.parent
if str(_BENCH_ROOT) not in sys.path:
    sys.path.insert(0, str(_BENCH_ROOT))

from fixture_cad.tools.registry import ToolRegistry

from fixture_bench.cases import load_cases, results_dir
from fixture_bench.models import (
    list_disk_model_names,
    list_disk_models,
    list_openrouter_models,
)
from fixture_bench.models import model_size_lookup, parse_param_count_billions
from fixture_cad.config import settings
from fixture_cad.providers import parse_model_ref
from fixture_bench.report import (
    latest_results_dir,
    load_results_jsonl,
    load_winner_preset_from_run,
    new_run_dir,
    render_console,
    render_summary_md,
    write_run,
)
from fixture_bench.runner import run_case
from fixture_bench.style import (
    Style,
    configure_stdio,
    enable_windows_ansi,
    short_model,
    supports_color,
)


def _parse_models(raw: str | None) -> list[str]:
    if not raw:
        return []
    return [m.strip() for m in raw.split(",") if m.strip()]


def _parse_models_file(path: str) -> list[str]:
    """Read a model list file: one ref per line, blank and # comment lines skipped."""
    lines = Path(path).read_text(encoding="utf-8").splitlines()
    return [line.strip() for line in lines if line.strip() and not line.lstrip().startswith("#")]


def _resolve_models(args: argparse.Namespace) -> list[str]:
    want_winners = bool(getattr(args, "winners", False))
    want_all = bool(
        getattr(args, "all_models", False) or (args.models or "").strip().lower() == "all"
    )
    explicit = _parse_models(args.models) if (args.models or "").strip().lower() != "all" else []
    models_file = getattr(args, "models_file", None)
    sources = sum([want_winners, want_all, bool(explicit), bool(models_file)])
    if sources > 1:
        raise RuntimeError(
            "Use only one of --winners, --all-models / --models all, "
            "--models TAGS, or --models-file PATH"
        )
    if getattr(args, "winners_from", None) and not want_winners:
        raise RuntimeError("--winners-from requires --winners")

    if models_file:
        try:
            names = _parse_models_file(models_file)
        except OSError as exc:
            raise RuntimeError(f"Cannot read models file {models_file}: {exc}") from exc
        if not names:
            raise RuntimeError(f"Models file {models_file} has no model refs")
        args._models_from_file = str(models_file)
        return names

    if want_winners:
        root = results_dir()
        if getattr(args, "winners_from", None):
            run_dir = Path(args.winners_from)
        else:
            run_dir = latest_results_dir(root)
        if run_dir is None or not run_dir.exists():
            raise RuntimeError(
                "No prior results for --winners. Run a benchmark first, "
                "or pass --winners-from PATH"
            )
        names, roles = load_winner_preset_from_run(run_dir)
        args._winners_from = str(run_dir)
        args._winners_roles = roles
        return names

    if want_all:
        names = list_disk_model_names(include_embed=bool(getattr(args, "include_embed", False)))
        if not names:
            raise RuntimeError("No chat models found on disk via Ollama /api/tags")
        return names
    if not explicit:
        raise RuntimeError("Specify --models TAGS, --all-models, --winners, or --models-file PATH")
    return explicit


def _style_from_args(args: argparse.Namespace) -> Style:
    force = False if getattr(args, "no_color", False) else None
    if supports_color(force=force):
        enable_windows_ansi()
    return Style(supports_color(force=force))


async def _run_async(args: argparse.Namespace) -> int:
    st = _style_from_args(args)
    if getattr(args, "tool_rerank", 0):
        settings.tool_rerank_limit = int(args.tool_rerank)
    try:
        models = _resolve_models(args)
    except RuntimeError as exc:
        print(st.red(str(exc)), file=sys.stderr)
        return 2

    tags = set(args.tag) if args.tag else None
    cases = load_cases(app=args.app, case_id=args.case, tags=tags)
    if not cases:
        print(st.red("No cases matched"), file=sys.stderr)
        return 2

    print(st.bold(st.cyan("Fixture bench")), flush=True)
    print(
        st.dim(
            f"  {len(models)} models | {len(cases)} cases | "
            f"{args.app or 'freecad+blender'}"
        ),
        flush=True,
    )
    roles = getattr(args, "_winners_roles", None) or {}
    winners_from = getattr(args, "_winners_from", None)
    if winners_from:
        print(st.dim(f"  winners from → {winners_from}"), flush=True)
    models_from = getattr(args, "_models_from_file", None)
    if models_from:
        print(st.dim(f"  models from → {models_from}"), flush=True)
    if settings.tool_rerank_limit > 0:
        print(st.dim(f"  tool rerank → top {settings.tool_rerank_limit}"), flush=True)
    for m in models:
        role_s = ",".join(roles.get(m) or [])
        suffix = f"  [{role_s}]" if role_s else ""
        print(st.dim(f"  - {m}{suffix}"), flush=True)
    print(flush=True)

    registry = ToolRegistry.load()
    results = []
    total = len(models) * len(cases)
    n = 0
    for model in models:
        print(st.bold(f"-- {short_model(model, 56)} --"), flush=True)
        for case in cases:
            n += 1
            print(
                st.dim(f"  [{n}/{total}] ") + case["id"] + st.dim(" ..."),
                flush=True,
                end="",
            )
            row = await run_case(case, model=model, registry=registry)
            ok = row["score"] >= row["max_score"]
            pct = 100.0 * row["score"] / row["max_score"] if row["max_score"] else 0
            print(
                "\r"
                + st.dim(f"  [{n}/{total}] ")
                + pad_case(case["id"])
                + " "
                + st.pass_fail(ok)
                + f"  {row['score']:.1f}/{row['max_score']:.1f}"
                + st.dim(f"  ({pct:.0f}%)")
                + st.dim(f"  {row['latency_s']:.1f}s")
                + " " * 8,
                flush=True,
            )
            if row.get("notes") and not ok:
                print(st.yellow(f"           -> {'; '.join(row['notes'][:2])}"), flush=True)
            results.append(row)
        print(flush=True)

    out = new_run_dir(results_dir())
    model_info: dict[str, dict] = {}
    try:
        disk = model_size_lookup(
            include_embed=bool(getattr(args, "include_embed", False))
        )
    except RuntimeError:
        disk = {}
    for name in models:
        provider = parse_model_ref(name).provider
        if name in disk:
            model_info[name] = {**disk[name], "provider": provider}
        else:
            model_info[name] = {
                "provider": provider,
                "size": None,
                "parameter_size": None,
                "param_b": parse_param_count_billions(name=name),
            }

    meta = {
        "started": datetime.now(timezone.utc).isoformat(),
        "models": models,
        "all_models": bool(
            getattr(args, "all_models", False)
            or (args.models or "").strip().lower() == "all"
        ),
        "winners": bool(getattr(args, "winners", False)),
        "winners_from": getattr(args, "_winners_from", None),
        "include_embed": bool(getattr(args, "include_embed", False)),
        "models_file": getattr(args, "_models_from_file", None),
        "tool_rerank_limit": settings.tool_rerank_limit,
        "app": args.app,
        "case_count": len(cases),
        "case_ids": [c["id"] for c in cases],
        "model_info": model_info,
    }
    write_run(results, out_dir=out, meta=meta)
    print(render_console(results, meta, color=st.enabled))
    print(st.dim(f"  saved → {out}"))
    print(st.dim(f"         {out / 'summary.md'}"))
    print()
    return 0


def pad_case(case_id: str, width: int = 28) -> str:
    return case_id.ljust(width) if len(case_id) <= width else case_id[: width - 1] + "..."


def cmd_run(args: argparse.Namespace) -> int:
    return asyncio.run(_run_async(args))


def cmd_report(args: argparse.Namespace) -> int:
    st = _style_from_args(args)
    root = results_dir()
    target = Path(args.path) if args.path else latest_results_dir(root)
    if target is None or not target.exists():
        print(st.red("No results found. Run a benchmark first."), file=sys.stderr)
        return 2

    jsonl = target / "results.jsonl"
    meta_path = target / "meta.json"
    if not jsonl.exists():
        # fallback to md only
        summary = target / "summary.md"
        if summary.exists():
            print(summary.read_text(encoding="utf-8"))
            return 0
        print(st.red(f"No results.jsonl in {target}"), file=sys.stderr)
        return 2

    results = load_results_jsonl(jsonl)
    meta = json.loads(meta_path.read_text(encoding="utf-8")) if meta_path.exists() else {}
    print(render_console(results, meta, color=st.enabled))
    print(st.dim(f"  from → {target}"))
    # Refresh summary.md so winner tags stay current with report code
    summary = render_summary_md(results, meta)
    (target / "summary.md").write_text(summary, encoding="utf-8")
    if args.markdown:
        print()
        print(summary)
    return 0


def cmd_list(args: argparse.Namespace) -> int:
    st = _style_from_args(args)
    cases = load_cases(app=args.app)
    print(st.bold(st.cyan("cases")))
    for case in cases:
        tags = ",".join(case.get("tags") or [])
        print(
            f"  {st.green(case['id'].ljust(28))} "
            f"{st.dim(case['app'].ljust(8))} "
            f"{st.dim(tags)}"
        )
        print(st.dim(f"    {case['message'][:70]}"))
    return 0


def cmd_list_models(args: argparse.Namespace) -> int:
    st = _style_from_args(args)
    if getattr(args, "openrouter", False):
        try:
            cloud = list_openrouter_models()
        except RuntimeError as exc:
            print(st.red(str(exc)), file=sys.stderr)
            return 2
        if not cloud:
            print(st.red("No tool-capable OpenRouter models found"), file=sys.stderr)
            return 2
        print(st.bold(st.cyan(f"openrouter tool+json models ({len(cloud)})")))
        for m in cloud:
            ctx = m.get("context_length")
            ctx_s = f"{ctx / 1000:.0f}k" if isinstance(ctx, (int, float)) else "-"
            prompt = m.get("prompt_per_m")
            completion = m.get("completion_per_m")
            price_s = (
                f"${prompt:.2f}/${completion:.2f}/M"
                if isinstance(prompt, (int, float)) and isinstance(completion, (int, float))
                else "-"
            )
            print(
                f"  {st.green(short_model(str(m['id']), 46).ljust(46))} "
                f"{st.dim(ctx_s.ljust(7))} "
                f"{st.dim(price_s)}"
            )
        return 0

    try:
        models = list_disk_models(include_embed=bool(args.include_embed))
    except RuntimeError as exc:
        print(st.red(str(exc)), file=sys.stderr)
        return 2
    if not models:
        print(st.red("No models found"), file=sys.stderr)
        return 2
    print(st.bold(st.cyan(f"ollama models on disk ({len(models)})")))
    for m in models:
        family = m.get("family") or "-"
        params = m.get("parameter_size") or "-"
        size = m.get("size")
        size_s = f"{size / 1e9:.1f}GB" if isinstance(size, (int, float)) else "-"
        print(
            f"  {st.green(short_model(m['name'], 42).ljust(42))} "
            f"{st.dim(str(params).ljust(8))} "
            f"{st.dim(str(family).ljust(10))} "
            f"{st.dim(size_s)}"
        )
    return 0


def _add_color_flag(p: argparse.ArgumentParser) -> None:
    p.add_argument(
        "--no-color",
        action="store_true",
        help="Disable ANSI colors",
    )


def main(argv: list[str] | None = None) -> int:
    configure_stdio()
    parser = argparse.ArgumentParser(prog="fixture_bench", description="Fixture model benchmarks")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_run = sub.add_parser("run", help="Run benchmark cases against Ollama models")
    p_run.add_argument(
        "--models",
        default=None,
        help=(
            "Comma-separated model refs, or 'all' for every chat model on disk. "
            "Bare names are Ollama tags; prefix with openrouter: to bench a "
            "cloud model, e.g. openrouter:anthropic/claude-sonnet-5.5"
        ),
    )
    p_run.add_argument(
        "--all-models",
        action="store_true",
        help="Bench every chat-capable model Ollama reports on disk (skips embed by default)",
    )
    p_run.add_argument(
        "--models-file",
        default=None,
        metavar="PATH",
        help=(
            "File with one model ref per line; blank lines and # comments are "
            "ignored. Mutually exclusive with --models / --all-models / --winners"
        ),
    )
    p_run.add_argument(
        "--tool-rerank",
        type=int,
        default=0,
        metavar="N",
        help=(
            "Send only the N best keyword-matched tools per case (freecad-ai "
            "pattern). 0 keeps the full catalog. Recorded in meta.json"
        ),
    )
    p_run.add_argument(
        "--include-embed",
        action="store_true",
        help="When using --all-models / --models all, also include embedding models",
    )
    p_run.add_argument(
        "--winners",
        action="store_true",
        help=(
            "Bench BEST / FASTEST / BEST-SMALLEST / BEST-FASTEST from the latest "
            "results run (deduped). Mutually exclusive with --models / --all-models"
        ),
    )
    p_run.add_argument(
        "--winners-from",
        default=None,
        metavar="PATH",
        help="Results directory for --winners (default: latest under benchmark/results)",
    )
    p_run.add_argument("--app", choices=["freecad", "blender"], default=None)
    p_run.add_argument("--case", default=None, help="Single case id")
    p_run.add_argument("--tag", action="append", default=[], help="Require tag (repeatable)")
    _add_color_flag(p_run)
    p_run.set_defaults(func=cmd_run)

    p_rep = sub.add_parser("report", help="Print colored leaderboard for a results run")
    p_rep.add_argument("--latest", action="store_true", default=True)
    p_rep.add_argument("--path", default=None, help="Results directory")
    p_rep.add_argument("--markdown", action="store_true", help="Also print summary.md")
    _add_color_flag(p_rep)
    p_rep.set_defaults(func=cmd_report)

    p_list = sub.add_parser("list", help="List available cases")
    p_list.add_argument("--app", choices=["freecad", "blender"], default=None)
    _add_color_flag(p_list)
    p_list.set_defaults(func=cmd_list)

    p_lm = sub.add_parser("list-models", help="List Ollama models on disk (chat by default)")
    p_lm.add_argument(
        "--include-embed",
        action="store_true",
        help="Include embedding models",
    )
    p_lm.add_argument(
        "--openrouter",
        action="store_true",
        help="List OpenRouter models that support tools + JSON output",
    )
    _add_color_flag(p_lm)
    p_lm.set_defaults(func=cmd_list_models)

    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
