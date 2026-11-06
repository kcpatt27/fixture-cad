# Fixture Harness

Local FastAPI service that talks to Ollama (default) or OpenRouter (opt-in) and returns schema-validated `tool_call` / `meta` actions.

```powershell
cd harness
pip install -e .
# or: uv sync
$env:FIXTURE_OLLAMA_MODEL = "qwen2.5:14b-instruct-q4_K_M"
fixture
# → http://127.0.0.1:8766/health

# Opt-in cloud lane (prompts + CAD context leave the machine):
$env:FIXTURE_OPENROUTER_API_KEY = "sk-or-..."
$env:FIXTURE_ACCURATE_MODEL = "openrouter:anthropic/claude-sonnet-5.5"
$env:FIXTURE_FAST_MODEL = "openrouter:google/gemini-3.8-flash"
```

See `docs/harness.md` and `docs/api-contract.md` (model lanes).

## Running the harness tests

```powershell
uv run --project harness --with pytest pytest harness/tests -q
```

Runs the harness pytest suite (`harness/tests`) via `uv`, injecting `pytest`
into the harness project environment without adding it as a dependency.

## Building a release

```powershell
python harness/scripts/sync_contracts.py
uv build harness
uv publish harness/dist/*
```

`sync_contracts.py` copies the canonical `docs/tools` and `docs/schemas` into the
package so the sdist and wheel are self-contained. The generated
`harness/src/fixture_cad/data/` directory is gitignored.
