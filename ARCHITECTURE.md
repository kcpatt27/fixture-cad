# ARCHITECTURE

*Design and as-built truth for Fixture. This is **not** the plan
(`ROADMAP.md`), **not** the API contract (`docs/api-contract.md` is authoritative
for wire shapes), and **not** a live status page (`README.md` carries dated
status). Every stub below is labelled where it sits.*

## The one invariant

**The harness proposes; clients mutate. Actions are `tool_call` / `meta` only —
no arbitrary `python` ever executes.**

Everything else is arranged around that sentence: schema validation at both
boundaries, named-tool execution in the CAD app, client-owned confirm and undo,
one bounded repair. If a change would let the model run code, it does not land.

## Planes

| Plane | Owns |
| --- | --- |
| **Control** (deterministic) | Schema validation, sanitize (drop `python`/unknown tools/bad args), permission tiers, intent gate, `need_confirm` injection, one-repair bound, localhost bind |
| **Execution** (model) | Token generation, tool selection and argument suggestions *inside* the allowed catalog only |

## Components

```
FreeCAD workbench            Blender addon
(dock, context, runners)     (N-panel, context, runners)
        │  HTTP REST (JSON)          │
        └──────────────┬─────────────┘
                       ▼
              Fixture harness :8766
              ├─ validate.py        ingress/egress JSON Schema
              ├─ tools/registry.py  named tools + args schemas + tiers
              ├─ chat.py            prompts, sanitize, intent gate, finalize_plan
              ├─ model_lanes.py     accurate / fast / auto
              └─ providers.py       model-ref dispatch + fallback chain
                       │
              ┌────────┴─────────┐
              ▼                  ▼
        Ollama :11434      OpenRouter (opt-in cloud)
```

The harness holds **no CAD document state**. Context is a compact snapshot the
client sends per request; mutations happen in the app process only.

## Request lifecycle (`POST /chat`)

1. Validate `chat-request.json` (schema is authoritative).
2. Resolve the lane → model ref (`accurate` default; `auto` routes by mode).
3. Build the system prompt: narrow rules, intent-status policy, tool catalog
   (optionally keyword-reranked to top-N), then the user prompt with bounded
   history.
4. Call the provider chain (first reachable model wins; the response names the
   model that answered).
5. Parse JSON (fences tolerated), normalize intent fields (fail closed to
   `ambiguous`), align known arg slips (W×H×D permutation, pad sketch name).
6. Sanitize actions (no `python`, known tools only, args validated).
7. Apply the intent gate: `ambiguous`/`unsupported` strip tools; `partial`
   requires remainder + forced confirm.
8. Ensure `need_confirm` for confirm-tier plans; validate
   `chat-response.json`; return.

Tool execution is client-side. On failure the client stops the stale remainder
and calls `POST /tools/result` once; the harness may return a revised plan. A
second failure surfaces honestly — no loop.

## Providers and lanes

- **Ollama** (default): `POST /api/chat`, `format:"json"`, `127.0.0.1:11434`.
- **OpenRouter** (opt-in): `POST /chat/completions` with bearer key and
  `response_format`; when a model rejects JSON mode (e.g. Ling 3.1) the client
  retries once without it, and the parser still tolerates plain/fenced output.
- **Fallback chain**: a lane may list `FIXTURE_FALLBACK_MODELS`; any provider
  failure advances down the chain. Benchmark runs bypass fallbacks on purpose.
- **Tool reranking**: opt-in `FIXTURE_TOOL_RERANK=N` prunes the catalog to the
  N best keyword matches; unknown wording returns the full catalog.

## Safety layers (deterministic, in order)

