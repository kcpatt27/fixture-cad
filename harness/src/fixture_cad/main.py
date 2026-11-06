from __future__ import annotations

from typing import Any

import uvicorn
from fastapi import FastAPI, Query
from fastapi.responses import JSONResponse

from . import __version__, ollama, providers
from .chat import plan_chat, plan_repair
from .config import settings
from .model_lanes import resolve_model
from .tools.registry import ToolRegistry
from .validate import validate_or_raise

app = FastAPI(title="Fixture Harness", version=__version__)
registry = ToolRegistry.load()


def error_body(code: str, message: str, detail: str | None = None) -> dict[str, Any]:
    err: dict[str, Any] = {"code": code, "message": message}
    if detail:
        err["detail"] = detail
    return {"error": err}


@app.get("/health")
async def health() -> dict[str, Any]:
    ok_ollama = await ollama.ping()
    return {
        "ok": True,
        "version": __version__,
        "model": settings.accurate_model,
        "model_lanes": {
            "accurate": settings.accurate_model,
            "fast": settings.fast_model,
        },
        "ollama": ok_ollama,
        "openrouter": {
            "configured": bool(settings.openrouter_api_key),
            "url": settings.openrouter_url,
        },
        "fallbacks": providers.parse_fallback_models(settings.fallback_models),
        "tool_rerank_limit": settings.tool_rerank_limit,
    }


@app.get("/tools")
async def list_tools(app_name: str = Query(alias="app", default="freecad")) -> Any:
    if app_name not in {"freecad", "blender"}:
        return JSONResponse(
            status_code=400,
            content=error_body("validation_error", "bad app"),
        )
    tools = [t.raw for t in registry.for_app(app_name)]
    return {"app": app_name, "tools": tools}


@app.post("/chat")
async def chat_endpoint(payload: dict[str, Any]) -> JSONResponse:
    try:
        validate_or_raise(payload, "chat-request.json")
    except ValueError as exc:
        return JSONResponse(
            status_code=400,
            content=error_body("validation_error", "request failed schema validation", str(exc)),
        )

    try:
        selection = resolve_model(
            payload.get("model_lane"),
            mode=payload["mode"],
            settings=settings,
        )
        result = await plan_chat(
            app=payload["app"],
            message=payload["message"],
            context=payload.get("context") or {},
            mode=payload["mode"],
            registry=registry,
            model_lane=selection.lane,
            model=selection.model,
            fallback_models=providers.parse_fallback_models(settings.fallback_models),
            request_id=payload.get("request_id"),
            history=payload.get("history") or [],
        )
    except (ollama.OllamaError, providers.ProviderError) as exc:
        provider = getattr(exc, "provider", "ollama")
        code = f"{provider}_unreachable" if exc.unreachable else "model_error"
        status = 503 if exc.unreachable else 502
        return JSONResponse(status_code=status, content=error_body(code, str(exc)))

    try:
        validate_or_raise(result, "chat-response.json")
    except ValueError as exc:
        return JSONResponse(
            status_code=502,
            content=error_body("model_error", "response failed schema validation", str(exc)),
        )
    return JSONResponse(result)


@app.post("/tools/result")
async def tools_result(payload: dict[str, Any]) -> JSONResponse:
    try:
        validate_or_raise(payload, "tool-result.json")
    except ValueError as exc:
        return JSONResponse(
            status_code=400,
            content=error_body("validation_error", "request failed schema validation", str(exc)),
        )

    selection = resolve_model(
        payload.get("model_lane"),
        mode="tool",
        settings=settings,
    )
    if payload.get("success"):
        result: dict[str, Any] = {
            "reply_text": "Tool succeeded.",
            "actions": [],
            "intent_status": "supported",
            "supported_scope": {"summary": "Tool succeeded."},
            "model_lane": selection.lane,
            "model": selection.model,
        }
        if payload.get("request_id"):
            result["request_id"] = payload["request_id"]
        return JSONResponse(result)

    attempt = int(payload.get("attempt") or 1)
    if attempt >= 2:
        return JSONResponse(
            status_code=409,
            content=error_body(
                "repair_exhausted",
                "Repair attempts exhausted",
                (payload.get("error") or {}).get("message"),
            ),
        )

    try:
        result = await plan_repair(
            app=payload["app"],
            tool_name=payload["tool_name"],
            error=payload.get("error"),
            context=payload.get("context"),
            registry=registry,
            model_lane=selection.lane,
            model=selection.model,
            fallback_models=providers.parse_fallback_models(settings.fallback_models),
            request_id=payload.get("request_id"),
        )
    except (ollama.OllamaError, providers.ProviderError) as exc:
        provider = getattr(exc, "provider", "ollama")
        code = f"{provider}_unreachable" if exc.unreachable else "model_error"
        status = 503 if exc.unreachable else 502
        return JSONResponse(status_code=status, content=error_body(code, str(exc)))

    try:
        validate_or_raise(result, "chat-response.json")
    except ValueError as exc:
        return JSONResponse(
            status_code=502,
            content=error_body("model_error", "response failed schema validation", str(exc)),
        )
    return JSONResponse(result)


def run() -> None:
    uvicorn.run(
        "fixture_cad.main:app",
        host=settings.host,
        port=settings.port,
        reload=False,
    )


if __name__ == "__main__":
    run()
