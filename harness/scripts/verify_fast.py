"""Fast verification gate: fixtures + pytest + FreeCAD/Blender Path B smokes.

Requires harness on 127.0.0.1:8766. No Path A bench. No GUI soak.

Usage (from repo root):
  python harness/scripts/verify_fast.py
  python harness/scripts/verify_fast.py --list
  python harness/scripts/verify_fast.py --skip-blender
  python harness/scripts/verify_fast.py --keep-going
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = Path(__file__).resolve().parent
MANIFEST_PATH = SCRIPTS / "verify_manifest.json"
HARNESS_URL = "http://127.0.0.1:8766/health"
DEFAULT_FREECAD = Path(r"C:\Program Files\FreeCAD 1.1\bin\freecadcmd.exe")
DEFAULT_BLENDER = Path(
    r"C:\Program Files\Blender Foundation\Blender 5.2\blender.exe"
)

SUMMARY_RE = re.compile(
    r"(?:summary:\s*|===\s*)(\d+)\s*pass\s*/\s*(\d+)\s*fail",
    re.IGNORECASE,
)
PASS_LINE_RE = re.compile(r"^PASS\s+", re.MULTILINE)
FAIL_LINE_RE = re.compile(r"^FAIL\s+", re.MULTILINE)
PYTEST_PASSED_RE = re.compile(r"(\d+)\s+passed")


@dataclass
class StepResult:
    name: str
    ok: bool
    detail: str = ""
    log_path: Path | None = None
    passes: int = 0
    fails: int = 0


@dataclass
class RunState:
    results: list[StepResult] = field(default_factory=list)
    failed: bool = False


def _load_manifest() -> dict[str, list[str]]:
    data = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    return {
        "freecad_smokes": list(data.get("freecad_smokes") or []),
        "blender_smokes": list(data.get("blender_smokes") or []),
    }


def _resolve_binary(env_key: str, default: Path) -> Path:
    raw = os.environ.get(env_key, "").strip()
    return Path(raw) if raw else default


def _preflight_harness() -> None:
    try:
        with urllib.request.urlopen(HARNESS_URL, timeout=5) as resp:
            body = resp.read().decode("utf-8", errors="replace")
            data = json.loads(body)
            if data.get("ok") is False:
                raise RuntimeError(f"harness health not ok: {body[:200]}")
    except urllib.error.URLError as exc:
        raise RuntimeError(
            "Harness not reachable at 127.0.0.1:8766.\n"
            "Start it first:\n"
            '  $env:PYTHONPATH="harness/src"\n'
            "  python -m fixture_cad.main"
        ) from exc
    except Exception as exc:
        raise RuntimeError(f"Harness health check failed: {exc}") from exc


def _parse_smoke_counts(text: str) -> tuple[int, int]:
    matches = list(SUMMARY_RE.finditer(text))
    if matches:
        m = matches[-1]
        return int(m.group(1)), int(m.group(2))
    passes = len(PASS_LINE_RE.findall(text))
    fails = len(FAIL_LINE_RE.findall(text))
    return passes, fails


def _safe_log_name(name: str) -> str:
    """Windows-safe log basename (no colons)."""
    return name.replace(":", "_").replace("/", "_").replace("\\", "_")


def _run_logged(
    name: str,
    cmd: list[str],
    log_dir: Path,
    *,
    env: dict[str, str] | None = None,
    cwd: Path | None = None,
) -> StepResult:
    log_path = log_dir / f"{_safe_log_name(name)}.log"
    print(f"  running {name} ...", flush=True)
    run_env = dict(env) if env is not None else os.environ.copy()
    run_env.setdefault("PYTHONIOENCODING", "utf-8")
    run_env.setdefault("PYTHONUTF8", "1")
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            env=run_env,
            cwd=str(cwd) if cwd else None,
            check=False,
        )
    except FileNotFoundError as exc:
        msg = f"command not found: {cmd[0]} ({exc})"
        log_path.write_text(msg + "\n", encoding="utf-8")
        return StepResult(name=name, ok=False, detail=msg, log_path=log_path)

    combined = ""
    if proc.stdout:
        combined += proc.stdout
    if proc.stderr:
        if combined and not combined.endswith("\n"):
            combined += "\n"
        combined += "--- stderr ---\n" + proc.stderr
    log_path.write_text(combined, encoding="utf-8")

    passes, fails = _parse_smoke_counts(combined)
    ok = proc.returncode == 0 and fails == 0
    if proc.returncode != 0 and passes == 0 and fails == 0:
        detail = f"exit {proc.returncode}"
    else:
        detail = f"{passes}/{fails}"
        if proc.returncode != 0:
            detail += f" exit={proc.returncode}"
    return StepResult(
        name=name,
        ok=ok,
        detail=detail,
        log_path=log_path,
        passes=passes,
        fails=fails,
    )


def _phase_fixtures(log_dir: Path) -> StepResult:
    cmd = [sys.executable, str(SCRIPTS / "validate_fixtures.py")]
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT / "harness" / "src")
    result = _run_logged("fixtures", cmd, log_dir, env=env, cwd=ROOT)
    if result.ok:
        result.detail = "OK"
    return result


def _phase_pytest(log_dir: Path) -> StepResult:
    paths = [
        "harness/tests",
        "clients/freecad_workbench/tests",
        "clients/blender_addon/tests",
        "benchmark/tests",
    ]
    cmd = [sys.executable, "-m", "pytest", *paths, "-q"]
    env = os.environ.copy()
    env["PYTHONPATH"] = os.pathsep.join(
        [
            str(ROOT / "harness" / "src"),
            str(ROOT / "benchmark"),
            str(ROOT / "clients" / "freecad_workbench"),
            str(ROOT / "clients" / "blender_addon"),
        ]
    )
    result = _run_logged("pytest", cmd, log_dir, env=env, cwd=ROOT)
    text = result.log_path.read_text(encoding="utf-8") if result.log_path else ""
    m = PYTEST_PASSED_RE.search(text)
    if m:
        result.detail = f"{m.group(1)} passed"
        result.passes = int(m.group(1))
    elif result.ok:
        result.detail = "OK"
    return result


def _freecad_cmd(freecad: Path, script: Path) -> list[str]:
    # freecadcmd -c: set __file__ so Path(__file__) works inside smokes
    path_lit = str(script).replace("\\", "\\\\")
    code = (
        f"__file__ = r'{path_lit}'; "
        f"exec(compile(open(__file__, encoding='utf-8').read(), __file__, 'exec'))"
    )
    return [str(freecad), "-c", code]


def _blender_cmd(blender: Path, script: Path) -> list[str]:
    return [str(blender), "--background", "--python", str(script)]


def _print_step(index: int, total: int, result: StepResult) -> None:
    status = "OK" if result.ok else "FAIL"
    print(
        f"[{index}/{total}] {result.name}  {result.detail} {status}",
        flush=True,
    )
    if not result.ok and result.log_path:
        print(f"         log: {result.log_path}", flush=True)


def _record(state: RunState, result: StepResult, *, keep_going: bool) -> bool:
    state.results.append(result)
    if not result.ok:
        state.failed = True
        if not keep_going:
            return False
    return True


def _list_steps(skip_freecad: bool, skip_blender: bool) -> None:
    manifest = _load_manifest()
    print("verify_fast steps:")
    print("  1. fixtures  (validate_fixtures.py)")
    print("  2. pytest    harness/tests + freecad + blender tests + benchmark/tests")
    if skip_freecad:
        print("  FreeCAD Path B: (skipped)")
    else:
        print("  FreeCAD Path B:")
        for name in manifest["freecad_smokes"]:
            print(f"    - {name}")
    if skip_blender:
        print("  Blender Path B: (skipped)")
    else:
        print("  Blender Path B:")
        for name in manifest["blender_smokes"]:
            print(f"    - {name}")


def _print_summary(
    run_id: str,
    state: RunState,
    skipped_freecad: bool,
    skipped_blender: bool,
) -> None:
    by_name = {r.name: r for r in state.results}
    fixtures = by_name.get("fixtures")
    pytest_r = by_name.get("pytest")
    fc = [r for r in state.results if r.name.startswith("fc:")]
    bl = [r for r in state.results if r.name.startswith("bl:")]

    fc_pass = sum(r.passes for r in fc)
    fc_fail = sum(r.fails for r in fc)
    bl_pass = sum(r.passes for r in bl)
    bl_fail = sum(r.fails for r in bl)

    print()
    print(f"verify_fast  {run_id}")
    print(
        f"  fixtures          {fixtures.detail if fixtures else '-'}"
    )
    print(
        f"  pytest            {pytest_r.detail if pytest_r else '-'}"
    )
    if fc:
        print(
            f"  freecad smokes    {len(fc)} scripts  "
            f"{fc_pass}/{fc_fail}"
        )
    elif skipped_freecad and not fc:
        print("  freecad smokes    skipped")
    else:
        print("  freecad smokes    -")
    if skipped_blender and not bl:
        print("  blender smokes    skipped")
    elif bl:
        print(
            f"  blender smokes    {len(bl)} scripts  "
            f"{bl_pass}/{bl_fail}"
        )
    else:
        print("  blender smokes    -")
    print(f"RESULT: {'PASS' if not state.failed else 'FAIL'}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Fast gate: fixtures + pytest + Path B smokes"
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="List steps and exit",
    )
    parser.add_argument(
        "--keep-going",
        action="store_true",
        help="Continue after failures; still exit 1 if any failed",
    )
    parser.add_argument(
        "--skip-blender",
        action="store_true",
        help="Skip Blender Path B smokes",
    )
    parser.add_argument(
        "--skip-freecad",
        action="store_true",
        help="Skip FreeCAD Path B smokes",
    )
    args = parser.parse_args(argv)

    if args.list:
        _list_steps(skip_freecad=args.skip_freecad, skip_blender=args.skip_blender)
        return 0

    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    log_dir = ROOT / "artifacts" / "verify" / run_id
    log_dir.mkdir(parents=True, exist_ok=True)

    freecad = _resolve_binary("FREECAD_CMD", DEFAULT_FREECAD)
    blender = _resolve_binary("BLENDER_EXE", DEFAULT_BLENDER)
    manifest = _load_manifest()

    fc_dir = ROOT / "clients" / "freecad_workbench"
    bl_dir = ROOT / "clients" / "blender_addon"
    fc_scripts = [fc_dir / name for name in manifest["freecad_smokes"]]
    bl_scripts = [bl_dir / name for name in manifest["blender_smokes"]]

    for script in fc_scripts:
        if not script.is_file():
            print(f"FAIL  missing FreeCAD smoke: {script}", flush=True)
            return 1
    if not args.skip_blender:
        for script in bl_scripts:
            if not script.is_file():
                print(f"FAIL  missing Blender smoke: {script}", flush=True)
                return 1

    print(f"verify_fast  {run_id}", flush=True)
    print(f"  logs -> {log_dir}", flush=True)

    try:
        _preflight_harness()
        print("  preflight harness  OK", flush=True)
    except RuntimeError as exc:
        print(f"FAIL  preflight\n{exc}", flush=True)
        return 1

    skip_blender = args.skip_blender
    skip_freecad = args.skip_freecad
    if not skip_blender and not blender.is_file():
        print(
            f"FAIL  Blender binary not found: {blender}\n"
            "Set BLENDER_EXE or pass --skip-blender",
            flush=True,
        )
        return 1
    if not skip_freecad and not freecad.is_file():
        print(
            f"FAIL  FreeCAD binary not found: {freecad}\n"
            "Set FREECAD_CMD or pass --skip-freecad",
            flush=True,
        )
        return 1

    state = RunState()
    total = 2 + (0 if skip_freecad else len(fc_scripts)) + (
        0 if skip_blender else len(bl_scripts)
    )
    step_i = 0

    # Phase 1
    for runner in (_phase_fixtures, _phase_pytest):
        step_i += 1
        result = runner(log_dir)
        _print_step(step_i, total, result)
        if not _record(state, result, keep_going=args.keep_going):
            _print_summary(
                run_id,
                state,
                skipped_freecad=skip_freecad,
                skipped_blender=skip_blender,
            )
            return 1

    # Phase 2 - FreeCAD
    if not skip_freecad:
        for script in fc_scripts:
            step_i += 1
            name = f"fc:{script.name}"
            result = _run_logged(
                name,
                _freecad_cmd(freecad, script),
                log_dir,
                cwd=ROOT,
            )
            # Prefer short display name in status line
            display = StepResult(
                name=script.name,
                ok=result.ok,
                detail=result.detail,
                log_path=result.log_path,
                passes=result.passes,
                fails=result.fails,
            )
            _print_step(step_i, total, display)
            # Keep namespaced name in state for summary grouping
            result.name = name
            if not _record(state, result, keep_going=args.keep_going):
                _print_summary(
                    run_id,
                    state,
                    skipped_freecad=skip_freecad,
                    skipped_blender=skip_blender,
                )
                return 1

    # Phase 3 — Blender
    if not skip_blender:
        for script in bl_scripts:
            step_i += 1
            name = f"bl:{script.name}"
            result = _run_logged(
                name,
                _blender_cmd(blender, script),
                log_dir,
                cwd=ROOT,
            )
            display = StepResult(
                name=script.name,
                ok=result.ok,
                detail=result.detail,
                log_path=result.log_path,
                passes=result.passes,
                fails=result.fails,
            )
            _print_step(step_i, total, display)
            result.name = name
            if not _record(state, result, keep_going=args.keep_going):
                _print_summary(
                    run_id,
                    state,
                    skipped_freecad=skip_freecad,
                    skipped_blender=False,
                )
                return 1

    _print_summary(
        run_id,
        state,
        skipped_freecad=skip_freecad,
        skipped_blender=skip_blender,
    )
    return 1 if state.failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
