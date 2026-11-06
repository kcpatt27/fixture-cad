# Fixture Model Benchmarks

Compare local **Ollama** and opt-in **OpenRouter** models on **harness planning quality** for FreeCAD and Blender tool catalogs.

This does **not** require FreeCAD or Blender GUI. It uses the same prompts and tool registry as the harness, then scores structured outputs.

## What it measures

| Check | Meaning |
|-------|---------|
| `parse_ok` | Model returned a JSON object with `reply_text` / `actions` |
| `no_python` | No `type: "python"` actions in raw output |
| `valid_actions` | Surviving actions are only `tool_call` / `meta` with valid shapes |
| `tool_hit` | Required tool(s) present after sanitize |
| `tool_miss` | Forbidden tools absent |
| `args_ok` | Expected argument constraints hold |
| `need_confirm` | Confirm-tier cases include `meta.kind=need_confirm` when required |
| `latency_s` | Wall time for the Ollama call |

## Layout

```
benchmark/
  cases/freecad/*.json
  cases/blender/*.json
  cases-extra/blender/*.json   # post-suite additions, not in the 60-case run
  fixture_bench/     # runner + scorer
  results/             # written by runs (gitignored samples ok)
  README.md
```

The default benchmark suite is the measured **60 cases** under
`cases/freecad` + `cases/blender`. `cases-extra/` keeps later additions
(for example the `clean_scan` case) out of that fixed-size run; the tool itself
is exercised by `clients/blender_addon/smoke_clean_scan.py`.

## Run

From the repo root (harness installed):

```powershell
pip install -e .\harness
$env:PYTHONPATH = "benchmark"

# One model, both apps
python -m fixture_bench run --models qwen2.5:7b-instruct-q8_0

# The project model list (edit benchmark/models.txt; one ref per line)
python -m fixture_bench run --models-file benchmark/models.txt

# Cloud models (opt-in): set FIXTURE_OPENROUTER_API_KEY first
python -m fixture_bench list-models --openrouter
python -m fixture_bench run --models openrouter:anthropic/claude-sonnet-5.5

# Tool reranking A/B (freecad-ai pattern): send only top-N keyword tools per case
python -m fixture_bench run --models-file benchmark/models.txt --tool-rerank 6

# Every chat model on disk (skips embed models like nomic-embed-text)
python -m fixture_bench run --all-models
# same thing:
python -m fixture_bench run --models all

# See what would be benched
python -m fixture_bench list-models

# Compare an explicit subset
python -m fixture_bench run --models qwen2.5:7b-instruct-q8_0,qwen3.5:4b,llama3.1:8b-instruct-q4_K_M

# Rebench only last-run winners (BEST / FASTEST / BEST-SMALLEST / BEST-FASTEST)
python -m fixture_bench run --winners --tag hard2
python -m fixture_bench run --winners --winners-from benchmark\results\20260720T193434Z

# FreeCAD only
python -m fixture_bench run --app freecad --all-models

# Harder suite only (multi-tool, strict args, cross-app refuse) — do not confuse with --tag harden
python -m fixture_bench run --tag hard --models qwen2.5:14b-instruct-q4_K_M
# hard2 pack (comma decimals, LWH, FAQ, refuse remesh, scientific notation, …)
python -m fixture_bench run --tag hard2 --all-models

# Single case across all disk models
python -m fixture_bench run --case fc-create-box-basic --all-models

# Print last summary (colored leaderboard with winner tags)
python -m fixture_bench report
python -m fixture_bench report --markdown   # also dump summary.md
python -m fixture_bench run ... --no-color  # plain output
```

Winner tags on the leaderboard:

| Tag | Meaning |
|-----|---------|
| `BEST` | Highest accuracy (then score, then speed) |
| `FASTEST` | Lowest avg latency (any accuracy) |
| `BEST-SMALL` | Fewest params among models with **>90%** accuracy |
| `BEST-FAST` | Lowest latency among models with **>90%** accuracy |

Runner-ups share the category color in a lighter (bright) tint with no badge.

