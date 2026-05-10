from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional, Union

from pydantic import BaseModel, Field


class ChatMessage(BaseModel):
    role: Literal["system", "user", "assistant"]
    content: str


class ChatCompletionRequest(BaseModel):
    model: Optional[str] = None
    messages: List[ChatMessage] = Field(..., min_length=1)
    max_tokens: Optional[int] = Field(default=None, ge=1)
    temperature: Optional[float] = Field(default=None, ge=0)
    top_p: Optional[float] = Field(default=None, ge=0, le=1)
    stream: bool = False
    stop: Optional[Union[str, List[str]]] = None
    presence_penalty: Optional[float] = None
    frequency_penalty: Optional[float] = None
    repeat_penalty: Optional[float] = None

    def llama_kwargs(
        self,
        *,
        default_max_tokens: int,
        default_temperature: float,
        default_top_p: float,
    ) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "messages": [message.model_dump() for message in self.messages],
            "max_tokens": self.max_tokens or default_max_tokens,
            "temperature": (
                self.temperature
                if self.temperature is not None
                else default_temperature
            ),
            "top_p": self.top_p if self.top_p is not None else default_top_p,
            "stream": self.stream,
        }

        for key in (
            "stop",
            "presence_penalty",
            "frequency_penalty",
            "repeat_penalty",
        ):
            value = getattr(self, key)
            if value is not None:
                payload[key] = value

        return payload
