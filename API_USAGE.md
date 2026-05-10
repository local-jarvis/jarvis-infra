# API Usage

이 문서는 로컬에서 실행 중인 Qwen2.5 7B Instruct GGUF FastAPI 서버의 API 사용법을 정리합니다.

기본 주소:

```text
http://localhost:8000
```

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
  "model_path": "/models/qwen2.5-7b-instruct-q4_k_m-00001-of-00002.gguf",
  "model_path_exists": true,
  "model_loaded": true
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
      "id": "qwen2.5-7b-instruct-gguf",
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
| `model` | string | 아니오 | 응답의 모델 이름. 생략하면 서버 기본값 사용 |
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
curl.exe -X POST http://localhost:8000/v1/chat/completions -H "Content-Type: application/json; charset=utf-8" -d '{"messages":[{"role":"user","content":"Say a short greeting in Korean only."}],"max_tokens":32,"temperature":0}'
```

한글 프롬프트:

```powershell
curl.exe -X POST http://localhost:8000/v1/chat/completions -H "Content-Type: application/json; charset=utf-8" -d '{"messages":[{"role":"user","content":"한국어로 짧게 인사해 주세요."}],"max_tokens":32,"temperature":0}'
```

인증이 켜져 있을 때:

```powershell
curl.exe -X POST http://localhost:8000/v1/chat/completions -H "Authorization: Bearer change-me" -H "Content-Type: application/json; charset=utf-8" -d '{"messages":[{"role":"user","content":"Respond with exactly OK."}],"max_tokens":8,"temperature":0}'
```

### Bash 예시

```bash
curl -X POST http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json; charset=utf-8" \
  -d '{"messages":[{"role":"user","content":"Respond with exactly OK."}],"max_tokens":8,"temperature":0}'
```

### 응답 예시

```json
{
  "id": "chatcmpl-d2f86c74-20be-4b28-b8ed-62c5a3b54afa",
  "object": "chat.completion",
  "created": 1778399910,
  "model": "qwen2.5-7b-instruct-gguf",
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
curl.exe -N -X POST http://localhost:8000/v1/chat/completions -H "Content-Type: application/json; charset=utf-8" -d '{"messages":[{"role":"user","content":"Respond with exactly OK."}],"max_tokens":8,"temperature":0,"stream":true}'
```

응답은 다음 형태의 SSE 이벤트로 전달됩니다.

```text
data: {"id":"...","object":"chat.completion.chunk",...}

data: [DONE]
```

## 오류 응답

모델 파일이 없거나 `llama-cpp-python`을 사용할 수 없으면 `503`을 반환합니다.

```json
{
  "detail": "GGUF model file not found: /models/model.gguf"
}
```

인증이 켜져 있고 토큰이 없거나 틀리면 `401`을 반환합니다.

```json
{
  "detail": "Invalid or missing API key."
}
```

JSON 형식이 잘못되면 `422`를 반환합니다. PowerShell에서 이 문제가 자주 발생하면 JSON 전체를 작은따옴표로 감싸세요.
