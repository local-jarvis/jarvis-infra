from __future__ import annotations

import asyncio
import time
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import Depends, FastAPI, Header, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from .config import settings
from .llm import LlamaModelManager, ModelUnavailableError
from .schemas import ChatCompletionRequest


model_manager = LlamaModelManager(settings)


@asynccontextmanager
async def lifespan(app: FastAPI):
    if settings.preload_model:
        await asyncio.to_thread(model_manager.load)
    yield


app = FastAPI(title=settings.app_name, lifespan=lifespan)

if settings.cors_origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(settings.cors_origins),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )


async def require_api_key(
    authorization: Optional[str] = Header(default=None),
    x_api_key: Optional[str] = Header(default=None),
) -> None:
    if not settings.api_key:
        return

    bearer_prefix = "Bearer "
    bearer_token = (
        authorization[len(bearer_prefix) :]
        if authorization and authorization.startswith(bearer_prefix)
        else None
    )

    if x_api_key != settings.api_key and bearer_token != settings.api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API key.",
        )


@app.get("/healthz")
async def healthz():
    return {"status": "ok"}


@app.get("/readyz")
async def readyz():
    exists = model_manager.model_path.exists()
    return {
        "status": "ready" if exists else "not_ready",
        "model_path": str(model_manager.model_path),
        "model_path_exists": exists,
        "model_loaded": model_manager.is_loaded,
    }


@app.get("/v1/models", dependencies=[Depends(require_api_key)])
async def list_models():
    return {
        "object": "list",
        "data": [
            {
                "id": settings.served_model_name,
                "object": "model",
                "created": 0,
                "owned_by": "local",
            }
        ],
    }


@app.post("/v1/chat/completions", dependencies=[Depends(require_api_key)])
async def create_chat_completion(request: ChatCompletionRequest):
    payload = request.llama_kwargs(
        default_max_tokens=settings.default_max_tokens,
        default_temperature=settings.default_temperature,
        default_top_p=settings.default_top_p,
    )
    payload["model"] = request.model or settings.served_model_name

    if request.stream:
        try:
            await asyncio.to_thread(model_manager.load)
            return StreamingResponse(
                model_manager.stream_chat_completion(payload),
                media_type="text/event-stream",
            )
        except ModelUnavailableError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc

    try:
        result = await asyncio.to_thread(model_manager.create_chat_completion, payload)
    except ModelUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    if isinstance(result, dict):
        result.setdefault("id", f"chatcmpl-{int(time.time() * 1000)}")
        result.setdefault("object", "chat.completion")
        result.setdefault("created", int(time.time()))
        result.setdefault("model", settings.served_model_name)

    return result
