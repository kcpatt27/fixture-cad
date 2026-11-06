# Fixture FreeCAD workbench

Copy or symlink this folder into FreeCAD's user `Mod` directory. FreeCAD 1.1
uses `%APPDATA%\FreeCAD\v1-1\Mod\`; earlier versions use
`%APPDATA%\FreeCAD\Mod\`. Check your FreeCAD version first.

```powershell
# FreeCAD 1.1 (use "$env:APPDATA\FreeCAD\Mod\Fixture" on earlier versions)
New-Item -ItemType Junction -Path "$env:APPDATA\FreeCAD\v1-1\Mod\Fixture" -Target (Resolve-Path .)
```

Then restart FreeCAD and switch to the **Fixture** workbench.

Requires harness at `http://127.0.0.1:8766`.

See `docs/freecad-workbench.md`.
