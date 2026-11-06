# Fixture Blender addon

Install and enable from PowerShell:

```powershell
& "C:\Program Files\Blender Foundation\Blender 5.2\blender.exe" `
  --background --python clients/blender_addon/install_addon.py
```

The installer packages the current `fixture_blender` source, installs it in the Blender 5.2 user profile, enables it, and saves preferences.

Requires harness at `http://127.0.0.1:8766`.

See `docs/blender-addon.md`.
