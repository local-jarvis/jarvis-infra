from __future__ import annotations

import asyncio
import json
import logging
import time
from contextlib import asynccontextmanager
from typing import Any, Dict, Iterator, Optional
from uuid import uuid4

from fastapi import Depends, FastAPI, Header, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from .config import settings
from .llm import LlamaModelManager, ModelUnavailableError
from .schemas import ChatCompletionRequest


model_manager = LlamaModelManager(settings)
chat_logger = logging.getLogger("uvicorn.error")


def _log_json(event: str, **fields: Any) -> None:
    chat_logger.info(
        "chat_log %s",
        json.dumps({"event": event, **fields}, ensure_ascii=False, default=str),
    )


def _collect_stream_chunk(
    event: str,
    *,
    content_parts: list[str],
    metadata: Dict[str, Any],
) -> None:
    data = event.strip()
    if not data.startswith("data: "):
        return

    payload = data[len("data: ") :].strip()
    if payload == "[DONE]":
        metadata["done"] = True
        return

    try:
        chunk = json.loads(payload)
    except json.JSONDecodeError:
        metadata["unparsed_chunks"] = metadata.get("unparsed_chunks", 0) + 1
        return

    metadata["chunk_count"] = metadata.get("chunk_count", 0) + 1
    metadata.setdefault("id", chunk.get("id"))
    metadata.setdefault("model", chunk.get("model"))

    choices = chunk.get("choices") or []
    if not isinstance(choices, list):
        return

    for choice in choices:
        if not isinstance(choice, dict):
            continue

        delta = choice.get("delta")
        if isinstance(delta, dict):
            content = delta.get("content")
            if isinstance(content, str):
                content_parts.append(content)

        finish_reason = choice.get("finish_reason")
        if finish_reason is not None:
            metadata.setdefault("finish_reasons", []).append(finish_reason)


def _logged_stream(
    events: Iterator[str],
    *,
    request_id: str,
    request_payload: Dict[str, Any],
    started_at: float,
) -> Iterator[str]:
    content_parts: list[str] = []
    metadata: Dict[str, Any] = {}

    try:
        for event in events:
            _collect_stream_chunk(
                event,
                content_parts=content_parts,
                metadata=metadata,
            )
            yield event
    except Exception as exc:
        _log_json(
            "chat_completion_error",
            request_id=request_id,
            request_payload=request_payload,
            elapsed_ms=round((time.perf_counter() - started_at) * 1000, 2),
            error=str(exc),
        )
        raise
    else:
        _log_json(
            "chat_completion_response",
            request_id=request_id,
            request_payload=request_payload,
            response_payload={
                "stream": True,
                "content": "".join(content_parts),
                **metadata,
            },
            elapsed_ms=round((time.perf_counter() - started_at) * 1000, 2),
        )


@asynccontextmanager
async def lifespan(app: FastAPI):
    if settings.preload_model:
        await asyncio.to_thread(model_manager.load)

    _log_json(
        "model_serving_ready",
        served_model_name=settings.served_model_name,
        model_path=str(model_manager.model_path),
        model_path_exists=model_manager.model_path.exists(),
        model_loaded=model_manager.is_loaded,
        preload_model=settings.preload_model,
    )

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
    request_id = uuid4().hex
    started_at = time.perf_counter()
    request_payload = request.model_dump(exclude_none=True)

    _log_json(
        "chat_completion_request",
        request_id=request_id,
        request_payload=request_payload,
    )

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
                _logged_stream(
                    model_manager.stream_chat_completion(payload),
                    request_id=request_id,
                    request_payload=request_payload,
                    started_at=started_at,
                ),
                media_type="text/event-stream",
            )
        except ModelUnavailableError as exc:
            _log_json(
                "chat_completion_error",
                request_id=request_id,
                request_payload=request_payload,
                elapsed_ms=round((time.perf_counter() - started_at) * 1000, 2),
                error=str(exc),
            )
            raise HTTPException(status_code=503, detail=str(exc)) from exc

    try:
        result = await asyncio.to_thread(model_manager.create_chat_completion, payload)
    except ModelUnavailableError as exc:
        _log_json(
            "chat_completion_error",
            request_id=request_id,
            request_payload=request_payload,
            elapsed_ms=round((time.perf_counter() - started_at) * 1000, 2),
            error=str(exc),
        )
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    if isinstance(result, dict):
        result.setdefault("id", f"chatcmpl-{int(time.time() * 1000)}")
        result.setdefault("object", "chat.completion")
        result.setdefault("created", int(time.time()))
        result.setdefault("model", settings.served_model_name)

    _log_json(
        "chat_completion_response",
        request_id=request_id,
        request_payload=request_payload,
        response_payload=result,
        elapsed_ms=round((time.perf_counter() - started_at) * 1000, 2),
    )

    return result
