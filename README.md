# jarvis-infra

Python FastAPI service for serving a pre-downloaded Gemma 3 4B Instruct GGUF
model through llama.cpp via `llama-cpp-python`.

## Layout

- `app/main.py`: FastAPI entrypoint
- `app/llm.py`: lazy llama.cpp model loader and inference lock
- `app/config.py`: environment-based runtime settings
- `docker-compose.yml`: local container runtime with `./models` mounted read-only

## Model

Place the GGUF file outside git, then point the service at it:

```powershell
$env:LLAMA_MODEL_PATH="C:\models\gemma-3-4b-it-Q4_K_M.gguf"
```

The current Docker Compose configuration expects Gemma 3 4B Instruct GGUF Q4_K_M:

```powershell
.\.venv\Scripts\hf.exe download ggml-org/gemma-3-4b-it-GGUF `
  --include "gemma-3-4b-it-Q4_K_M.gguf" `
  --local-dir models
```

## Local Run

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
$env:LLAMA_MODEL_PATH="C:\models\gemma-3-4b-it-Q4_K_M.gguf"
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

You can also copy `.env.example` to `.env`; the app loads it automatically.

## Docker Run

Docker Compose loads runtime environment values from `.env.docker`.
Copy `.env.docker.example` to `.env.docker`, then edit it for container paths
such as `/models/...`.

```powershell
Copy-Item .env.docker.example .env.docker
docker compose up --build
```

## API

Detailed API usage is available in [API_USAGE.md](API_USAGE.md).

The served model is logged when the app is ready. Chat completion requests and
responses are logged as single-line JSON messages with the `chat_log` prefix in
the application logs.

Health:

```powershell
curl.exe http://localhost:8000/healthz
curl.exe http://localhost:8000/readyz
```

Chat completion:

```powershell
curl.exe -X POST http://localhost:8000/v1/chat/completions `
  -H "Content-Type: application/json" `
  -d "{`"messages`":[{`"role`":`"user`",`"content`":`"안녕하세요. 한 문장으로 자기소개를 해주세요.`"}],`"max_tokens`":128}"
```

Optional API key:

```powershell
$env:API_KEY="change-me"
curl.exe -H "Authorization: Bearer change-me" http://localhost:8000/v1/models
```

## Runtime Settings

- `LLAMA_MODEL_PATH`: GGUF model path
- `LLAMA_N_CTX`: context size, default `4096`
- `LLAMA_N_THREADS`: CPU threads, default `0` lets llama.cpp decide
- `LLAMA_N_GPU_LAYERS`: GPU offload layers, default `0`
- `LLAMA_CHAT_FORMAT`: optional explicit chat format; empty uses GGUF metadata
- `LLAMA_PRELOAD_MODEL`: load model during startup when `true`
- `SERVED_MODEL_NAME`: model id returned by `/v1/models` and completions
- `DEFAULT_MAX_TOKENS`: default completion length, default `512`
- `DEFAULT_TEMPERATURE`: default temperature, default `0.7`
- `DEFAULT_TOP_P`: default top-p, default `0.95`
- `API_KEY`: optional token for `/v1/*` endpoints
