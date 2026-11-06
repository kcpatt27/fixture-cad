# Fixture vs freecad-ai — head-to-head (2026-10-06)

Both systems driven by the **same 4 cloud models** on the **same 60-case
planner suite** (Fixture's case set, `benchmark/cases/`). Competitor pinned
at `ghbalf/freecad-ai` commit `5ef1e2d3dda4932de6064cda78758237dd1376c6`; it
is driven headlessly through its own client + prompt + 56-tool registry
(`benchmark/competitors/freecad_ai_planner.py`) — no FreeCAD needed, only its
planner turn is captured.

## Read this before the numbers (rubric asymmetry)

- **Fixture** number = share of cases where **every check** passes
  (parse, intent, exact args, confirm tier, reply/scope policy). It is
  single-response by construction — one planner turn, same `finalize_plan`
  postprocess as `/chat`.
- **freecad-ai** number = semantic case pass: only checks that transfer
  across the two tool catalogs count (a documented mapping in
  `competitors/freecad_ai_score.py`); non-equivalent tools are `n/a`, exact
  args and intent status are not compared, `execute_code` is recorded as a
  codegen-fallback signal, never as a hit.
- The suite is **Fixture's home contract test** — the competitor is
  measured on our turf, with the lenient rubric, so the gap below is
  conservative *against* Fixture's rubric-strictness, not inflated by it.

## The fair table — single-shot vs single-shot

freecad-ai given the same information as Fixture: one response must contain
the complete plan (their adapter appends: "respond with the COMPLETE sequence
of tool calls in this single response").

| model | Fixture (case pass, exact contract) | freecad-ai single-shot (case pass, semantic) | run (theirs) |
|---|---:|---:|---|
| `openrouter:deepseek/deepseek-v4.1-flash` | 59/60 = **98.3 %** | 37/58 = **63.8 %** | `20261006T215721Z` |
| `openrouter:deepseek/deepseek-v4-pro` | 59/60 = **98.3 %** | 34/59 = **57.6 %** | `20261006T221602Z` |
| `openrouter:z-ai/glm-5.3-flash` | 58/60 = **96.7 %** | 44/59 = **74.6 %** | `20261006T224128Z` |
| `openrouter:google/gemini-3.8-flash` | 59/60 = **98.3 %** | 40/58 = **69.0 %** | `20261006T225853Z` |

Fixture runs: `20261006T023121Z` (v4.1), `20261006T160826Z` (v4-pro),
`20261006T021353Z` (GLM), `20261006T160314Z` (Gemini) — from
`headtohead_leaderboard.md`.

Raw capture rows hold text + tool calls + latency, so any rescoring is a local
operation (no re-billing). One transient connection reset each for v4.1 and
Gemini (their client doesn't retry); those rows are excluded from serve stats,
not counted as model errors.

## Multi-turn architecture difference — measured separately

freecad-ai's **native mode is a multi-turn agent loop**: it plans turn 1,
expects tool results back, continues. We can't run its loop end-to-end here
(its tools drive its own FreeCAD client), so both captures are turn-1-only;
the only difference is the prompt:

| model | freecad-ai, default prompt (their native turn 1) | freecad-ai, forced single-shot | Δ |
|---|---:|---:|---:|
| v4.1-flash | 38/59 = 64.4 % | 37/58 = 63.8 % | −0.6 |
| v4-pro | 32/58 = 55.2 % | 34/59 = 57.6 % | +2.4 |
| GLM 5.3 | 35/59 = 59.3 % | 44/59 = 74.6 % | **+15.3** |
| Gemini 3.8 | 32/59 = 54.2 % | 40/58 = 69.0 % | **+14.8** |

Default-prompt run: `20261006T192542Z` (4 models × 60 cases, captured
2026-10-06 UTC). GLM and Gemini clearly follow the forced-instruction prompt
better; the DeepSeek pair is unaffected. The honest summary: **this measures
planner-turn quality, not the multi-turn product** — a full end-to-end
comparison needs their client executing their tools, out of scope here.

## Failure anatomy (single-shot, all 4 models)

16–26 failing cases per model; miss kinds aggregated over all failing cases:

| miss kind | count | reading |
|---|---:|---|
| required tool absent from the plan | 68 | tool-binding / coverage of their catalog vs required semantics |
| missing required reply substring | 18 | policy/reply behavior (briefs, refusals, explanations) |
| tools emitted when none expected | 15 | refusal/FAQ cases — they act when they should answer |
| no tool calls at all | 9 | empty/talk-only responses |
| forbidden tool present | 7 | boundary violations |

Cases failing on **all four** models are the tell: `fc-ideation-refuse-chair`,
`fc-offer-partial-scope`, `fc-ideation-partial-enclosure`,
`bl-ideation-route-mesh`, `fc-no-blender-tool`, `bl-explain-then-clean`,
`fc-hinge-mockup-multi`, `fc-import-svg-trace-box`. That is mostly the
**ideation/refusal policy surface** (a deliberate Fixture contract their
product doesn't implement) plus a couple of longer multi-tool chains — not
raw tool-picking ability. `execute_code` fallback usage: 1–11 cases per model
(GLM 11) — their adapter counts a codegen fallback, not a tool hit.

## Verdict

- On shared ground, Fixture's planner is **22–41 points ahead** at case
  level, with the stricter rubric. The failures cluster in policy surfaces
  Fixture designed for (honest partial/unsupported, cross-app routing,
  explain-with-tools) — this is a product-contract difference, not a model
  quality difference.
- freecad-ai remains the closest open competitor (see
  `docs/research/competitive-landscape-2026-10.md`); borrow-worthy patterns
  (headless isolation, dispatch health) are already tracked there.
- The comparison machinery is reusable: any future competitor adapter that
  exposes a turn-1 planner plugs into `headtohead_runner.py`.

## Artifacts

- Single-shot captures: `benchmark/results/20261006T215721Z/`,
  `20261006T221602Z/`, `20261006T224128Z/`, `20261006T225853Z/`
  (`freecad_ai.jsonl` + `freecad_ai_scored.jsonl` + `meta.json` each).
- Default-prompt capture: `benchmark/results/20261006T192542Z/`.
- Suite: `benchmark/cases/` (60 cases, 501 checks). Models list:
  `benchmark/headtohead-cloud.txt`. Runner: `competitors/headtohead_runner.py`
  (`--systems theirs --single-shot`). Scorer: `competitors/freecad_ai_score.py`.