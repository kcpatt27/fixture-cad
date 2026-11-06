# Harness Design

## Stack

- Python 3.11+
- FastAPI + uvicorn
- httpx → Ollama (default) or OpenRouter (opt-in cloud lane)
- jsonschema validation
- Tool JSON loaded from `docs/tools/` (path configurable)

## Package layout

```
harness/
  pyproject.toml
  src/fixture_cad/
    __init__.py
    main.py              # app + routes
    config.py            # host, port, model refs, provider keys, paths
    model_lanes.py       # lane resolution
    validate.py          # JSON Schema loading + validation
    providers.py         # model-ref parsing + provider dispatch
    ollama.py            # Ollama /api/chat wrapper
    openrouter.py        # OpenRouter /chat/completions wrapper
    chat.py              # prompt build + parse
    tools/
      registry.py
```

## Config

| Env / setting | Default |
|---------------|---------|
| `FIXTURE_HOST` | `127.0.0.1` |
| `FIXTURE_PORT` | `8766` |
| `FIXTURE_DEBUG_LOG` | unset (raw model logging off) |
| `FIXTURE_OLLAMA_URL` | `http://127.0.0.1:11434` |
| `FIXTURE_OLLAMA_MODEL` | Accurate lane fallback: `qwen2.5:14b-instruct-q4_K_M` |
| `FIXTURE_OLLAMA_FAST_MODEL` | Fast lane fallback: `qwen2.5:7b-instruct-q8_0` |
| `FIXTURE_ACCURATE_MODEL` | Accurate lane ref; defaults to `FIXTURE_OLLAMA_MODEL` |
| `FIXTURE_FAST_MODEL` | Fast lane ref; defaults to `FIXTURE_OLLAMA_FAST_MODEL` |
| `FIXTURE_OPENROUTER_API_KEY` | empty (OpenRouter lane disabled) |
| `FIXTURE_OPENROUTER_URL` | `https://openrouter.ai/api/v1` |
| `FIXTURE_OPENROUTER_REFERER` | empty (optional `HTTP-Referer` header) |
| `FIXTURE_OPENROUTER_TITLE` | `Fixture` (`X-Title` header) |
| `FIXTURE_FALLBACK_MODELS` | empty; comma-separated refs tried in order when the lane model fails |
| `FIXTURE_TOOL_RERANK` | `0` (off); `N>0` sends only the top-N keyword-matched tools per request |
| `FIXTURE_TOOLS_DIR` | repo `docs/tools` |
| `FIXTURE_SCHEMAS_DIR` | repo `docs/schemas` |

A gitignored `.env` at the repo root is loaded when the harness imports
(`config.load_env_file`); real environment variables win. Copy `.env.example` to
`.env` to hold `FIXTURE_OPENROUTER_API_KEY` and optional knobs.

Lane model refs select a provider by prefix: `openrouter:anthropic/claude-sonnet-5.5`
routes to OpenRouter, `ollama:qwen2.5:14b` or a bare `qwen2.5:14b` routes to
Ollama. The default remains fully local; the OpenRouter lane is opt-in and sends
the prompt plus CAD context (selection/properties metadata) to the cloud.

Requests may select `accurate`, `fast`, or `auto`. Omitted selections use
Accurate. Auto routes normal chat to Fast and explain/tool requests to Accurate.

## Routes

### `GET /health`

```json
{
  "ok": true,
  "model": "qwen2.5:14b-instruct-q4_K_M",
  "model_lanes": {
    "accurate": "qwen2.5:14b-instruct-q4_K_M",
    "fast": "qwen2.5:7b-instruct-q8_0"
  },
  "ollama": true,
  "openrouter": {
    "configured": false,
    "url": "https://openrouter.ai/api/v1"
  }
}
```

### `GET /tools?app=freecad`

Filtered tool list for prompting/clients.

### `POST /chat`

1. Validate request schema  
2. Build system prompt: role, rules (no python), tool catalog for `app`, intent-status rules  
3. Build user prompt: mode + optional bounded `history` + current `message` + context  
4. Call the lane's model provider (Ollama or OpenRouter)  
5. Parse JSON object from model (`reply_text`, `actions`, `intent_status`, `supported_scope`) — tolerate fenced ```json  
6. Normalize intent fields; fail closed to `ambiguous` when missing/invalid  
7. Filter actions: drop `python`; drop unknown tools; validate args against tool `args_schema`  
8. Enforce intent gate: strip tools for `ambiguous`/`unsupported`; require scope+confirm for `partial`  
9. Inject `need_confirm` for remaining confirm-tier or partial plans  
10. Validate response schema  
11. Return  

### `POST /tools/result`

1. Validate tool-result schema  
2. If `success` or `attempt >= 2` → return advice-only response / error  
3. Else repair prompt with error detail + tools → same parse pipeline once  

## Prompt shape (sketch)

System:

- You are Fixture planner for `{app}`.
- Reply with a single JSON object: `reply_text`, `actions`.
- Actions may be `tool_call` or `meta` only.
- Never emit Python code actions.
- Only use these tools: … (JSON schemas)

User:

- `message` + compact `context` JSON.

## Parsing robustness

- Strip markdown fences
- If parse fails → `meta` status + empty actions + apologetic `reply_text`, HTTP 200 (soft fail) or 502 `model_error` — prefer soft fail with message so UI stays usable
- Opt-in: set `FIXTURE_DEBUG_LOG=1` to log request id, model, and raw model text to stderr.

## Model providers

**Ollama (default, local):** `POST {OLLAMA_URL}/api/chat` with `stream: false`,
`format: "json"` when model supports it.

**OpenRouter (opt-in):** `POST {OPENROUTER_URL}/chat/completions` with
`Authorization: Bearer <key>` and `response_format: {"type":"json_object"}`.
Requires `FIXTURE_OPENROUTER_API_KEY`. Transport failures map to
`openrouter_unreachable` (503); HTTP/API errors map to `model_error` (502).
Both providers share the same parse/sanitize/intent-gate pipeline, so adding
cloud quality tests does not change the client contract.

### Fallback models (freecad-ai pattern)

`FIXTURE_FALLBACK_MODELS=openrouter:openai/gpt-6-luna,ollama:qwen2.5:7b-instruct-q8_0`
tries the lane model first, then each fallback, on any provider failure
(unreachable, auth, rate limit, missing model). The response reports the model
that actually answered. The benchmark calls models directly and does **not**
apply fallbacks, so scored runs stay honest.

### Tool reranking (freecad-ai pattern)

`FIXTURE_TOOL_RERANK=6` sends only the 6 best keyword matches for the current
message instead of the full catalog (freecad-ai does this to save prompt tokens
and steady small models). Name-token hits weigh 3x; unknown wording returns the
full catalog. Measure with `fixture_bench run --tool-rerank N` before enabling
it by default.

## Security

- Bind `127.0.0.1` only
- No auth in v1 (localhost trust)
- Do not execute tools on the server
- Local-first default: the OpenRouter lane is enabled only when a lane model ref
  uses the `openrouter:` prefix and an API key is set; then prompts and CAD
  context metadata leave the machine
