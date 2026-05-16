from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

try:
    from dotenv import load_dotenv
except ImportError:
    load_dotenv = None

if load_dotenv is not None:
    load_dotenv()


def _env(name: str, default: str = "") -> str:
    return os.getenv(name, default).strip()


def _env_int(name: str, default: int) -> int:
    value = _env(name)
    if not value:
        return default
    return int(value)


def _env_float(name: str, default: float) -> float:
    value = _env(name)
    if not value:
        return default
    return float(value)


def _env_bool(name: str, default: bool = False) -> bool:
    value = _env(name).lower()
    if not value:
        return default
    return value in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class ModelSettings:
    name: str
    path: Path


def _env_models() -> tuple[ModelSettings, ...]:
    raw = _env("LLAMA_MODELS")
    if not raw:
        return (
            ModelSettings(
                name=_env("SERVED_MODEL_NAME", "gemma-3-4b-it-gguf"),
                path=Path(_env("LLAMA_MODEL_PATH", "./models/gemma-3-4b-it-Q4_K_M.gguf")),
            ),
        )

    models: list[ModelSettings] = []
    for entry in raw.replace("\n", ";").split(";"):
        entry = entry.strip()
        if not entry:
            continue

        name, separator, path = entry.partition("=")
        if not separator or not name.strip() or not path.strip():
            raise ValueError(
                "LLAMA_MODELS entries must use 'model-name=/path/to/model.gguf'."
            )

        models.append(ModelSettings(name=name.strip(), path=Path(path.strip())))

    if not models:
        raise ValueError("LLAMA_MODELS did not contain any valid model entries.")

    names = [model.name for model in models]
    if len(set(names)) != len(names):
        raise ValueError("LLAMA_MODELS contains duplicate model names.")

    return tuple(models)


@dataclass(frozen=True)
class Settings:
    app_name: str = _env("APP_NAME", "jarvis-llamacpp-fastapi")
    api_key: str = _env("API_KEY")
    models: tuple[ModelSettings, ...] = _env_models()
    default_model_name: str = _env("DEFAULT_MODEL_NAME")

    n_ctx: int = _env_int("LLAMA_N_CTX", 4096)
    n_threads: int = _env_int("LLAMA_N_THREADS", 0)
    n_gpu_layers: int = _env_int("LLAMA_N_GPU_LAYERS", 0)
    chat_format: str = _env("LLAMA_CHAT_FORMAT")
    preload_model: bool = _env_bool("LLAMA_PRELOAD_MODEL", False)
    verbose: bool = _env_bool("LLAMA_VERBOSE", False)

    default_max_tokens: int = _env_int("DEFAULT_MAX_TOKENS", 512)
    default_temperature: float = _env_float("DEFAULT_TEMPERATURE", 0.7)
    default_top_p: float = _env_float("DEFAULT_TOP_P", 0.95)

    cors_origins: tuple[str, ...] = tuple(
        origin.strip()
        for origin in _env("CORS_ORIGINS").split(",")
        if origin.strip()
    )


settings = Settings()
