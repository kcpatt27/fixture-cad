# Onboarding

Prerequisites and getting-started steps for Fixture.

## Prerequisites

- Python 3.11+ with pip
- Ollama installed and running on `:11434`
- FreeCAD 1.0+ (1.1 uses the versioned `v1-1` Mod path; check your version)
- Blender 5.2+
- Port `8766` free

`uvicorn`, `jsonschema`, and the other runtime libraries come with
`pip install -e harness`; no separate install is needed.

## Getting started

1. Clone the repository.

2. Create and activate a virtual environment:

   ```
   python -m venv .venv
   ```

   Activate it — PowerShell:

   ```
   .venv\Scripts\Activate.ps1
   ```

   Or macOS/Linux:

   ```
   source .venv/bin/activate
   ```

3. Install the harness in development mode (from the repo root):

   ```
   pip install -e harness
   ```

4. Start Ollama and pull models:

   ```
   ollama pull qwen2.5:14b-instruct-q4_K_M
   ollama pull qwen2.5:7b-instruct-q8_0
   ```

5. Start the harness (leave it running in its own terminal):

   ```
   python -m fixture_cad.main
   ```

   Or, equivalently:

   ```
   python -m uvicorn fixture_cad.main:app --host 127.0.0.1 --port 8766
   ```

6. Verify the harness is reachable:

   ```
   curl http://127.0.0.1:8766/health
   ```

7. Install client add-ons (FreeCAD workbench junction or Blender addon). For
   FreeCAD 1.1 the user Mod path is `%APPDATA%\FreeCAD\v1-1\Mod\`; earlier
   versions use `%APPDATA%\FreeCAD\Mod\`. See `docs/freecad-workbench.md` and
   `docs/blender-addon.md`.

## Environment variables

- `FIXTURE_OLLAMA_MODEL`
- `FIXTURE_OLLAMA_FAST_MODEL`
- `FIXTURE_PORT`

## Read before coding

1. `README.md` - what ships and how to run it
2. `docs/harness.md` - harness stack, config defaults, Python requirement
3. `ARCHITECTURE.md` - system design
4. `docs/api-contract.md` - request and response shapes
