# DECISIONS

*Append-only ADR log. Newest last. Supersede by adding a new ADR that references
the old one — never edit history. A new runtime dependency requires an admitting
ADR. This is **not** meeting notes and **not** the plan (`ROADMAP.md`).*

## ADR-001: Named tools only — arbitrary Python is rejected by design

- **Status:** accepted (2026-07-19)
- **Deciders:** Kalen
- **Related:** `docs/safety-ux.md`, ADR-002, ADR-006; invariant in `ARCHITECTURE.md`

### Context

LLM-generated FreeCAD/Blender Python is brittle, unauditable, and can destroy
undo history. The founding brief called for AI-hackable CAD without pasting
unsafe code into the console.

### Decision

The harness emits `tool_call` / `meta` actions only. `python` actions are
stripped; tools are registered with args schemas and permission tiers.

### Alternatives

- Arbitrary codegen with sandboxing — rejected: no reliable FreeCAD/Blender
  sandbox; audit surface unbounded.
- Codegen behind a "danger mode" toggle — rejected for v1: splits the safety
  story and invites drift.

### Consequences

Safer, deterministic, repairable plans; requires building tools for each
capability instead of getting them free from codegen. Residual risk: a model
can still choose the wrong *tool*; the intent gate and confirm UX bound it.

---

## ADR-002: One shared harness, thin clients, client-owned mutation

- **Status:** accepted (2026-07-19)
- **Deciders:** Kalen
- **Related:** `ARCHITECTURE.md`, `docs/api-contract.md`

### Context

FreeCAD and Blender each need an AI surface; duplicating model glue in both
apps guarantees drift.

### Decision

One FastAPI harness owns prompting/validation; clients send context and execute
registered tools locally. The harness never holds a CAD document.

### Alternatives

- Per-app AI integration — rejected: two contract implementations.
- Harness-side execution — rejected: no document access, and it would make the
  harness privileged.

### Consequences

One contract to evolve; clients stay thin but must implement every runner.
Client bugs are the primary execution risk; Path B smokes cover them.

---

## ADR-003: Local-first — Ollama on localhost, no cloud key required

- **Status:** accepted (2026-07-19); cloud non-goal amended by ADR-010
- **Deciders:** Kalen
- **Related:** ADR-010, `docs/harness.md`

### Context

Personal CAD work is private and should not depend on paid APIs. The machine
already runs Ollama for the sibling a separate local agent stack stack.

### Decision

Default and required-for-product operation is local Ollama on `127.0.0.1:11434`;
harness binds `127.0.0.1:8766` only.

### Alternatives

- Cloud models as the default — rejected: cost, privacy, availability.
- No cloud support at all — amended in ADR-010 when quality comparison became
  desirable.

### Consequences

Offline-capable, zero-cost planning; quality ceiling is the local model. The
cloud lane exists only as an explicit opt-in (ADR-010).

---

## ADR-004: JSON Schema is the wire contract

- **Status:** accepted (2026-07-19)
- **Deciders:** Kalen
- **Related:** `docs/schemas/`, `docs/api-contract.md`

### Context

Two independent clients (FreeCAD, Blender) plus a harness and a benchmark all
consume the same shapes. Prose docs drift; schemas can be validated in CI and
tests.

### Decision

`docs/schemas/` is authoritative for requests/responses; the harness validates
ingress and egress; fixtures must validate against the schemas.

### Alternatives

- Pydantic-first models shared as code — rejected: clients are Python but the
  contract should stay language-neutral and readable.
- Prose-only contracts — rejected: drift found during bench/smoke work.

### Consequences

Changing behavior means changing the schema first. Schema edits ripple to
fixtures, docs, and tests in the same change.

---

## ADR-005: Confirm UX is inline Apply/Cancel with per-runner undo

- **Status:** accepted (2026-07-19)
- **Deciders:** Kalen
- **Related:** `docs/safety-ux.md`, ADR-001

### Context

Confirm-tier mutations need user consent that stays inside the chat flow; modal
popups interrupt and are easy to mis-click.

### Decision

Confirm-tier actions stay pending in the dock/N-panel until **Apply** or
**Cancel**; each mutating runner is undo-wrapped (FreeCAD transaction, Blender
`undo_push`); clients enforce the tier even if `need_confirm` meta is missing.

### Alternatives

- Immediate execution with "undo available" — rejected: beginners should not
  discover mistakes after the fact.
- Modal confirmation dialog — rejected: breaks chat flow, worse for keyboard
  use.

### Consequences

Safe default for beginners; plan staging must block a second Send while pending
(both clients implement this).

---

## ADR-006: Fail-closed intent gate — missing classification becomes `ambiguous`

- **Status:** accepted (2026-07-21)
- **Deciders:** Kalen
- **Related:** ADR-001, `docs/safety-ux.md`, roadmap N1

### Context

Models sometimes omit or corrupt `intent_status`; silently proceeding could
stage part of an impossible request and imply full support.

### Decision

`supported` / `ambiguous` / `partial` / `unsupported` are mandatory; missing or
invalid → `ambiguous` with tools stripped. `unsupported`/`ambiguous` strip all
tool calls. `partial` requires a remainder and forced confirm.

### Alternatives

- Infer status from emitted tools — rejected for v1: circular and
  over-permissive.
- Trust the model's classification — rejected: observed omissions.

### Consequences

Honest refusals and clarifications; more clarification turns. An explicit
exploratory policy remains deferred, not shipped (see `ROADMAP.md`).

---

