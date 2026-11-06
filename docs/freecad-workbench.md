# FreeCAD AI Workbench Design

Target: FreeCAD **1.0+**, PySide6.

## Module layout

```
clients/freecad_workbench/
  package.xml                 # Addon Manager metadata (optional)
  Init.py                     # non-GUI import
  InitGui.py                  # register workbench
  fixture/
    __init__.py
    config.py                 # harness URL, timeouts, version
    client.py                 # HarnessClient (HTTP)
    context.py                # selection / document snapshot
    ai_chat_dock.py           # QDockWidget chat UI
    commands.py               # Fixture_OpenChat, ExplainSelection, …
    action_runner.py          # execute actions + confirm + repair
    tools/
      __init__.py             # registry of local runners
      explain_selection.py
      fit_view_selection.py
      create_parametric_box.py
      create_parametric_cylinder.py
      transform_placement.py
      boolean_cut.py
      boolean_fuse.py
      add_fillet.py
      add_chamfer.py
    resources/
      icons/
```

Install: copy/symlink `freecad_workbench` into the FreeCAD user `Mod` path so
`Init.py` / `InitGui.py` load. FreeCAD 1.1 uses
`%APPDATA%\FreeCAD\v1-1\Mod\`; earlier versions use `%APPDATA%\FreeCAD\Mod\`.
Check your FreeCAD version.

## Workbench

- `MenuText` / class name: **Fixture**
- Toolbar: `Fixture_OpenChat`, `Fixture_ExplainSelection`, `Fixture_FitView`
- On `Initialize`: register commands, append toolbar, create dock on main window (Right dock area)

## Chat dock

- Transcript (`QPlainTextEdit` read-only)
- Input (`QPlainTextEdit` or `QLineEdit`) + Send
- Model selector: Accurate, Fast, or Auto; defaults to Accurate
- Status label
- Apply/Cancel buttons for pending confirm-tier tools
- Native-theme grouping and spacing; no fixed light/dark palette
- Word-wrapped, bounded transcript and accessible control names/tooltips
- Pending actions appear in a dedicated confirmation group
- Bounded conversation `history` (user/assistant text only) is sent with each chat
- Intent status, supported scope, remainder, and clarifying question appear in
  the transcript; Send/Explain stay blocked while Apply/Cancel is pending

Workbench, toolbar, and Send icons are local monochrome SVGs under
`fixture/resources/icons/`. Command resource paths are resolved absolutely so
they work from a user Mod junction or copied installation.

**Send path:** gather message → `context.build()` → worker thread `HarnessClient.send_chat` → marshal result to GUI thread → render `reply_text` → `action_runner.run`.

Never block the GUI thread on HTTP.

## HarnessClient

```python
class HarnessClient:
    def __init__(self, base_url: str = "http://127.0.0.1:8766", timeout: float = 300.0): ...
    def health(self) -> dict: ...
    def send_chat(self, payload: dict) -> dict: ...
    def send_tool_result(self, payload: dict) -> dict: ...
```

Use `urllib` or `httpx` if available in FreeCAD’s Python; prefer stdlib `urllib.request` to avoid extra deps inside FreeCAD.

## Commands

| Command | Behavior |
|---------|----------|
| `Fixture_OpenChat` | Show/raise chat dock |
| `Fixture_ExplainSelection` | mode=`explain`, message fixed prompt |
| `Fixture_FitView` | Local tool or chat with fit intent |

## Tool runners (FreeCAD)

- `create_parametric_box` — `Part.makeBox` + addObject; transaction wrapped
- `create_parametric_cylinder` — `Part.makeCylinder` + `Part::Feature`
- `transform_placement` — absolute Base (mm) + Euler Rotation (degrees)
- `boolean_cut` / `boolean_fuse` — `Part::Cut` / `Part::Fuse`; new result; keep base/tool
- `add_fillet` — `Part.Fillet` / PartDesign fillet on selection (skeleton may use Part.Fillet)
- `add_chamfer` — `Part::Chamfer` on selection (bounded edges; optional makeChamfer fallback)
- `explain_selection` — return local summary string; often harness already wrote `reply_text` — runner can no-op or append facts
- `fit_view_selection` — `Gui.SendMsgToActiveView("ViewFit")` or selection fit
- `list_document_objects` — read-only name/type/label list (capped)
- `get_object` — read-only facts for one object by Name
- `create_body` — create native `PartDesign::Body`
- `new_sketch` — attach a Body-owned sketch to an XY/XZ/YZ origin plane
- `sketch_rectangle` — add one constrained rectangle to an empty sketch
- `pad_sketch` — create a native `PartDesign::Pad` from the sketch
- `pocket_sketch` — create a finite-length native `PartDesign::Pocket` from the sketch

Part multi-solid tools (box/cylinder/placement/boolean/fillet/chamfer) stay on
the Part workbench path and do not require a PartDesign Body. PartDesign calls
remain pending as one visible chain until Apply. A padded rectangle uses four
calls; adding an origin-plane rectangular Pocket uses seven. Cancel leaves the
document unchanged. Apply runs each confirm-tier tool in order; every tool has
its own undo transaction. Pocket through-all, face-attached sketches,
`hole_feature`, and assemblies remain deferred.

After a successful Apply, the dock selects tip objects, fits the view, runs
inspect tools, appends a deterministic verify block, then may send one grounded
`mode=explain` chat with `context.extra.inspection`. Confirm-tier tools from that
verify reply are never staged.

## Config

`config.py` defaults:

- `HARNESS_URL = "http://127.0.0.1:8766"`
- `CLIENT_VERSION = "0.1.0"` — this is the **wire protocol** version sent in
  the `version` field, not the package version. The package is `0.2.0`
  (`fixture.__version__`), so the pair is **wire protocol 0.1.0 / package
  0.2.0**.
- `PROTOCOL_APP = "freecad"`
