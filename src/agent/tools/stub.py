"""Stub-инструмент для тестирования."""

from __future__ import annotations

from src.agent.registry import ToolDefinition


def echo(text: str) -> str:
    """Возвращает входной текст без изменений."""
    return text


ECHO_TOOL: ToolDefinition = ToolDefinition(
    name="echo",
    description="Returns the input text unchanged. Used for testing.",
    parameters={
        "type": "object",
        "properties": {"text": {"type": "string"}},
        "required": ["text"],
    },
    func=echo,
)
