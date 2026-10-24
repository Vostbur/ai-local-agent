"""Регистр инструментов агента."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any


@dataclass
class ToolDefinition:
    """Описание одного инструмента.

    Атрибуты:
        name: Уникальное имя инструмента.
        description: Описание назначения инструмента.
        parameters: Схема параметров (JSON Schema-подобная структура).
        func: Вызываемый объект, реализующий инструмент.
    """

    name: str
    description: str
    parameters: dict[str, Any]
    func: Callable[..., Any]


class ToolRegistry:
    """Централизованный реестр инструментов агента.

    Все методы работают со словарём ``_tools``, ключ — имя инструмента.
    """

    def __init__(self) -> None:
        self._tools: dict[str, ToolDefinition] = {}

    def register(self, tool: ToolDefinition) -> None:
        """Регистрирует инструмент.

        Raises:
            ValueError: Если инструмент с таким именем уже зарегистрирован.
        """
        if tool.name in self._tools:
            raise ValueError(
                f"Инструмент '{tool.name}' уже зарегистрирован"
            )
        self._tools[tool.name] = tool

    def get(self, name: str) -> ToolDefinition:
        """Возвращает определение инструмента по имени.

        Raises:
            KeyError: Если инструмент не найден.
        """
        try:
            return self._tools[name]
        except KeyError:
            raise KeyError(f"Инструмент '{name}' не найден")

    def list_tools(self) -> list[ToolDefinition]:
        """Возвращает список всех зарегистрированных инструментов."""
        return list(self._tools.values())

    def call(self, name: str, /, **kwargs: Any) -> Any:
        """Вызывает инструмент по имени с переданными аргументами.

        Args:
            name: Имя инструмента.
            **kwargs: Аргументы для вызова функции инструмента.

        Returns:
            Результат вызова функции инструмента.

        Raises:
            KeyError: Если инструмент не найден.
        """
        tool = self.get(name)
        return tool.func(**kwargs)