Results land in `benchmark/results/<timestamp>/` as `results.jsonl` + `summary.md`.

**Case ideas backlog:** see [`CASE-BACKLOG.md`](CASE-BACKLOG.md) (harder Path A + future tools). Pull IDs from there when extending the suite.

## Competitor head-to-head (freecad-ai)

`competitors/headtohead_runner.py` captures Fixture vs the pinned
`ghbalf/freecad-ai` clone on the same suite (`--systems ours,theirs`;
`--single-shot` for planner parity). `competitors/freecad_ai_score.py` scores
their side semantically — only checks that transfer across the two tool
catalogs count, `n/a` tools are skipped. Latest result:
[`headtohead-vs-freecad-ai.md`](headtohead-vs-freecad-ai.md) — 2026-10-06,
4 cloud models: Fixture 96.7–98.3 % vs freecad-ai 57.6–74.6 % (single-shot
case pass, rubric asymmetry documented in the file).

To reproduce the competitor side, clone the pinned commit and point the adapter
at it:

```powershell
git clone https://github.com/ghbalf/freecad-ai "$env:TEMP\freecad-ai-audit"
git -C "$env:TEMP\freecad-ai-audit" checkout 5ef1e2d3dda4932de6064cda78758237dd1376c6
$env:FREECAD_AI_REPO = "$env:TEMP\freecad-ai-audit"
```

The adapter imports the competitor's planner only; FreeCAD is not required for
that half. Raw captures are not published, but the cases, scorer, and commit pin
are enough to re-run the comparison.

## Case format

```json
{
  "id": "fc-create-box-basic",
  "app": "freecad",
  "tags": ["tools", "create"],
  "message": "Create a 40x40x10mm box",
  "mode": "chat",
  "context": { "active_document": "Unnamed", "workbench_or_mode": "PartDesign", "selected_objects": [] },
  "expect": {
    "required_tools": ["create_parametric_box"],
    "forbidden_tools": ["clean_mesh"],
    "require_need_confirm": true,
    "arg_checks": [
      { "tool": "create_parametric_box", "arg": "width", "op": "eq", "value": 40 },
      { "tool": "create_parametric_box", "arg": "height", "op": "eq", "value": 40 },
      { "tool": "create_parametric_box", "arg": "depth", "op": "eq", "value": 10 }
    ]
  }
}
```

Optional N1 intent fields on `expect`:

| Field | Meaning |
|-------|---------|
| `intent_status` | String or list of allowed `supported` / `ambiguous` / `partial` / `unsupported` |
| `forbid_all_tools` | Sanitized plan must contain zero `tool_call` actions |
| `require_any_tool` | Sanitized plan must contain at least one `tool_call` |
| `required_reply_substr` | Case-insensitive substrings that must appear in `reply_text` |
| `required_scope_substr` | Case-insensitive substrings across `supported_scope` summary/remainder/clarifying_question |
| `history` (case root) | Prior `{role,text}` turns passed into the planner prompt |

Focused N1 pack: `--tags n1`.

## Adding cases

1. Drop a JSON file under `cases/freecad/` or `cases/blender/`.
2. Keep `id` unique and filename aligned (`fc-*.json` / `bl-*.json`).
3. Re-run; no code change needed unless you add new score ops.

## Limits (honest)

- **Local models touch the shared GPU.** Run `.\check_gpu.ps1` first; another
  session may be using it. Cloud (`openrouter:`) runs do not.
- Scores **planner** behavior (tool choice + args), not FreeCAD/Blender execution fidelity.
- Small models may fail `need_confirm` even when they pick the right tool.
- Latency depends on VRAM contention and whether the model is already loaded.
- Cloud runs send the full prompt (system + tool catalog + case context) to
  OpenRouter; set `FIXTURE_OPENROUTER_API_KEY` first.
- `--tool-rerank N` changes the prompt conditions; only compare runs that share
  the same setting. Both `tool_rerank_limit` and `models_file` are recorded in
  `meta.json`.
- The bench calls each model directly: harness fallback models
  (`FIXTURE_FALLBACK_MODELS`) are **not** applied, so scores stay honest.