| Layer | Where | Effect |
| --- | --- | --- |
| JSON Schema | harness ingress/egress | malformed requests/responses never pass |
| Sanitize | `chat.finalize_plan` | strips `python`, unknown tools, invalid args |
| Intent gate | `chat.finalize_plan` | unsupported asks cannot stage mutations |
| Permission tier | client runners | clients enforce tier even if meta is missing |
| Apply/Cancel | both clients | confirm-tier plans stay pending until the user decides |
| Undo transactions | FreeCAD `openTransaction`; Blender operator undo (`bl_options={"UNDO"}`) | every mutating runner is undo-wrapped; aborts remove partial work |
| Repair bound | `/tools/result` | exactly one repair attempt (`attempt >= 2` stops) |

## Clients

**FreeCAD workbench** (`clients/freecad_workbench/`)

- Chat dock with Apply/Cancel; HTTP on a `QThread`.
- Worker results relay through a GUI-thread `QObject` with
  `Qt.QueuedConnection` — direct worker→widget callbacks crashed Qt text layout
  (fixed 2026-07-29, `smoke_chat_threading.py`).
- Context boundary converts `FreeCAD.Units.Quantity` to canonical floats
  (`json_safe_property`); native wrappers never reach `json.dumps`.
- PartDesign chains (Body → Sketch → Pad → Pocket) are named tools with
  explicit object names; FreeCAD 1.1 uses `AttachmentSupport` and resolves
  origin planes by `OriginFeature.Role`, never numbered names.
- SVG reference store keeps bytes client-side; only file metadata crosses the
  wire. `export_stl` writes under `fixture_exports/`.
- Post-Apply verify: select tip, fit view, run read-only inspection, append a
  deterministic transcript, optionally one grounded `mode=explain` reply.

**Blender addon** (`clients/blender_addon/`)

- N-panel chat with the same contract; `bpy` work marshalled to the main
  thread; undo push before mutations; mesh tools (`clean_mesh`, explain, fit).

## Benchmark design

| Path | What it proves |
| --- | --- |
| **A** (`benchmark/`) | Planner quality: tool choice, args, schema safety, confirm meta, refusals. 60 hand-written cases + future mined cases. Same postprocess as `/chat`. |
| **B** (`clients/.../smoke_*.py`) | Execution fidelity: plan → real runners under `freecadcmd` / Blender headless. |

`harness/scripts/verify_fast.py` runs fixtures + pytest + all Path B smokes and
writes logs under `artifacts/verify/<UTC>/`.

## As-built truth

| Area | State |
| --- | --- |
| Named-tool planning (FreeCAD 19, Blender 4) | **Built**, benchmarked to 100% on shipped packs (see `README.md` status) |
| Intent gate, repair bound, confirm/undo | **Built** |
| Model lanes + provider dispatch + fallbacks + rerank | **Built** 2026-10-04 (working tree) |
| OpenRouter cloud lane | **Built**; **no cloud benchmark run yet** — pending `FIXTURE_OPENROUTER_API_KEY` |
| Async jobs / long-op status | **Not built** — all tools are synchronous |
| Headless crash isolation for heavy geometry | **Not built** — borrowed pattern from `neka-nat/freecad-mcp`, see `docs/research/competitive-landscape-2026-10.md` |
| GUI dispatch health/timeouts | **Not built** (clients rely on thread marshalling; no stuck detector) |
| Local vision (Slice C) | **Not built** — reference images are metadata-only |
| FEM / assemblies / TechDraw / DXF | **Not built** — later ladder stages |
| MCP server exposure | **Not built** — candidate distribution seam |
| Mined Path A cases from CAD-1K | **Not built** — data plan in `docs/research/cad-blender-data-strategy-2026-10.md` |

## Seams (where change is expected)

- `providers.py` — one place to add providers; tool registry format is the one
  place to add tools.
- `docs/tools/*.json` — tool definitions are data, not code; clients mirror
  runners.
- `context.extra` — bounded extension point for client-side facts (reference
  metadata, inspection transcripts).
- **Stubs / deliberate non-controls**: `repair.py` is a thin route helper; the
  success branch of `/tools/result` is a stub that never summarizes; there is
  no server-side conversation store.