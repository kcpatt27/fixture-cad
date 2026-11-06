# PROJECT_CONTEXT

*Stable map: what Fixture is, where it lives, how to run it, and the words it
uses. This is **not** a live snapshot (status lives in `README.md` and
`ROADMAP.md`), **not** a design doc (`ARCHITECTURE.md`), and **not** a decision
log (`DECISIONS.md`).*

## 1. Origin

Fixture started as a local-first CAD harness: one FastAPI service that both
FreeCAD and Blender can call, with named tools, schema validation, and undo.
The public tree contains the harness, both clients, the benchmark suite, and
two finished design packages.

Phase A was deliberately docs-first: schemas were frozen before product code,
and code was built from those docs.

## 2. Environment discovered

| Tool | Version / path | Notes |
| --- | --- | --- |
| Python | 3.11 (scoop) | `pip install -e harness/`; tests can run with `PYTHONPATH=harness/src` |
| Ollama | `127.0.0.1:11434` | local models incl. `qwen2.5:14b/7b`, `qwen3.8:27b`, `gemma4:12b`, `ornith-1.5:9b`, `qwen3.5:4b` |
| FreeCAD | 1.1.1, `C:\Program Files\FreeCAD 1.1` | Mod junction `%APPDATA%\FreeCAD\v1-1\Mod\Fixture` → `clients/freecad_workbench` (FreeCAD 1.1 uses the versioned `v1-1` folder; earlier versions use `Mod\`) |
| Blender | 5.2 | addon installed from `clients/blender_addon/fixture_blender` |
| GPU | RTX 5060 Ti, 16 GB | local inference; 7B QLoRA class for future training work |
| Harness port | `127.0.0.1:8766` | default local port |
| OS | Windows 10/11 | Qt/PySide6 client quirks documented in `ARCHITECTURE.md` |

## 3. What was built

```
harness/src/fixture_cad/   FastAPI harness on :8766
  main.py            routes: /health /tools /chat /tools/result
  config.py          env settings: lanes, providers, fallbacks, rerank
  providers.py       model-ref parsing + provider dispatch + fallback chain
  ollama.py          Ollama /api/chat wrapper
  openrouter.py      opt-in OpenRouter wrapper (JSON mode + retry)
  chat.py            prompt build, sanitize, intent gate, finalize_plan
  model_lanes.py     accurate / fast / auto lane resolution
  validate.py        JSON Schema validation ingress/egress
  tools/registry.py  tool defs loaded from docs/tools/

clients/freecad_workbench/  chat dock, context, runners, undo, reference store, smokes
clients/blender_addon/      N-panel, operators, mesh runners, smokes
benchmark/                  Path A planner bench: cases/, fixture_bench/, models.txt
docs/                       contracts: schemas/, tools/, api-contract.md, research
designs/                    two scripted-CAD cases:
                            desk-mounts/laptop-cradle/, desk-mounts/underdesk-shelf/
                            (headless FreeCAD + STEP/STL exports + print specs)
```

## 4. How to run

```powershell
# Harness (terminal 1) — Ollama already running on :11434
cd harness
pip install -e .
python -m uvicorn fixture_cad.main:app --host 127.0.0.1 --port 8766

# Fast verification gate (terminal 2, harness running)
python harness/scripts/verify_fast.py          # fixtures + pytest + Path B smokes

# Planner benchmark (no CAD GUI needed)
cd benchmark
python -m fixture_bench run --models-file benchmark/models.txt
python -m fixture_bench report --latest

# Clients
#   FreeCAD: junction clients/freecad_workbench into the user Mod/ path
#            (1.1: %APPDATA%\FreeCAD\v1-1\Mod\; earlier: %APPDATA%\FreeCAD\Mod\)
#   Blender: install clients/blender_addon/fixture_blender as an addon
```

Optional cloud lane (see `DECISIONS.md` ADR-010):

```powershell
$env:FIXTURE_OPENROUTER_API_KEY = "sk-or-..."
$env:FIXTURE_ACCURATE_MODEL = "openrouter:deepseek/deepseek-v4.1-flash"
# default remains local Ollama
```

Key placement: either export env vars in the shell (above), persist with
`setx FIXTURE_OPENROUTER_API_KEY "..."` (new terminals), or copy
`.env.example` → `.env` at the repo root (gitignored; loaded at harness import,
real env vars win).

## 5. Conventions

- **Contract before code** — `docs/schemas/` and `docs/api-contract.md` change
  first; clients and harness follow the docs.
- **Named tools only** — the harness returns `tool_call` / `meta`; arbitrary
  `python` actions are stripped and never executed.
- **Thin clients** — FreeCAD/Blender gather context, confirm, execute locally,
  and report failures; the harness holds no CAD document state.
- **Local-first** — Ollama is the default provider; the OpenRouter lane is
  opt-in and never stores keys in the repo.
- **Evidence discipline** — benchmark runs are addressed by timestamp id
  (`benchmark/results/<UTC>/`), smokes by pass/fail counts, tests by counts.
  A pending number is never reported as a claimed number.
- **GPU discipline** - run `benchmark/check_gpu.ps1` before local-model
  benches, training, or GUI soaks; don't stack VRAM-heavy jobs. Cloud bench
  refs don't touch the GPU.
- **Naming** - the project name is `Fixture`; this is a solo project, and the
  public identity lives in `AUTHORS`/`NOTICE`/package metadata.

## 6. Non-goals for this stage

- Arbitrary Python execution from the model (rejected by design, see
  `DECISIONS.md` ADR-001).
- Cloud models by default; no API key is required to run the product.
- Forking FreeCAD or building an Onshape-clone UI.
- FEM, assemblies, TechDraw, DXF, Blender N3 — later ladder stages in
  `ROADMAP.md`, not current scope.

## Domain glossary

**harness** — the FastAPI service that validates requests, prompts a model, and
returns `tool_call` / `meta` actions. *Avoid*: "server", "backend".

**named tool** — a registered operation with a JSON args schema, permission
tier, and per-app availability (`docs/tools/*.json`). *Avoid*: "function".

**Path A** — planner benchmark: model output → same `finalize_plan` postprocess
as the harness → scored case. *Avoid*: "unit bench".

**Path B** — module-execution smoke: harness plan → real FreeCAD/Blender
runners, executed headlessly. *Avoid*: "integration test" (it is stronger).

**lane** — model selection: `accurate`, `fast`, or `auto` (chat → fast;
explain/tool → accurate).

**model ref** — provider-prefixed lane model string:
`openrouter:<model>` or an Ollama tag (`ollama:` optional).

**intent status** — planner classification: `supported`, `ambiguous`,
`partial`, `unsupported`; missing/invalid fails closed to `ambiguous`.

**permission tier** — `auto` (run immediately), `confirm` (Apply/Cancel +
undo), `deny` (reserved).

**N1 / N2 / N3** — shipped capability packs: capability-aware conversation,
guided post-Apply verification, modeling tools (cylinder/placement/booleans/
chamfer).

**Slice A / B / C** - ideation pack: concept-brief policy (A), attach/SVG
import/STL export (B), local vision (C, deferred).