"""Merge the latest per-model Fixture runs into one head-to-head leaderboard.

Reads `benchmark/results/*/meta.json` + `results.jsonl` (one model per run makes
each run unambiguous), keeps the newest run per model, and renders a markdown
table with accuracy, latency, and provider-error counts (so throttled runs are
obvious rather than silently scoring ~0%).

Usage:
  python -m competitors.merge_leaderboard [--min-cases 60] [--out PATH]
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from fixture_bench.cases import results_dir


def load_latest_runs(root: Path, *, min_cases: int) -> dict[str, dict]:
    latest: dict[str, dict] = {}
    for meta_path in sorted(root.glob("*/meta.json"), key=lambda p: p.parent.name):
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if meta.get("kind") == "headtohead":
            continue
        models = meta.get("models") or []
        if len(models) != 1:
            continue
        if int(meta.get("case_count") or 0) < min_cases:
            continue
        results_path = meta_path.parent / "results.jsonl"
        if not results_path.exists():
            continue
        rows = [
            json.loads(line)
            for line in results_path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        if not rows:
            continue
        score = sum(float(r.get("score", 0)) for r in rows)
        max_score = sum(float(r.get("max_score", 0)) for r in rows)
        served = [r for r in rows if not r.get("error")]
        served_score = sum(float(r.get("score", 0)) for r in served)
        served_max = sum(float(r.get("max_score", 0)) for r in served)
        passes = sum(1 for r in rows if r.get("score") == r.get("max_score"))
        errors = sum(1 for r in rows if r.get("error"))
        genuine_fails = sum(
            1
            for r in served
            if float(r.get("score", 0)) != float(r.get("max_score", 0))
        )
        latency = sum(float(r.get("latency_s", 0)) for r in rows) / len(rows)
        latest[models[0]] = {
            "run": meta_path.parent.name,
            "cases": len(rows),
            "score": score,
            "max_score": max_score,
            "accuracy": (score / max_score * 100.0) if max_score else 0.0,
            "served_accuracy": (served_score / served_max * 100.0) if served_max else 0.0,
            "served": len(served),
            "pass": passes,
            "fail": len(rows) - passes,
            "genuine_fails": genuine_fails,
            "errors": errors,
            "avg_latency_s": latency,
        }
    return latest


def render_leaderboard(runs: dict[str, dict]) -> str:
    ordered = sorted(
        runs.items(),
        key=lambda item: (-item[1]["accuracy"], item[1]["avg_latency_s"]),
    )
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    lines = [
        f"# Fixture head-to-head — leaderboard ({stamp})",
        "",
        "| # | model | raw accuracy | served accuracy | served n | genuine fails | avg s | provider errors | run |",
        "|--:|---|---:|---:|---:|---:|---:|---:|---|",
    ]
    for index, (model, info) in enumerate(ordered, start=1):
        lines.append(
            f"| {index} | `{model}` | {info['accuracy']:.1f}% | "
            f"{info['served_accuracy']:.1f}% | "
            f"{info['served']}/{info['cases']} | {info['genuine_fails']} | "
            f"{info['avg_latency_s']:.2f} | {info['errors']} | {info['run']} |"
        )
    lines.append("")
    lines.append(
        "Ranked by **raw accuracy** (provider errors count against practical use). "
        "**Served accuracy** excludes provider-error rows, so it isolates model "
        "quality on requests that were actually answered."
    )
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--min-cases", type=int, default=60)
    parser.add_argument("--out", default=None)
    args = parser.parse_args(argv)

    runs = load_latest_runs(results_dir(), min_cases=args.min_cases)
    if not runs:
        print("No single-model runs with at least", args.min_cases, "cases found")
        return 2
    table = render_leaderboard(runs)
    print(table)
    out = Path(args.out) if args.out else results_dir().parent / "headtohead_leaderboard.md"
    out.write_text(table + "\n", encoding="utf-8")
    print(f"\nsaved -> {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())