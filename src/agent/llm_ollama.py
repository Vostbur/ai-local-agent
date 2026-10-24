"""Ollama LLM client."""

import json
import logging
import requests

from src.agent.llm import LLMResponse
from src.agent.registry import ToolDefinition

logger = logging.getLogger("agent")


class OllamaLLM:
    def __init__(
        self,
        model: str = "qwen2.5-3b-agent",
        base_url: str = "http://localhost:11434",
        timeout: int = 300,
        tools: list[ToolDefinition] | None = None,
    ) -> None:
        self.model = model
        self.base_url = base_url
        self.timeout = timeout
        self.tools = tools or []

    def chat(self, messages: list[dict]) -> LLMResponse:
        logger.info(
            "Ollama request: model=%s, messages=%s",
            self.model,
            messages,
        )

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
            "tool_choice": "auto",
        }
        if tools_payload is not None:
            payload["tools"] = tools_payload

        try:
            resp = requests.post(
                f"{self.base_url}/v1/chat/completions",
                json=payload,
                timeout=self.timeout,
            )
            resp.raise_for_status()
        except requests.RequestException as exc:
            raise RuntimeError(f"Ollama request failed: {exc}")

        data = resp.json()
        msg = data["choices"][0]["message"]

        tool_calls = msg.get("tool_calls")
        if tool_calls:
            tc = tool_calls[0]
            name = tc["function"]["name"]
            args = json.loads(tc["function"]["arguments"])
            logger.info("Ollama response: type=tool_call, tool_name=%s", name)
            return LLMResponse(
                type="tool_call",
                tool_name=name,
                tool_arguments=args,
            )

        logger.info("Ollama response: type=final")
        return LLMResponse(type="final", content=msg.get("content"))
