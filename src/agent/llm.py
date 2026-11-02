"""Интерфейс и базовые типы для LLM-клиентов."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Protocol


@dataclass
class LLMResponse:
    """Ответ от языковой модели."""
    type: Literal["tool_call", "final"]
    content: str | None = None
    tool_name: str | None = None
    tool_arguments: dict | None = None


class LLMClient(Protocol):
    """Протокол для LLM-клиентов (синхронный и асинхронный интерфейсы)."""

    def chat(self, messages: list[dict]) -> LLMResponse:
        """Синхронный вызов модели."""
        ...

    async def chat_async(self, messages: list[dict]) -> LLMResponse:
        """Асинхронный вызов модели."""
        ...


class FakeLLM:
    """Фиктивный клиент для тестов."""

    def __init__(self, responses: list[LLMResponse]) -> None:
        self.responses: list[LLMResponse] = list(responses)
        self.calls: list[list[dict]] = []

    def chat(self, messages: list[dict]) -> LLMResponse:
        self.calls.append(messages)
        if not self.responses:
            raise RuntimeError("FakeLLM ran out of responses")
        return self.responses.pop(0)

    async def chat_async(self, messages: list[dict]) -> LLMResponse:
        return self.chat(messages)