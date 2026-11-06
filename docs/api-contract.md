# API Contract — Fixture

Base URL: `http://127.0.0.1:8766`

Authoritative schemas: [`schemas/`](schemas/).

**Versioning:** the `version` field carries the **wire protocol** version,
currently `0.1.0`. The distributable package is **0.2.0**
(`fixture-cad`/`fixture_cad`, FreeCAD workbench, Blender addon, benchmark).
Read every `"version"` in this document as "wire protocol 0.1.0 / package
0.2.0". Bump the wire version only for a breaking request/response change; bump
the package version for releases.

## Endpoints

| Method | Path | Purpose |
|--------|------|---------|
| `GET` | `/health` | Liveness; reports model name if configured |
| `GET` | `/tools` | List tools available for `?app=freecad\|blender` |
| `POST` | `/chat` | Main chat + action planning |
| `POST` | `/tools/result` | Report tool failure/success for one repair attempt |

## Chat request

Schema: [`schemas/chat-request.json`](schemas/chat-request.json)

```json
{
  "app": "freecad",
  "version": "0.1.0",
  "context": {
    "active_document": "Unnamed",
    "workbench_or_mode": "PartDesign",
    "selected_objects": [
      {
        "name": "Pad001",
        "type": "PartDesign::Pad",
        "shape": "Solid",
        "properties": {"Length": 10}
      }
    ],
    "extra": {}
  },
  "history": [
    {"role": "user", "text": "make a hinge; start with anything you can"},
    {"role": "assistant", "text": "I can start with a rectangular base plate. Should I create that first?"}
  ],
  "message": "yes, make the base plate",
  "mode": "chat",
  "model_lane": "accurate"
}
```

| Field | Notes |
|-------|--------|
| `app` | `"freecad"` \| `"blender"` |
| `version` | Client protocol version (semver string) |
| `context` | App-specific snapshot; keep small (selection + light props) |
| `message` | Current user utterance or synthetic command text (max 2000 chars) |
| `history` | Optional prior user/assistant text turns (max 6). Exclude tool/meta/status/error lines. Each turn max 600 chars; clients should keep total history ≤ 2400 chars. |
| `mode` | `"chat"` \| `"explain"` \| `"tool"` |
| `model_lane` | Optional `"accurate"` \| `"fast"` \| `"auto"`; omitted defaults to `"accurate"` |

### Model lanes

| Requested lane | Resolved lane |
|----------------|---------------|
| `accurate` | Accurate model |
| `fast` | Fast model |
| `auto` + `mode: "chat"` | Fast model |
| `auto` + `mode: "explain"` or `"tool"` | Accurate model |

Clients may override Auto by sending `accurate` or `fast`. The harness returns
the resolved lane and model. A repair request should send that resolved lane so
the single repair attempt uses the same model.

Lane models are provider-aware refs configured with
`FIXTURE_ACCURATE_MODEL` / `FIXTURE_FAST_MODEL` (falling back to
`FIXTURE_OLLAMA_MODEL` / `FIXTURE_OLLAMA_FAST_MODEL`). A ref is either
`openrouter:<model>` or an Ollama tag (`ollama:` prefix optional), for example:

- `openrouter:anthropic/claude-sonnet-5.5` — opt-in cloud lane
- `qwen2.5:14b-instruct-q4_K_M` — local Ollama (default)

The default is fully local. The OpenRouter lane sends the prompt and CAD context
metadata to the cloud and requires `FIXTURE_OPENROUTER_API_KEY`; `/health`
reports `openrouter.configured`. When `FIXTURE_FALLBACK_MODELS` is set, the
harness retries that chain on provider failure and the response `model` field
names the model that answered.

### Context conventions

**FreeCAD:** `active_document`, `workbench_or_mode` (active workbench), `selected_objects[]` with FreeCAD type ids.

**Blender:** `active_document` = blend file name or `"untitled"`; `workbench_or_mode` = object mode (`OBJECT`/`EDIT`/…); selection = objects/meshes.

## Chat response

Schema: [`schemas/chat-response.json`](schemas/chat-response.json)

```json
{
  "reply_text": "I'll create a 40×40×10 mm box.",
  "actions": [
    {
      "type": "tool_call",
      "tool_name": "create_parametric_box",
      "args": {"width": 40, "height": 40, "depth": 10, "name": "Box"}
    },
    {
      "type": "meta",
      "kind": "ui_message",
      "text": "Confirm to create geometry."
    }
  ],
  "intent_status": "supported",
  "supported_scope": {
    "summary": "Create one 40×40×10 mm parametric box."
  },
  "model_lane": "accurate",
  "model": "qwen2.5:14b-instruct-q4_K_M",
  "request_id": "uuid-optional"
}
```

### Intent status (N1)

| `intent_status` | Meaning | Actions |
|-----------------|---------|---------|
| `supported` | Fully covered by current app tools | Normal tool_call + permission tiers |
| `ambiguous` | Need a clarifying choice before mutating | **No** `tool_call` |
| `partial` | Useful subset is supported; remainder is not | Tools allowed only with explicit scope + Apply/Cancel |
| `unsupported` | Nothing useful/safe to run for this ask | **No** `tool_call` |

`supported_scope` is required:

| Field | Notes |
|-------|--------|
| `summary` | What the assistant can/will do now (required) |
| `remainder` | Unsupported remainder of the original ask (required for `partial`; optional for `unsupported`) |
| `clarifying_question` | One concise clarifying question (required for `ambiguous`) |

