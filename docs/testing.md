# Testing

Testing summary. Run every command from the repo root.

## Fast gate

One command: fixtures + pytest + FreeCAD/Blender Path B smokes. Requires the
harness on `127.0.0.1:8766`.

```powershell
python harness/scripts/verify_fast.py
```

Useful flags:

```powershell
python harness/scripts/verify_fast.py --list
python harness/scripts/verify_fast.py --skip-freecad
python harness/scripts/verify_fast.py --skip-blender
python harness/scripts/verify_fast.py --keep-going
```

No Path A bench, no GUI soak. Gate logs land per-run in
`artifacts/verify/<UTC-timestamp>/` (one `.log` per step, e.g. `pytest.log`).

## Harness pytest

The gate runs pytest over the harness, the FreeCAD client, and the bench
suites:

```powershell
python -m pytest harness/tests clients/freecad_workbench/tests clients/blender_addon/tests benchmark/tests -q
```

Without an installed harness, set `PYTHONPATH` first:

```powershell
$env:PYTHONPATH = "harness/src;benchmark;clients/freecad_workbench;clients/blender_addon"
python -m pytest harness/tests clients/freecad_workbench/tests clients/blender_addon/tests benchmark/tests -q
```

Focused fallback:

```powershell
python -m pytest harness/tests benchmark/tests -q
```

## Benchmarks

Path A planner bench (no FreeCAD/Blender GUI), from the repo root:

```powershell
$env:PYTHONPATH = "benchmark"
python -m fixture_bench list
python -m fixture_bench list-models
python -m fixture_bench run --all-models
python -m fixture_bench run --models-file benchmark/models.txt
python -m fixture_bench report --latest
```

Results land in `benchmark/results/<UTC-timestamp>/` as `results.jsonl` +
`summary.md` (plus `meta.json`). Details: `benchmark/README.md`,
`docs/benchmark.md`.

## Separately gated

FreeCAD GUI soak tests and Path A planner benches are not part of the fast gate;
run them on their own. Local model runs use the shared GPU — check
`benchmark/check_gpu.ps1` first.

## Known gaps

The manual FreeCAD GUI soak remains open. Automated ExplainSelection and chat
smokes run in the gate (`smoke_freecad.py`, `smoke_chat_threading.py`), so the
gap is interactive GUI coverage, not the smoke path. See `README.md` for
current known gaps and the fast gate result.
