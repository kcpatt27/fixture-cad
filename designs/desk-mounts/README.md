# Desk mounts - two scripted-CAD designs

Two separate under-desk designs, one shared FreeCAD generator:

| Mount | What it is | Public artefacts |
|---|---|---|
| [`laptop-cradle/`](laptop-cradle/) | Slide-in laptop cradle: two rails + two-piece back stop (4 printed pieces) | STEP/STL, renders, print spec |
| [`underdesk-shelf/`](underdesk-shelf/) | Two-piece under-desk shelf with cable/vent openings and a magnetic front lip | STEP/STL, renders, print spec |

Both are generated from `desk_mounts.py` - the parameters live at the top of
that file. `stl_render.py` renders the previews from the exported binary STLs
(stdlib only), so the assembly can be checked without opening CAD.

```powershell
# Rebuild both mounts (FreeCAD headless)
& "C:\Program Files\FreeCAD 1.1\bin\python.exe" designs\desk-mounts\desk_mounts.py

# Re-render the previews
python designs\desk-mounts\stl_render.py
```

Each mount writes `export/<piece>.step`, `export/<piece>.stl`,
`export/manifest.json`, and `export/render_*.png`. All pieces export as single
valid solids; the manifest records volume and bounding box per piece.

The 3D-printed handheld keyboard is a separate private design. Its CAD source,
exports, and renders are not published in this repository and it does not
appear in the product reel.