Fail-closed policy (v1): if the model omits or corrupts `intent_status`, the harness sets `ambiguous`, strips tools, and asks for clarification. A future user-selectable `exploratory` policy may infer status from tools; it is not shipped in N1.

### Action types (v1)

| `type` | Fields | Behavior |
|--------|--------|----------|
| `tool_call` | `tool_name`, `args` | Client looks up runner; apply permission tier |
| `meta` | `kind`, `text` | UI-only (`ui_message`, `status`, `progress`, `need_confirm`) |

**Forbidden in v1:** `type: "python"`. Harness must strip/reject if the model emits it.

### Atomic PartDesign chain

Native PartDesign geometry uses linked tool calls rather than one opaque
operation. A rectangular pad calls `create_body`, `new_sketch`,
`sketch_rectangle`, then `pad_sketch`. The output name from each step is the
input name for the next step. All calls remain pending behind one Apply/Cancel
decision, and each runner owns its own FreeCAD undo transaction.

A finite pocket extends that chain with a second `new_sketch`,
`sketch_rectangle`, and `pocket_sketch` call. Origin-plane sketches resolve
their Body-local support by `OriginFeature.Role`. `pocket_sketch` accepts a
positive finite length and an explicit `reversed` direction; through-all and
face-attached profiles are outside this slice.

## Part multi-solid tools (N3)

FreeCAD confirm-tier tools `create_parametric_cylinder`, `transform_placement`,
`boolean_cut`, `boolean_fuse`, and `add_chamfer` mirror the box/fillet Part path.
Booleans create a new result object and leave base/tool in the document.
`transform_placement` sets absolute millimetres and Euler degrees; omitted axes
keep current placement values. These tools are FreeCAD-only.

## Reference attachments + 2D import/export (Slice B)

Local reference images and SVG outlines stay client-owned. The harness and
planner never receive absolute paths or image bytes.

### `context.extra.reference_image`

Bounded metadata only (schema-enforced):

| Field | Notes |
|-------|--------|
| `file_name` | Basename only; pattern rejects `/` and `\` |
| `media_type` | `image/png` \| `image/jpeg` \| `image/webp` \| `image/bmp` \| `image/svg+xml` |
| `byte_size` | Source file size, 1–8388608 (8 MB); bytes never sent |
| `width_px` / `height_px` | Optional raster dims, 1–16384 |

The client attaches this object after the user picks a local file. Until a
pinned local vision lane exists (Slice C), the planner must treat the payload
as metadata evidence only and must not claim to see image contents.

### Tools

| Tool | Tier | Notes |
|------|------|--------|
| `attach_reference_image` | `auto` | Opens the client file picker; never mutates the document |
| `import_svg_sketch` | `confirm` | No path arg; consumes the currently attached SVG at Apply; units mm; fail-closed on >64 paths or >512 edges |
| `export_stl` | `confirm` | Filename-only `path` (e.g. `remote.stl`); writes under `fixture_exports/`; optional `object_names` (default: all solids) |

FreeCAD-only this slice (Blender attach deferred). Import and export stay
confirm-tier with Apply/Cancel and undo transactions.

## Read-only inspection (N2)

FreeCAD catalog tools `list_document_objects` and `get_object` are `auto` tier
and must not mutate the document. Caps: list ≤40 objects; runner output and
`context.extra.inspection` payloads ≤2400 characters.

### Post-Apply verification

Clients own the verify loop after successful Apply:

1. Select tip objects → local `fit_view_selection` → local inspect runners.
2. Append a deterministic verify transcript (facts from runners, not model
   invention).
3. Optional second `POST /chat` with `mode: "explain"`, a synthetic verify
   message, and `context.extra.inspection` holding the same facts. The client
   shows `reply_text` but strips/ignores confirm-tier `tool_call` actions from
   that response.

Successful tool execution does **not** feed summarization through
`POST /tools/result` (success remains a stub). Failures still use `/tools/result`
for one repair attempt only.

## Tool result (repair)

Schema: [`schemas/tool-result.json`](schemas/tool-result.json)

```json
{
  "app": "freecad",
  "version": "0.1.0",
  "request_id": "uuid-optional",
  "tool_name": "create_parametric_box",
  "success": false,
  "model_lane": "accurate",
  "error": {
    "code": "tool_exec_failed",
    "message": "Part.makeBox failed",
    "detail": "traceback..."
  },
  "context": { },
  "attempt": 1
}
```

Harness may return a normal chat-response-shaped body with revised actions. Clients must set `attempt` and stop after **one** repair (attempt ≥ 2 → show error, no further POST).

## Error envelope

Schema: [`schemas/error.json`](schemas/error.json)

HTTP 4xx/5xx bodies:

```json
{
  "error": {
    "code": "validation_error",
    "message": "request failed schema validation",
    "detail": "..."
  }
}
```

| Code | When |
|------|------|
| `validation_error` | Bad request/response shape |
| `<provider>_unreachable` | Cannot reach the lane provider: `ollama_unreachable` or `openrouter_unreachable` (503) |
| `model_error` | Provider returned a model/API error (502) |
| `unsupported_action` | Model produced `python` or unknown tool |
| `repair_exhausted` | Client should stop retrying |

## Retry / repair strategy

1. Client executes `tool_call`.
2. On failure, stop the remaining actions from the original plan.
3. `POST /tools/result` with traceback + same context snapshot.
4. Harness prompts Ollama once with failure + allowed tools; repaired actions
   replace the stale remainder of the original plan.
5. If second execution fails, surface `error` in chat; do not loop.

## Fixtures

Examples under [`fixtures/`](fixtures/) must validate against schemas.
