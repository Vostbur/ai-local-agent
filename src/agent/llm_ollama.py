"""Ollama LLM client."""
from __future__ import annotations

import asyncio
import json
import logging

import requests

from src.agent.llm import LLMResponse
from src.agent.registry import ToolDefinition

try:
    import httpx
    HAS_HTTPX = True
except ImportError:
    HAS_HTTPX = False

logger = logging.getLogger("agent")


class OllamaLLM:
    def __init__(
        self,
        model: str = "qwen2.5-3b-agent",
        base_url: str = "http://localhost:11434",
        timeout: int = 300,
        tools: list[ToolDefinition] | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
        keep_alive: str | int | None = -1,
    ) -> None:
        self.model = model
        self.base_url = base_url
        self.timeout = timeout
        self.tools = tools or []
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.keep_alive = keep_alive

    def _build_payload(self, messages: list[dict]) -> dict:
        """Собрать общий payload для синхронного и асинхронного запросов."""
        tools_payload = None
        if self.tools:
            tools_payload = [
                {
                    "type": "function",
                    "function": {
                        "name": t.name,
                        "description": t.description,
                        "parameters": t.parameters,
                    },
                }
                for t in self.tools
            ]

        payload: dict = {
            "model": self.model,
            "messages": messages,
            "stream": False,
        }

        if self.keep_alive is not None:
            payload["keep_alive"] = self.keep_alive

        if tools_payload is not None:
            payload["tools"] = tools_payload
            payload["tool_choice"] = "auto"

        if self.temperature is not None:
            payload["temperature"] = self.temperature

        if self.max_tokens is not None:
            payload["max_tokens"] = self.max_tokens

        return payload

    def _parse_response(self, data: dict) -> LLMResponse:
        """Общий парсинг ответа от Ollama."""
        if not isinstance(data, dict):
            raise RuntimeError(
                f"Ollama returned unexpected JSON type: {type(data).__name__}"
            )

        choices = data.get("choices")
        if not choices:
            raise RuntimeError("Ollama response has no choices")

        message = choices[0].get("message")
        if not isinstance(message, dict):
            raise RuntimeError("Ollama response has no message in first choice")

        tool_calls = message.get("tool_calls")
        if tool_calls:
            if len(tool_calls) > 1:
                logger.warning(
                    "Ollama returned %d tool_calls, using the first one",
                    len(tool_calls),
                )

            tc = tool_calls[0]
            try:
                name = tc["function"]["name"]
                raw_args = tc["function"]["arguments"]
            except (KeyError, TypeError) as exc:
                raise RuntimeError(
                    f"Ollama tool_call has invalid structure: {exc}"
                )

            try:
                args = json.loads(raw_args) if isinstance(raw_args, str) else raw_args
            except json.JSONDecodeError as exc:
                raise RuntimeError(
                    f"Ollama tool_call has invalid JSON arguments: {exc}"
                )

            if not isinstance(args, dict):
                raise RuntimeError(
                    f"Ollama tool_call arguments is not an object: "
                    f"{type(args).__name__}"
                )

            logger.info("Ollama response: type=tool_call, tool_name=%s", name)
            return LLMResponse(
                type="tool_call",
                tool_name=name,
                tool_arguments=args,
            )

        logger.info("Ollama response: type=final")
        return LLMResponse(type="final", content=message.get("content"))

    def _log_request(self, messages: list[dict], async_mode: bool) -> None:
        """Логирование запроса."""
        last = messages[-1] if messages else {}
        logger.info(
            "Ollama %srequest: model=%s, messages_count=%d, last_role=%s, last_len=%d",
            "async " if async_mode else "",
            self.model,
            len(messages),
            last.get("role"),
            len(last.get("content") or ""),
        )

    def chat(self, messages: list[dict]) -> LLMResponse:
        """Синхронный вызов модели (для CLI и обратной совместимости)."""
        self._log_request(messages, async_mode=False)
        payload = self._build_payload(messages)

        try:
            resp = requests.post(
                f"{self.base_url}/v1/chat/completions",
                json=payload,
                timeout=self.timeout,
            )
            resp.raise_for_status()
        except requests.RequestException as exc:
            raise RuntimeError(f"Ollama request failed: {exc}")

        try:
            data = resp.json()
        except ValueError as exc:
            raise RuntimeError(f"Ollama returned invalid JSON: {exc}")

        return self._parse_response(data)

    async def chat_async(self, messages: list[dict]) -> LLMResponse:
        """Асинхронный вызов модели.

        Если установлен httpx — используется асинхронный HTTP-клиент.
        Иначе — фолбэк на asyncio.to_thread с синхронным chat().
        """
        self._log_request(messages, async_mode=True)

        if not HAS_HTTPX:
            logger.debug("httpx not installed, falling back to sync chat in thread")
            return await asyncio.to_thread(self.chat, messages)

        payload = self._build_payload(messages)

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                resp = await client.post(
                    f"{self.base_url}/v1/chat/completions",
                    json=payload,
                )
                resp.raise_for_status()
            except httpx.HTTPError as exc:
                raise RuntimeError(f"Ollama async request failed: {exc}")

        try:
            data = resp.json()
        except ValueError as exc:
            raise RuntimeError(f"Ollama returned invalid JSON: {exc}")

        return self._parse_response(data)