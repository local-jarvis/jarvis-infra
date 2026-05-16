# API Usage

이 문서는 로컬에서 실행 중인 Gemma 3 Instruct GGUF FastAPI 서버의 API 사용법을 정리합니다.

기본 주소:

```text
http://localhost:8000
```

모델 선택은 요청 JSON의 `model` 필드로 합니다.

## 인증

기본값으로는 인증이 비활성화되어 있습니다.

`API_KEY` 환경 변수를 설정하면 `/v1/*` 엔드포인트에 인증이 필요합니다. 둘 중 하나를 사용할 수 있습니다.

```http
Authorization: Bearer <API_KEY>
```

```http
X-API-Key: <API_KEY>
```

예시:

```powershell
curl.exe -H "Authorization: Bearer change-me" http://localhost:8000/v1/models
```

## Health Check

서버 프로세스가 살아 있는지 확인합니다.

```http
GET /healthz
```

예시:

```powershell
curl.exe http://localhost:8000/healthz
```

응답:

```json
{
  "status": "ok"
}
```

## Readiness Check

모델 파일 경로가 존재하는지, 모델이 메모리에 로드되었는지 확인합니다.

```http
GET /readyz
```

예시:

```powershell
curl.exe http://localhost:8000/readyz
```

응답:

```json
{
  "status": "ready",
  "default_model": "gemma-3-4b-it-gguf",
  "models": [
    {
      "id": "gemma-3-4b-it-gguf",
      "model_path": "/models/gemma-3-4b-it-Q4_K_M.gguf",
      "model_path_exists": true,
      "model_loaded": true
    },
    {
      "id": "gemma-3-1b-it-gguf",
      "model_path": "/models/gemma-3-1b-it-Q4_K_M.gguf",
      "model_path_exists": true,
      "model_loaded": true
    }
  ]
}
```

`model_loaded`는 첫 추론 요청 전에는 `false`일 수 있습니다.

## Models

서버가 제공하는 모델 목록을 반환합니다.

```http
GET /v1/models
```

예시:

```powershell
curl.exe http://localhost:8000/v1/models
```

응답:

```json
{
  "object": "list",
  "data": [
    {
      "id": "gemma-3-4b-it-gguf",
      "object": "model",
      "created": 0,
      "owned_by": "local"
    },
    {
      "id": "gemma-3-1b-it-gguf",
      "object": "model",
      "created": 0,
      "owned_by": "local"
    }
  ]
}
```

## Chat Completions

OpenAI Chat Completions 형식에 가깝게 채팅 응답을 생성합니다.

```http
POST /v1/chat/completions
Content-Type: application/json
```

### 요청 필드

| 필드 | 타입 | 필수 | 설명 |
| --- | --- | --- | --- |
| `messages` | array | 예 | 대화 메시지 배열 |
| `messages[].role` | string | 예 | `system`, `user`, `assistant` 중 하나 |
| `messages[].content` | string | 예 | 메시지 본문 |
| `model` | string | 예 | 사용할 모델 이름. `/v1/models`의 `id` 중 하나 |
| `max_tokens` | integer | 아니오 | 생성할 최대 토큰 수 |
| `temperature` | number | 아니오 | 샘플링 온도. `0`은 결정적 응답에 가까움 |
| `top_p` | number | 아니오 | nucleus sampling 값 |
| `stream` | boolean | 아니오 | `true`면 Server-Sent Events 스트리밍 응답 |
| `stop` | string 또는 array | 아니오 | 생성 중단 문자열 |
| `presence_penalty` | number | 아니오 | llama.cpp에 전달되는 presence penalty |
| `frequency_penalty` | number | 아니오 | llama.cpp에 전달되는 frequency penalty |
| `repeat_penalty` | number | 아니오 | llama.cpp에 전달되는 repeat penalty |

### PowerShell 예시

PowerShell에서는 JSON 전체를 작은따옴표로 감싸는 방식이 가장 안전합니다.

