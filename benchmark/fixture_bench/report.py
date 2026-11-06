from __future__ import annotations

import json
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .models import model_size_lookup, parse_param_count_billions
from .style import Style, pad, pad_ansi, short_model, supports_color

# Competence floor for BEST-SMALLEST / BEST-FASTEST (strictly over 90%).
ACCURACY_FLOOR_PCT = 90.0

# Primary leaderboard slots used by `--winners` (order preserved, deduped).
WINNER_PRESET_SLOTS: tuple[tuple[str, str], ...] = (
    ("best", "BEST"),
    ("fastest", "FASTEST"),
    ("best_smallest", "BEST-SMALLEST"),
    ("best_fastest", "BEST-FASTEST"),
)


def aggregate(
    results: list[dict[str, Any]],
    *,
    size_by_model: dict[str, dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    by_model: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in results:
        by_model[row["model"]].append(row)

    sizes = size_by_model or {}
    rows: list[dict[str, Any]] = []
    for model, items in by_model.items():
        total = sum(r["score"] for r in items)
        max_total = sum(r["max_score"] for r in items)
        pct = (100.0 * total / max_total) if max_total else 0.0
        avg_lat = sum(r["latency_s"] for r in items) / max(len(items), 1)
        fails = [r["case_id"] for r in items if r["score"] < r["max_score"]]
        passes = sum(1 for r in items if r["score"] >= r["max_score"])
        info = sizes.get(model) or {}
        param_b = info.get("param_b")
        if param_b is None:
            param_b = parse_param_count_billions(
                info.get("parameter_size") if isinstance(info.get("parameter_size"), str) else None,
                name=model,
            )
        rows.append(
            {
                "model": model,
                "score": total,
                "max_score": max_total,
                "pct": pct,
                "avg_latency_s": avg_lat,
                "passes": passes,
                "fails": fails,
                "n_cases": len(items),
                "param_b": param_b,
                "size": info.get("size"),
                "parameter_size": info.get("parameter_size"),
            }
        )
    return rows


def resolve_size_by_model(meta: dict[str, Any] | None) -> dict[str, dict[str, Any]]:
    """Prefer sizes stored in run meta; else query Ollama tags."""
    meta = meta or {}
    stored = meta.get("model_info")
    if isinstance(stored, dict) and stored:
        out: dict[str, dict[str, Any]] = {}
        for name, info in stored.items():
            if not isinstance(info, dict):
                continue
            param_s = info.get("parameter_size")
            param_b = info.get("param_b")
            if param_b is None:
                param_b = parse_param_count_billions(
                    param_s if isinstance(param_s, str) else None,
                    name=str(name),
                )
            out[str(name)] = {
                "size": info.get("size"),
                "parameter_size": param_s,
                "param_b": param_b,
            }
        if out:
            return out
    try:
        return model_size_lookup(
            include_embed=bool(meta.get("include_embed")),
        )
    except RuntimeError:
        return {}


def _size_key(row: dict[str, Any]) -> tuple[float, float]:
    """Sort key: smaller params first; unknown params sort last via disk size."""
    param_b = row.get("param_b")
    if isinstance(param_b, (int, float)):
        return (0.0, float(param_b))
    disk = row.get("size")
    if isinstance(disk, (int, float)):
        return (1.0, float(disk))
    return (2.0, float("inf"))


def _nth(rows: list[dict[str, Any]], n: int) -> dict[str, Any] | None:
    return rows[n] if len(rows) > n else None


def pick_winners(agg: list[dict[str, Any]]) -> dict[str, Any]:
    empty = {
        "best": None,
        "fastest": None,
        "best_smallest": None,
        "best_fastest": None,
        "best2": None,
        "fastest2": None,
        "best_smallest2": None,
        "best_fastest2": None,
        "ranked_score": [],
        "ranked_speed": [],
    }
    if not agg:
        return empty

    by_score = sorted(
        agg, key=lambda r: (-r["pct"], -r["score"], r["avg_latency_s"], r["model"])
    )
    by_speed = sorted(agg, key=lambda r: (r["avg_latency_s"], -r["pct"], r["model"]))
    best = by_score[0]
    fastest = by_speed[0]

    competent = [r for r in agg if r["pct"] > ACCURACY_FLOOR_PCT]
    by_small = sorted(
        competent,
        key=lambda r: (
            _size_key(r),
            -r["pct"],
            -r["score"],
            r["avg_latency_s"],
            r["model"],
        ),
    )
    by_best_fast = sorted(
        competent,
        key=lambda r: (
            r["avg_latency_s"],
            -r["pct"],
            -r["score"],
            _size_key(r),
            r["model"],
        ),
    )

    return {
        "best": best,
        "fastest": fastest,
        "best_smallest": _nth(by_small, 0),
        "best_fastest": _nth(by_best_fast, 0),
        "best2": _nth(by_score, 1),
        "fastest2": _nth(by_speed, 1),
        "best_smallest2": _nth(by_small, 1),
        "best_fastest2": _nth(by_best_fast, 1),
        "ranked_score": by_score,
        "ranked_speed": by_speed,
    }


def winner_preset_models(
    results: list[dict[str, Any]],
    meta: dict[str, Any] | None = None,
) -> tuple[list[str], dict[str, list[str]]]:
    """Unique models for BEST / FASTEST / BEST-SMALLEST / BEST-FASTEST.

    Returns ``(ordered_names, roles_by_model)``. BEST-SMALLEST / BEST-FASTEST
    are omitted when no model clears the accuracy floor.
    """
    sizes = resolve_size_by_model(meta)
    winners = pick_winners(aggregate(results, size_by_model=sizes))
    ordered: list[str] = []
    roles: dict[str, list[str]] = {}
    for key, label in WINNER_PRESET_SLOTS:
        row = winners.get(key)
        if not isinstance(row, dict):
            continue
        name = row.get("model")
        if not isinstance(name, str) or not name:
            continue
        roles.setdefault(name, []).append(label)
        if name not in ordered:
            ordered.append(name)
    return ordered, roles


def load_winner_preset_from_run(
    run_dir: Path,
) -> tuple[list[str], dict[str, list[str]]]:
    """Load winner-preset models from a results directory."""
    jsonl = run_dir / "results.jsonl"
    if not jsonl.exists():
        raise RuntimeError(f"No results.jsonl in {run_dir}")
    meta_path = run_dir / "meta.json"
    meta: dict[str, Any] = {}
    if meta_path.exists():
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
    results = load_results_jsonl(jsonl)
    if not results:
        raise RuntimeError(f"Empty results.jsonl in {run_dir}")
    names, roles = winner_preset_models(results, meta)
    if not names:
        raise RuntimeError(f"No winner models found in {run_dir}")
    return names, roles


def _format_params(row: dict[str, Any]) -> str:
    param_s = row.get("parameter_size")
    if isinstance(param_s, str) and param_s.strip():
        raw = param_s.strip()
        # Keep leaderboard size column ≤7 chars when possible (fits pad 8).
        if len(raw) <= 7:
            return raw
        param_b = parse_param_count_billions(raw)
        if param_b is not None:
            if param_b < 1.0:
                return f"{param_b * 1000:.0f}M"
            if param_b >= 10:
                return f"{param_b:.1f}B"
            return f"{param_b:.2f}B".rstrip("0").rstrip(".") + "B"
        return raw[:7]
    param_b = row.get("param_b")
    if isinstance(param_b, (int, float)):
        if param_b < 1.0:
            return f"{param_b * 1000:.0f}M"
        if param_b >= 10:
            return f"{param_b:.1f}B"
        return f"{param_b:.2f}B".rstrip("0").rstrip(".") + "B"
    return "?"


def write_run(
    results: list[dict[str, Any]],
    *,
    out_dir: Path,
    meta: dict[str, Any],
) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    with (out_dir / "results.jsonl").open("w", encoding="utf-8") as fh:
        for row in results:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
    summary = render_summary_md(results, meta)
    (out_dir / "summary.md").write_text(summary, encoding="utf-8")
    return out_dir


def render_summary_md(results: list[dict[str, Any]], meta: dict[str, Any]) -> str:
    sizes = resolve_size_by_model(meta)
    agg = aggregate(results, size_by_model=sizes)
    winners = pick_winners(agg)
    best = winners.get("best")
    fastest = winners.get("fastest")
    best_smallest = winners.get("best_smallest")
    best_fastest = winners.get("best_fastest")

    lines = [
        "# Fixture benchmark summary",
        "",
        f"- started: `{meta.get('started')}`",
        f"- models: {len(meta.get('models') or [])}",
        f"- apps: {meta.get('app') or 'freecad+blender'}",
        f"- cases: {meta.get('case_count')}",
        "",
        "## Winners",
        "",
    ]
    if best:
        lines.append(
            f"- **BEST (accuracy):** `{best['model']}` — "
            f"**{best['pct']:.1f}%** ({best['score']:.1f}/{best['max_score']:.1f}) "
            f"avg {best['avg_latency_s']:.2f}s"
        )
    if fastest:
        lines.append(
            f"- **FASTEST (avg latency):** `{fastest['model']}` — "
            f"**{fastest['avg_latency_s']:.2f}s** "
            f"({fastest['pct']:.1f}% accuracy)"
        )
    if best_smallest:
        lines.append(
            f"- **BEST-SMALLEST (>{ACCURACY_FLOOR_PCT:.0f}% accuracy, fewest params):** "
            f"`{best_smallest['model']}` — "
            f"**{_format_params(best_smallest)}** · "
            f"**{best_smallest['pct']:.1f}%** "
            f"({best_smallest['score']:.1f}/{best_smallest['max_score']:.1f}) "
            f"avg {best_smallest['avg_latency_s']:.2f}s"
        )
    if best_fastest:
        lines.append(
            f"- **BEST-FASTEST (>{ACCURACY_FLOOR_PCT:.0f}% accuracy, lowest latency):** "
            f"`{best_fastest['model']}` — "
            f"**{best_fastest['avg_latency_s']:.2f}s** · "
            f"**{best_fastest['pct']:.1f}%** "
            f"({best_fastest['score']:.1f}/{best_fastest['max_score']:.1f})"
        )
    if best and fastest and best["model"] == fastest["model"]:
        lines.append(f"- **BEST OVERALL:** `{best['model']}` (wins accuracy + speed)")

    lines.extend(
        [
            "",
            "## Leaderboard (by accuracy)",
            "",
            "| # | model | accuracy | score | avg s | size | pass/fail |",
            "|--:|---|---:|---:|---:|---:|---|",
        ]
    )
    for i, row in enumerate(winners.get("ranked_score") or [], start=1):
        mark = ""
        if best and row["model"] == best["model"]:
            mark = " BEST"
        if fastest and row["model"] == fastest["model"]:
            mark += " FASTEST"
        if best_smallest and row["model"] == best_smallest["model"]:
            mark += " BEST-SMALL"
        if best_fastest and row["model"] == best_fastest["model"]:
            mark += " BEST-FAST"
        fail_n = len(row["fails"])
        lines.append(
            f"| {i} | `{row['model']}`{mark} | {row['pct']:.1f}% | "
            f"{row['score']:.1f}/{row['max_score']:.1f} | {row['avg_latency_s']:.2f} | "
            f"{_format_params(row)} | {row['passes']}/{fail_n} |"
        )

    lines.extend(["", "## Per-case detail", ""])
    by_model: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in results:
        by_model[row["model"]].append(row)
    for model in [r["model"] for r in (winners.get("ranked_score") or [])]:
        items = by_model[model]
        lines.append(f"### `{model}`")
        lines.append("")
        lines.append("| case | app | score | s | missed |")
        lines.append("|---|---|---:|---:|---|")
        for r in items:
            missed = [k for k, ok in (r.get("checks") or {}).items() if not ok]
            lines.append(
                f"| `{r['case_id']}` | {r['app']} | {r['score']:.1f}/{r['max_score']:.1f} | "
                f"{r['latency_s']:.2f} | {', '.join(missed) or '-'} |"
            )
        lines.append("")

    return "\n".join(lines) + "\n"


def render_console(
    results: list[dict[str, Any]],
    meta: dict[str, Any],
    *,
    color: bool | None = None,
) -> str:
    st = Style(supports_color(force=color))
    sizes = resolve_size_by_model(meta)
    agg = aggregate(results, size_by_model=sizes)
    winners = pick_winners(agg)
    best = winners.get("best")
    fastest = winners.get("fastest")
    best_smallest = winners.get("best_smallest")
    best_fastest = winners.get("best_fastest")
    best2 = winners.get("best2")
    fastest2 = winners.get("fastest2")
    best_smallest2 = winners.get("best_smallest2")
    best_fastest2 = winners.get("best_fastest2")
    ranked = winners.get("ranked_score") or []

    width = 86
    bar = st.dim("=" * width)
    thin = st.dim("-" * width)
    out: list[str] = []
    out.append("")
    out.append(st.bold(st.cyan("=== Fixture BENCH RESULTS " + "=" * 54)))
    out.append(st.dim(
        f"  {meta.get('case_count')} cases | "
        f"{len(meta.get('models') or [])} models | "
        f"{meta.get('app') or 'freecad+blender'}"
    ))
    out.append(bar)

    if best:
        out.append(
            st.green(st.bold("  >>> BEST          "))
            + short_model(best["model"], 36)
            + st.dim("  ")
            + st.green(f"{best['pct']:.1f}%")
            + st.dim(f"  ({best['score']:.1f}/{best['max_score']:.1f})")
            + st.dim(f"  avg {best['avg_latency_s']:.2f}s")
        )
    if fastest:
        out.append(
            st.magenta(st.bold("  >>> FASTEST       "))
            + short_model(fastest["model"], 36)
            + st.dim("  ")
            + st.magenta(f"{fastest['avg_latency_s']:.2f}s")
            + st.dim(f"  ({fastest['pct']:.1f}% accuracy)")
        )
    if best_smallest:
        out.append(
            st.cyan(st.bold("  >>> BEST-SMALLEST "))
            + short_model(best_smallest["model"], 36)
            + st.dim("  ")
            + st.blue(_format_params(best_smallest))
            + st.dim("  ")
            + st.green(f"{best_smallest['pct']:.1f}%")
            + st.dim(f"  avg {best_smallest['avg_latency_s']:.2f}s")
        )
    if best_fastest:
        out.append(
            st.yellow(st.bold("  >>> BEST-FASTEST  "))
            + short_model(best_fastest["model"], 36)
            + st.dim("  ")
            + st.yellow(f"{best_fastest['avg_latency_s']:.2f}s")
            + st.dim("  ")
            + st.green(f"{best_fastest['pct']:.1f}%")
            + st.dim(f"  ({best_fastest['score']:.1f}/{best_fastest['max_score']:.1f})")
        )
    if best and fastest and best["model"] == fastest["model"]:
        out.append(
            st.yellow(st.bold("  >>> OVERALL       "))
            + short_model(best["model"], 36)
            + st.yellow("  (wins accuracy + speed)")
        )

    out.append(thin)
    model_w = 36
    hdr = (
        pad("#", 3)
        + pad("model", model_w)
        + pad("accuracy", 10, right=True)
        + pad("score", 12, right=True)
        + pad("avg s", 8, right=True)
        + pad("size", 8, right=True)
        + pad("P/F", 7, right=True)
    )
    out.append(st.dim("  " + hdr))
    out.append(st.dim("  " + "-" * (width - 2)))

    for i, row in enumerate(ranked, start=1):
        is_best = bool(best and row["model"] == best["model"])
        is_fast = bool(fastest and row["model"] == fastest["model"])
        is_small = bool(best_smallest and row["model"] == best_smallest["model"])
        is_best_fast = bool(best_fastest and row["model"] == best_fastest["model"])
        is_best2 = bool(best2 and row["model"] == best2["model"])
        is_fast2 = bool(fastest2 and row["model"] == fastest2["model"])
        is_small2 = bool(best_smallest2 and row["model"] == best_smallest2["model"])
        is_best_fast2 = bool(best_fastest2 and row["model"] == best_fastest2["model"])

        # Plain tags first so we can size the name column accurately.
        tag_plain: list[str] = []
        if is_best:
            tag_plain.append("BEST")
        if is_fast:
            tag_plain.append("FAST")
        if is_small:
            tag_plain.append("BEST-SMALL")
        if is_best_fast:
            tag_plain.append("BEST-FAST")
        tag_plain_s = (" " + " ".join(tag_plain)) if tag_plain else ""

        tags = []
        if is_best:
            tags.append(st.hue("32", "BEST", bold=True))
        if is_fast:
            tags.append(st.hue("35", "FAST", bold=True))
        if is_small:
            tags.append(st.hue("36", "BEST-SMALL"))
        if is_best_fast:
            tags.append(st.hue("33", "BEST-FAST"))
        tag_s = (" " + " ".join(tags)) if tags else ""

        # Reserve space for tags so pad_ansi never overflows.
        name_budget = max(8, model_w - len(tag_plain_s))
        name = short_model(row["model"], name_budget)
        if is_best:
            name = st.hue("32", name, bold=True)
        elif is_small:
            name = st.hue("36", name, bold=True)
        elif is_best_fast:
            name = st.hue("33", name, bold=True)
        elif is_fast:
            name = st.hue("35", name, bold=True)
        name_col = pad_ansi(name + tag_s, model_w)

        pct_s = f"{row['pct']:.1f}%"
        if is_best or is_best2 or row["pct"] >= 99.9:
            pct_s = st.hue("32", pct_s, bold=is_best)
        pct_col = pad_ansi(pct_s, 10, right=True)

        score_col = pad(f"{row['score']:.1f}/{row['max_score']:.1f}", 12, right=True)

        lat_s = f"{row['avg_latency_s']:.2f}"
        if is_fast:
            lat_s = st.hue("35", lat_s, bold=True)
        elif is_best_fast:
            lat_s = st.hue("33", lat_s, bold=True)
        elif is_fast2:
            lat_s = st.hue("35", lat_s)
        elif is_best_fast2:
            lat_s = st.hue("33", lat_s)
        lat_col = pad_ansi(lat_s, 8, right=True)

        size_s = _format_params(row)
        if is_small:
            size_s = st.hue("34", size_s, bold=True)
        elif is_small2:
            size_s = st.hue("34", size_s)
        size_col = pad_ansi(size_s, 8, right=True)

        pf = f"{row['passes']}/{len(row['fails'])}"
        pf_col = pad(pf, 7, right=True)
        out.append(
            f"  {pad(str(i), 3)}{name_col}{pct_col}{score_col}{lat_col}{size_col}{pf_col}"
        )

    out.append(bar)
    out.append(
        st.dim(
            "  Tip: open summary.md for per-case misses. "
            "BEST-SMALLEST / BEST-FASTEST require >90% accuracy."
        )
    )
    out.append("")
    return "\n".join(out)


def latest_results_dir(results_root: Path) -> Path | None:
    if not results_root.exists():
        return None
    dirs = sorted([p for p in results_root.iterdir() if p.is_dir()], reverse=True)
    return dirs[0] if dirs else None


def new_run_dir(results_root: Path) -> Path:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return results_root / stamp


def load_results_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows
