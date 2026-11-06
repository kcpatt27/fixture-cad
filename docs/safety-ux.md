# Safety and UX — Fixture

## tool_call vs python

| Approach | v1 |
|----------|----|
| `tool_call` | **Required** for all mutations and structured reads |
| `meta` | Status, progress, confirm prompts |
| `python` | **Forbidden** — stripped by harness; logged as `unsupported_action` |

Future (backlog): allow `python` only behind explicit user preference, sandbox, and confirm — not in v1.

## Permission tiers

| Tier | Examples | Client behavior |
|------|----------|-----------------|
| `auto` | `explain_selection`, `fit_view_selection`, `list_document_objects`, `get_object` | Run immediately |
| `confirm` | `create_parametric_box`, `create_parametric_cylinder`, `transform_placement`, `boolean_cut`, `boolean_fuse`, `add_fillet`, `add_chamfer`, `clean_mesh` | Show proposed args; Require OK before execute |
| `deny` | (reserved) | Never run; show error |

Harness may attach `meta.kind = "need_confirm"`; clients must still enforce tier from the registry even if meta is missing.

## Undo / redo

- **FreeCAD:** wrap mutating tools in `doc.openTransaction` / `commitTransaction` (abort on failure).
- **Blender:** mutating operators declare `bl_options = {"UNDO"}`, so Blender
  wraps the operator execution in its undo stack.
- Chat UI should mention “Undo available in the app” after successful confirms.

## Capability-aware conversation (N1)

The planner must classify every chat response:

| Status | UX |
|--------|----|
| `supported` | Show what will run; stage confirm-tier tools behind Apply/Cancel |
| `ambiguous` | Ask one clarifying question; do **not** stage tools |
| `partial` | Show supported scope + unsupported remainder; stage only the reduced plan behind Apply/Cancel |
| `unsupported` | Explain the limit honestly; do **not** invent tools or stage mutations |

Clients send a bounded `history` of recent user/assistant text turns so a short answer like “yes, make the base plate” retains the prior intent. History excludes tool/meta/status/error lines.

Strict fail-closed is the default: missing classification becomes `ambiguous` with tools stripped. A later optional exploratory policy may push ahead by inferring status; do not ship that toggle in N1.

While pending Apply/Cancel exists, both FreeCAD and Blender must block Send/Explain so a new reply cannot silently replace the pending plan.

## Guided verification after Apply (N2)

After a successful Apply of confirm-tier tools, clients:

1. Select tip object(s) created/touched by the batch.
2. Run `fit_view_selection` locally.
3. Run read-only inspect tools (FreeCAD: `list_document_objects` / `get_object`;
   Blender: selection/mesh facts) and append a **deterministic verify** block to
   the chat transcript immediately.
4. Optionally `POST /chat` with `mode: "explain"` and
   `context.extra.inspection` set to those facts so the model can narrate and
   offer one bounded next step. Clients must **not** stage confirm-tier tools
   from this verify reply (reply text only).

Success posts to `/tools/result` are not used for summarization.

## Preview before commit

For confirm-tier tools and partial-scope plans:

1. Show `reply_text` + humanized args / supported scope (e.g. “Box 40×40×10 mm”).
2. Buttons: **Apply** / **Cancel**.
3. Optional later: ghost preview geometry — not required in v1 skeleton.

## Status and progress

Use `meta` actions:

| `kind` | UI |
|--------|-----|
| `status` | Persistent status line (“Talking to harness…”) |
| `progress` | Indeterminate progress while waiting |
| `ui_message` | Inline transcript note |
| `need_confirm` | Trigger confirm dialog |

Client-local states (before/after HTTP):

- `idle` → `sending` → `awaiting_confirm` | `executing` → `idle` | `error`

## Failure UX

1. Show short error in transcript.
2. If `attempt == 1`, offer “Ask AI to repair” (calls `/tools/result`) or auto-repair once.
3. If repair fails, stop; do not spam Ollama.

## Network safety

- Clients only call configured harness base URL (default `http://127.0.0.1:8766`).
- Tool runners must not open network sockets or write outside the open document/blend file.
