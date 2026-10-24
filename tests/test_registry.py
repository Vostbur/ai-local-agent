"""Тесты для ToolRegistry."""

import pytest

from src.agent.registry import ToolDefinition, ToolRegistry


class TestToolRegistry:
    """Тесты для ToolRegistry."""

    def test_register_and_get(self):
        """Регистрация и получение инструмента."""
        registry = ToolRegistry()
        tool = ToolDefinition(
            name="echo",
            description="Возвращает переданный текст",
            parameters={},
            func=lambda text: text,
        )
        registry.register(tool)
        retrieved = registry.get("echo")
        assert retrieved.name == "echo"
        assert retrieved.description == "Возвращает переданный текст"

    def test_call_echo(self):
        """Вызов инструмента echo."""
        registry = ToolRegistry()
        registry.register(
            ToolDefinition(
                name="echo",
                description="Возвращает переданный текст",
                parameters={},
                func=lambda text: f"echo: {text}",
            )
        )
        result = registry.call("echo", text="hello")
        assert result == "echo: hello"

    def test_duplicate_name_raises_value_error(self):
        """Дубликат имени вызывает ValueError."""
        registry = ToolRegistry()
        tool = ToolDefinition(
            name="echo",
            description="Описание",
            parameters={},
            func=lambda: None,
        )
        registry.register(tool)
        with pytest.raises(ValueError, match="уже зарегистрирован"):
            registry.register(tool)

    def test_unknown_tool_raises_key_error(self):
        """Неизвестный инструмент вызывает KeyError."""
        registry = ToolRegistry()
        with pytest.raises(KeyError, match="не найден"):
            registry.get("nonexistent")
