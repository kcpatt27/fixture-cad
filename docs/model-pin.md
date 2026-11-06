# Harness model pin (bench winner 2026-07-19 post-harden suite)

Default Ollama model for the harness is **`qwen2.5:14b-instruct-q4_K_M`**
(100% on `benchmark/results/20260719T204337Z`, avg ~3.7s).

## Runtime lanes

| Lane | Default model | Behavior |
|------|---------------|----------|
| Accurate | `qwen2.5:14b-instruct-q4_K_M` | Default selection |
| Fast | `qwen2.5:7b-instruct-q8_0` | Manual low-latency selection |
| Auto | Resolves per request | Chat uses Fast; explain/tool uses Accurate |

Both CAD clients default to Accurate. Set `FIXTURE_OLLAMA_FAST_MODEL` to
change the Fast model without changing the API or client controls.

## PartDesign padded rectangle

The Accurate 14b lane planned the four-tool native PartDesign chain at
**100%** on the focused `partdesign-p1` case:

- Path A: `benchmark/results/20260721T141741Z`, 8.0/8.0, 4.78s
- Path B: FreeCAD 1.1.1 direct runners plus chat -> pending -> Apply,
  **13 pass / 0 fail**

The implementation uses FreeCAD 1.1's `AttachmentSupport` property and
`PartDesign::Pad.SideType`; it does not rely on numbered origin-plane names or
the deprecated Pad `Midplane` setter.

## PartDesign finite pocket

The Accurate 14b lane planned the full seven-call Body -> Pad -> second
origin-plane Sketch -> Pocket chain at **100%**:

- Path A: `benchmark/results/20260721T160957Z`, 8.0/8.0, 36.31s
- Path B: FreeCAD 1.1.1 direct runners plus chat -> pending -> Apply,
  **17 pass / 0 fail**

The bounded `pocket_sketch` tool supports positive finite lengths only. The
smoke cut a reversed 5 mm inner rectangle from a 40 x 20 x 10 mm pad and
verified the solid volume changed from 8000 to 7000 mm3. Through-all and
face-attached sketches remain deferred.

Override anytime:

```powershell
$env:FIXTURE_OLLAMA_MODEL = "qwen2.5:7b-instruct-q8_0"  # speed lane (~99%, ~3s)
# $env:FIXTURE_OLLAMA_MODEL = "gemma4:12b"              # also 100% on that suite
```

## Path A vs Path B

| Path | What |
|------|------|
| A Planner bench | Model → harness prompts → scored plans (`fixture_bench`) |
| B Mod exec | Harness plan → FreeCAD/Blender runners |

Harness postprocess (2026-07-19 harden): auto-injects `need_confirm` for confirm-tier tools; clearer W×H×D + cross-app refusal rules in the system prompt. Bench uses the same `finalize_plan` path.

## FreeCAD install smoke

```powershell
# Mod junction (done once):
# %APPDATA%\FreeCAD\v1-1\Mod\Fixture  ->  clients\freecad_workbench
# (earlier FreeCAD versions use %APPDATA%\FreeCAD\Mod\Fixture)

# Start harness
cd harness
$env:FIXTURE_OLLAMA_MODEL = "qwen2.5:14b-instruct-q4_K_M"
python -m uvicorn fixture_cad.main:app --host 127.0.0.1 --port 8766

# Headless smoke (no GUI)
& "C:\Program Files\FreeCAD 1.1\bin\freecadcmd.exe" `
  -c "exec(open(r'clients/freecad_workbench/smoke_freecad.py', encoding='utf-8').read())"

# GUI soak (manual): open FreeCAD → workbench Fixture → box / fillet / explain / fit + Apply/Cancel
```
