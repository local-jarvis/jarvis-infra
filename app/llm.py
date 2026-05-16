from __future__ import annotations

import json
import threading
from dataclasses import dataclass, field
from typing import Any, Dict, Iterator, Optional

from .config import ModelSettings, Settings


class ModelUnavailableError(RuntimeError):
    pass


class UnknownModelError(ValueError):
    pass


@dataclass
class _ModelState:
    config: ModelSettings
    llm: Optional[Any] = None
    load_lock: threading.Lock = field(default_factory=threading.Lock)
    infer_lock: threading.Lock = field(default_factory=threading.Lock)


class LlamaModelManager:
    def __init__(self, settings: Settings):
        self.settings = settings
        self._models = {
            model.name: _ModelState(config=model)
            for model in settings.models
        }

    @property
    def default_model_name(self) -> str:
        return self.settings.default_model_name or self.settings.models[0].name

    @property
    def model_names(self) -> tuple[str, ...]:
        return tuple(self._models.keys())

    def resolve_model_name(self, model_name: Optional[str]) -> str:
        resolved = model_name or self.default_model_name
        if resolved not in self._models:
            available = ", ".join(self.model_names)
            raise UnknownModelError(
                f"Unknown model '{resolved}'. Available models: {available}"
            )
        return resolved

    def status(self) -> list[Dict[str, Any]]:
        return [
            {
                "id": name,
                "model_path": str(state.config.path),
                "model_path_exists": state.config.path.exists(),
                "model_loaded": state.llm is not None,
            }
            for name, state in self._models.items()
        ]

    def load(self, model_name: Optional[str] = None) -> Any:
        resolved = self.resolve_model_name(model_name)
        state = self._models[resolved]

        if state.llm is not None:
            return state.llm

        with state.load_lock:
            if state.llm is not None:
                return state.llm

            if not state.config.path.exists():
                raise ModelUnavailableError(
                    f"GGUF model file not found: {state.config.path}"
                )

            try:
                from llama_cpp import Llama
            except ImportError as exc:
                raise ModelUnavailableError(
                    "llama-cpp-python is not installed. Run `pip install -r requirements.txt`."
                ) from exc

            kwargs: Dict[str, Any] = {
                "model_path": str(state.config.path),
                "n_ctx": self.settings.n_ctx,
                "n_gpu_layers": self.settings.n_gpu_layers,
                "verbose": self.settings.verbose,
            }

            if self.settings.n_threads > 0:
                kwargs["n_threads"] = self.settings.n_threads

            if self.settings.chat_format:
                kwargs["chat_format"] = self.settings.chat_format

            state.llm = Llama(**kwargs)
            return state.llm

    def preload_all(self) -> None:
        for model_name in self.model_names:
            self.load(model_name)

    def create_chat_completion(
        self,
        model_name: str,
        payload: Dict[str, Any],
    ) -> Dict[str, Any]:
        resolved = self.resolve_model_name(model_name)
        state = self._models[resolved]
        llm = self.load(resolved)
        with state.infer_lock:
            result = llm.create_chat_completion(**payload)

        if isinstance(result, dict):
            result["model"] = resolved
        return result

    def stream_chat_completion(
        self,
        model_name: str,
        payload: Dict[str, Any],
    ) -> Iterator[str]:
        resolved = self.resolve_model_name(model_name)
        state = self._models[resolved]
        llm = self.load(resolved)
        stream_payload = {**payload, "stream": True}

        with state.infer_lock:
            for chunk in llm.create_chat_completion(**stream_payload):
                if isinstance(chunk, dict):
                    chunk["model"] = resolved
                yield f"data: {json.dumps(chunk, ensure_ascii=False)}\n\n"

        yield "data: [DONE]\n\n"