## ADR-007: Exactly one bounded repair attempt

- **Status:** accepted (2026-07-21)
- **Deciders:** Kalen
- **Related:** `docs/api-contract.md`, ADR-002

### Context

Tool failures need a chance to recover, but retry loops burn tokens and can
thrash a document.

### Decision

Clients stop the stale action remainder on failure and `POST /tools/result`
once. The harness may return one replacement plan; `attempt >= 2` stops.

### Alternatives

- Automatic N retries — rejected: unbounded cost and mutation risk.
- No repair — rejected: single arg slips are the most common failure and cheap
  to fix.

### Consequences

Bounded recovery; second failures surface honestly to the user.

---

## ADR-008: PartDesign chains are explicit named tools with FreeCAD 1.1 semantics

- **Status:** accepted (2026-07-22)
- **Deciders:** Kalen
- **Related:** `ARCHITECTURE.md`

### Context

Body → Sketch → Pad → Pocket must remain an editable native feature tree, and
FreeCAD 1.1 changed several APIs (Sketcher `AttachmentSupport`, Pad `SideType`,
origin-plane identity).

### Decision

Compose native features from explicit named tools with shared names
(`create_body` → `new_sketch` → `sketch_rectangle` → `pad_sketch`). Resolve
origin planes by `OriginFeature.Role`, use `SideType` (never legacy `Midplane`),
and verify a finite pocket leaves one solid with lower volume.

### Alternatives

- One opaque `make_plate` macro — rejected: not editable, hard to repair.
- Part primitives instead of PartDesign — rejected: north star is an editable
  feature tree.

### Consequences

Editable results and repairable steps; more planner steps per model, which the
benchmark covers (100% on the shipped packs).

---

## ADR-009: Reference images are metadata-only; bytes and paths stay client-side

- **Status:** accepted (2026-07-28)
- **Deciders:** Kalen
- **Related:** `docs/api-contract.md` Slice B; roadmap Slice C deferred

### Context

Attachments are useful for intent, but shipping paths/bytes to the harness
leaks filesystem layout and implies vision that does not exist yet.

### Decision

`context.extra.reference_image` carries basename + media type + byte size (+
optional raster dims) only. SVG import and STL export run client-side;
`export_stl` writes under `fixture_exports/`. Planner must fail closed: a
raster attachment never yields `import_svg_sketch`.

### Alternatives

- Send bytes for a future VLM — rejected until a pinned local vision lane
  exists (Slice C).
- Absolute paths — rejected: privacy and confusion.

### Consequences

Honest metadata-only behavior today; vision remains a separately opened slice.
Known weak point: the planner can still overclaim SVG import for a raster
attachment — the runner strips it, and a deterministic guard is on the roadmap.

---

## ADR-010: Opt-in OpenRouter lane; the default stays local

- **Status:** accepted (2026-10-04)
- **Deciders:** Kalen
- **Related:** ADR-003, `docs/harness.md`, `docs/api-contract.md`

### Context

Quality comparison against cloud models became desirable (credits available);
the product must not silently depend on them.

### Decision

Lane refs may be `openrouter:<model>`; `FIXTURE_OPENROUTER_API_KEY` enables
the lane. Defaults remain Ollama. Cloud prompts send system prompt + tool
catalog + bounded CAD context metadata; no document bytes/paths.

### Alternatives

- A third lane (`cloud`) — rejected: forces clients/UI to know providers.
- Provider-per-request field — rejected for v1: repair semantics and schema
  churn.

### Consequences

Same contract, same postprocess for both providers; users must know that
cloud runs send context off-machine. Error codes are `<provider>_unreachable`.

---

## ADR-011: Fallback chains and tool reranking are opt-in and measured

- **Status:** accepted (2026-10-04)
- **Deciders:** Kalen
- **Related:** ADR-010, `benchmark/README.md`

### Context

Patterns borrowed from `ghbalf/freecad-ai`: provider fallback profiles and
keyword tool reranking. Both change behavior; neither is proven on this
project's suite.

### Decision

Implement both behind env config (`FIXTURE_FALLBACK_MODELS`,
`FIXTURE_TOOL_RERANK`), off by default. The bench exposes `--tool-rerank N`
and records it in `meta.json`; fallbacks are **not** applied in bench runs so
scores stay exact-model.

### Alternatives

- On by default — rejected: unmeasured behavior change.
- Skip both — rejected: resilience and small-model prompt savings are useful.

### Consequences

Users opt into behavior changes; the suite decides whether reranking becomes a
default (drop it if the A/B shows no gain).

---

## ADR-012: Foundation docs live at the repo root; `docs/` stays the contract layer

- **Status:** accepted (2026-10-04)
- **Deciders:** Kalen
- **Related:** this file, `README.md`, `PROJECT_CONTEXT.md`

### Context

Fixture predated the house foundation-doc set. Roadmap/architecture lived in
`docs/` mixed with wire contracts; there was no project map or decision log.

### Decision

Adopt the root doc set (`README`, `ROADMAP`, `ARCHITECTURE`,
`PROJECT_CONTEXT`, `DECISIONS`). `docs/roadmap.md` and `docs/architecture.md`
become pointers; `docs/` keeps what is genuinely contract/design-detail:
schemas, tool defs, api-contract, research, safety-ux.

### Alternatives

- Add only the missing docs - rejected: two homes for the plan invites drift.
- Leave everything in `docs/` - rejected: the reading order deserves the root.

### Consequences

One canonical home per fact. Inbound references were updated in the same
change.