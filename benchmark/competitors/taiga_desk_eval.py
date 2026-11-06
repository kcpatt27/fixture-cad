"""Goal-compiler experiment: fixed desk-mount goals through Biome-S1 (Taiga-S1).

The executor half of the planner pairing: a System-2 compiler turns an NL
request into an ordered feature goal (the JSON shape in
`taiga_desk_goals.json`); this script feeds those fixed goals through the
pinned biome-s1 clone (never vendored):

  1. **feasibility** — the scripted expert builds the goal headlessly
     (`build_target`), proving the feature list is accepted by the runtime;
  2. **execution** — the released Taiga-S1 checkpoint drives live headless
     FreeCAD from a clean PartDesign start, argmax actions. Success/clean use
     the repo's native-eval definitions: `Done` issued and the final solid
     matches the expert target with volumetric IoU >= 0.99 (clean = no stray
     objects left).

Set `BIOME_S1_REPO` to a biome-s1 clone (defaults to the OpenCode temp clone)
and run with the clone's venv. `FREECAD_PYTHON` / `FREECAD_LIB` must point at
a FreeCAD install with a scriptable Python (FreeCAD 1.1 here).

Usage (PowerShell, biome-s1 venv):

  $env:FREECAD_PYTHON = "C:\\Program Files\\FreeCAD 1.1\\bin\\python.exe"
  $env:FREECAD_LIB    = "C:\\Program Files\\FreeCAD 1.1\\bin"
  & "$env:TEMP\\opencode\\biome-s1-analysis\\biome-s1-main\\.venv\\Scripts\\python.exe" `
      benchmark/competitors/taiga_desk_eval.py `
      --goals benchmark/competitors/taiga_desk_goals.json `
      --out benchmark/results/<UTC>/taiga_desk.json
"""

from __future__ import annotations

import argparse
import json
import os
import random
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

DEFAULT_REPO = Path(
    os.environ.get(
        "BIOME_S1_REPO",
        str(Path(tempfile.gettempdir()) / "opencode" / "biome-s1-analysis" / "biome-s1-main"),
    )
)
# A fresh PartDesign document: what a client would hand the executor.
START = {"doc_open": True, "workbench": "PartDesignWorkbench"}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--goals", required=True, help="JSON file: {name: {level, scale, features}}")
    ap.add_argument("--out", default=None, help="write the full JSON report here")
    ap.add_argument("--repo", default=str(DEFAULT_REPO), help="biome-s1 clone path")
    ap.add_argument("--ckpt", default=None, help="checkpoint file/dir/repo id (default <repo>/release/hf)")
    ap.add_argument("--device", default="cpu", help="torch device (cpu keeps the shared GPU free)")
    ap.add_argument("--perturb", type=float, default=0.0, help="probability of random valid actions (recovery stress)")
    ap.add_argument("--sample", action="store_true", help="sample actions instead of argmax")
    ap.add_argument("--repeat", type=int, default=1, help="episodes per goal")
    args = ap.parse_args(argv)

    repo = Path(args.repo)
    if not (repo / "freecad_s1").is_dir():
        raise SystemExit(f"biome-s1 clone not found at {repo}; set BIOME_S1_REPO")
    sys.path.insert(0, str(repo))

    from freecad_s1.model.net import from_pretrained, select_device
    from freecad_s1.rollout import Policy, run_episodes
    from freecad_s1.runtime.client import VecEnv, WorkerError
    from freecad_s1.schema import Goal

    goals_data = json.loads(Path(args.goals).read_text(encoding="utf-8"))
    goals = {name: Goal.from_json(spec) for name, spec in goals_data.items()}

    ckpt = args.ckpt or str(repo / "release" / "hf")
    device = select_device(args.device)
    model = from_pretrained(ckpt, device)
    policy = Policy(model, device)
    print(f"checkpoint {ckpt} on {device}; {len(goals)} goal(s) from {args.goals}", flush=True)

    report: dict = {
        "kind": "taiga-desk-goals",
        "started": datetime.now(timezone.utc).isoformat(),
        "checkpoint": str(ckpt),
        "goals_file": str(args.goals),
        "perturb": args.perturb,
        "repeat": max(1, args.repeat),
        "results": [],
    }

    vec = VecEnv(1)  # one worker, goals run sequentially so one bad goal cannot kill the batch
    try:
        for name, goal in goals.items():
            entry: dict = {
                "name": name,
                "level": goal.level,
                "scale": goal.scale,
                "features": [f.kind for f in goal.features],
            }
            started = time.perf_counter()

            # -- boundary 1: is the goal feasible for the scripted expert? --
            try:
                resp = vec.envs[0].call(
                    {"op": "reset", "goal": goal.to_json(), "start": START, "level": goal.level}
                )
            except WorkerError as exc:
                entry.update(feasible=False, error=str(exc), runs=[])
                print(f"[{name}] INFEASIBLE: {exc}", flush=True)
                report["results"].append(entry)
                continue
            entry["feasible"] = True
            entry["target"] = resp["goal"].get("target")
            entry["expert_budget"] = resp.get("budget")
            t = entry["target"] or {}
            print(
                f"[{name}] expert build ok: vol={t.get('volume')} bbox={t.get('bbox')} "
                f"faces={t.get('n_faces')} budget={entry['expert_budget']}",
                flush=True,
            )

            # -- boundary 2: can the released policy build it from a live start? --
            spec = {"goal": goal.to_json(), "start": START, "level": goal.level}
            runs: list[dict] = []
            for rep in range(max(1, args.repeat)):
                try:
                    eps = run_episodes(
                        policy, vec, [spec], sample=args.sample,
                        rng=random.Random(2000 + rep), perturb=args.perturb,
                    )
                except WorkerError as exc:
                    runs.append({"error": str(exc)})
                    print(f"[{name}] run {rep + 1} failed: {exc}", flush=True)
                    continue
                r = eps[0]
                runs.append(
                    {
                        "success": r.success,
                        "clean": r.clean,
                        "iou": round(r.iou, 4),
                        "steps": r.steps,
                        "expert_steps": r.expert_steps,
                        "budget": r.budget,
                        "agreement": round(r.agreement, 4),
                        "deviations": r.deviations,
                        "outcome": r.outcome,
                        "history": r.history,
                    }
                )
                print(
                    f"[{name}] run {rep + 1}: success={r.success} clean={r.clean} "
                    f"iou={r.iou:.4f} steps={r.steps}/{r.expert_steps} outcome={r.outcome}",
                    flush=True,
                )
            entry["runs"] = runs
            entry["latency_s"] = round(time.perf_counter() - started, 2)
            report["results"].append(entry)
    finally:
        vec.close()
    report["finished"] = datetime.now(timezone.utc).isoformat()

    print("\n| goal | level | feasible | success | clean | IoU | steps | expert | outcome |")
    print("|---|---:|---|---:|---:|---:|---:|---:|---|")
    for e in report["results"]:
        if not e.get("feasible"):
            print(f"| {e['name']} | {e['level']} | no | - | - | - | - | - | {e.get('error', '')[:60]} |")
            continue
        r = e["runs"][0] if e["runs"] else {}
        print(
            f"| {e['name']} | {e['level']} | yes | {int(bool(r.get('success')))} | "
            f"{int(bool(r.get('clean')))} | {r.get('iou', 0.0):.4f} | "
            f"{r.get('steps', '-')} | {r.get('expert_steps', '-')} | {r.get('outcome', '')} |"
        )

    if args.out:
        out = Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(f"\nsaved -> {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())