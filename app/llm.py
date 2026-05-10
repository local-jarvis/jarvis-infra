from __future__ import annotations

import json
import threading
from pathlib import Path
from typing import Any, Dict, Iterator, Optional

from .config import Settings


class ModelUnavailableError(RuntimeError):
    pass


class LlamaModelManager:
    def __init__(self, settings: Settings):
        self.settings = settings
        self._llm: Optional[Any] = None
        self._load_lock = threading.Lock()
        self._infer_lock = threading.Lock()

    @property
    def is_loaded(self) -> bool:
        return self._llm is not None

    @property
    def model_path(self) -> Path:
        return self.settings.model_path

    def load(self) -> Any:
        if self._llm is not None:
            return self._llm

        with self._load_lock:
            if self._llm is not None:
                return self._llm

            if not self.model_path.exists():
                raise ModelUnavailableError(
                    f"GGUF model file not found: {self.model_path}"
                )

            try:
                from llama_cpp import Llama
            except ImportError as exc:
                raise ModelUnavailableError(
                    "llama-cpp-python is not installed. Run `pip install -r requirements.txt`."
                ) from exc

            kwargs: Dict[str, Any] = {
                "model_path": str(self.model_path),
                "n_ctx": self.settings.n_ctx,
                "n_gpu_layers": self.settings.n_gpu_layers,
                "verbose": self.settings.verbose,
            }

            if self.settings.n_threads > 0:
                kwargs["n_threads"] = self.settings.n_threads

            if self.settings.chat_format:
                kwargs["chat_format"] = self.settings.chat_format

            self._llm = Llama(**kwargs)
            return self._llm

    def create_chat_completion(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        llm = self.load()
        with self._infer_lock:
            result = llm.create_chat_completion(**payload)

        if isinstance(result, dict):
            result.setdefault("model", self.settings.served_model_name)
        return result

    def stream_chat_completion(self, payload: Dict[str, Any]) -> Iterator[str]:
        llm = self.load()
        stream_payload = {**payload, "stream": True}

        with self._infer_lock:
            for chunk in llm.create_chat_completion(**stream_payload):
                yield f"data: {json.dumps(chunk, ensure_ascii=False)}\n\n"

        yield "data: [DONE]\n\n"
