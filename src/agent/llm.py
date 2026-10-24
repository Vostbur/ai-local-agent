from dataclasses import dataclass, field
from typing import Literal, Protocol


@dataclass
class LLMResponse:
    type: Literal["tool_call", "final"]
    content: str | None = None
    tool_name: str | None = None
    tool_arguments: dict | None = None


class LLMClient(Protocol):
    def chat(self, messages: list[dict]) -> LLMResponse: ...


class FakeLLM:
    def __init__(self, responses: list[LLMResponse]) -> None:
        self.responses: list[LLMResponse] = list(responses)
        self.calls: list[list[dict]] = []

    def chat(self, messages: list[dict]) -> LLMResponse:
        self.calls.append(messages)
        if not self.responses:
            raise RuntimeError("FakeLLM ran out of responses")
        return self.responses.pop(0)