```powershell
curl.exe -X POST http://localhost:8000/v1/chat/completions -H "Content-Type: application/json; charset=utf-8" -d '{"model":"gemma-3-4b-it-gguf","messages":[{"role":"user","content":"Say a short greeting in Korean only."}],"max_tokens":32,"temperature":0}'
```

한글 프롬프트:

```powershell
curl.exe -X POST http://localhost:8000/v1/chat/completions -H "Content-Type: application/json; charset=utf-8" -d '{"model":"gemma-3-1b-it-gguf","messages":[{"role":"user","content":"한국어로 짧게 인사해 주세요."}],"max_tokens":32,"temperature":0}'
```

인증이 켜져 있을 때:

```powershell
curl.exe -X POST http://localhost:8000/v1/chat/completions -H "Authorization: Bearer change-me" -H "Content-Type: application/json; charset=utf-8" -d '{"model":"gemma-3-4b-it-gguf","messages":[{"role":"user","content":"Respond with exactly OK."}],"max_tokens":8,"temperature":0}'
```

### Bash 예시

```bash
curl -X POST http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json; charset=utf-8" \
  -d '{"model":"gemma-3-4b-it-gguf","messages":[{"role":"user","content":"Respond with exactly OK."}],"max_tokens":8,"temperature":0}'
```

### 응답 예시

```json
{
  "id": "chatcmpl-d2f86c74-20be-4b28-b8ed-62c5a3b54afa",
  "object": "chat.completion",
  "created": 1778399910,
  "model": "gemma-3-4b-it-gguf",
  "choices": [
    {
      "index": 0,
      "message": {
        "role": "assistant",
        "content": "OK"
      },
      "logprobs": null,
      "finish_reason": "stop"
    }
  ],
  "usage": {
    "prompt_tokens": 34,
    "completion_tokens": 1,
    "total_tokens": 35
  }
}
```

## Streaming

`stream`을 `true`로 보내면 `text/event-stream` 형식으로 토큰 조각을 반환합니다.

```powershell
curl.exe -N -X POST http://localhost:8000/v1/chat/completions -H "Content-Type: application/json; charset=utf-8" -d '{"model":"gemma-3-4b-it-gguf","messages":[{"role":"user","content":"Respond with exactly OK."}],"max_tokens":8,"temperature":0,"stream":true}'
```

응답은 다음 형태의 SSE 이벤트로 전달됩니다.

```text
data: {"id":"...","object":"chat.completion.chunk",...}

data: [DONE]
```

## Logging

`/v1/chat/completions` 요청은 애플리케이션 로그에 `chat_log` prefix가 붙은
single-line JSON으로 남습니다.

앱이 준비되면 현재 서빙 모델도 기록됩니다.

```text
chat_log {"event":"model_serving_ready","default_model_name":"...","models":[...],"preload_model":true}
```

요청 시작 시에는 유저가 보낸 payload가 기록됩니다.

```text
chat_log {"event":"chat_completion_request","request_id":"...","request_payload":{...}}
```

응답 완료 시에는 같은 `request_id`로 유저 payload와 응답 payload가 함께 기록됩니다.
스트리밍 응답은 토큰 조각을 모은 최종 `content`가 기록됩니다.

```text
chat_log {"event":"chat_completion_response","request_id":"...","request_payload":{...},"response_payload":{...},"elapsed_ms":123.45}
```

## 오류 응답

모델 파일이 없거나 `llama-cpp-python`을 사용할 수 없으면 `503`을 반환합니다.

```json
{
  "detail": "GGUF model file not found: /models/model.gguf"
}
```

알 수 없는 `model` 값을 보내면 `404`를 반환합니다.

```json
{
  "detail": "Unknown model 'missing'. Available models: gemma-3-4b-it-gguf, gemma-3-1b-it-gguf"
}
```

인증이 켜져 있고 토큰이 없거나 틀리면 `401`을 반환합니다.

```json
{
  "detail": "Invalid or missing API key."
}
```

JSON 형식이 잘못되면 `422`를 반환합니다. PowerShell에서 이 문제가 자주 발생하면 JSON 전체를 작은따옴표로 감싸세요.
