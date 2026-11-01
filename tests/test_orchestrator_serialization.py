"""Тесты сериализации результатов инструментов в оркестраторе."""
import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from src.agent.orchestrator import _serialize_tool_result, OrchestratorResult


def test_serialize_primitives():
    """Проверяет сериализацию примитивных типов."""
    assert _serialize_tool_result(None) is None
    assert _serialize_tool_result("text") == "text"
    assert _serialize_tool_result(42) == 42
    assert _serialize_tool_result(3.14) == 3.14
    assert _serialize_tool_result(True) is True
    assert _serialize_tool_result(False) is False


def test_serialize_path():
    """Проверяет, что Path преобразуется в строку."""
    path = Path("data/notes/test.md")
    result = _serialize_tool_result(path)
    assert result == "data/notes/test.md"
    assert isinstance(result, str)


def test_serialize_dict():
    """Проверяет сериализацию словарей."""
    data = {
        "path": Path("data/notes/test.md"),
        "title": "Test",
        "count": 5,
        "nested": {"key": None},
    }
    result = _serialize_tool_result(data)
    assert result == {
        "path": "data/notes/test.md",
        "title": "Test",
        "count": 5,
        "nested": {"key": None},
    }
    # Проверяем, что результат сериализуется в валидный JSON
    json_str = json.dumps(result, ensure_ascii=False)
    assert "null" in json_str  # None должен стать null
    assert "'" not in json_str  # Не должно быть одинарных кавычек


def test_serialize_list():
    """Проверяет сериализацию списков."""
    data = [
        {"path": Path("data/notes/1.md"), "title": "Note 1"},
        {"path": Path("data/notes/2.md"), "title": "Note 2"},
    ]
    result = _serialize_tool_result(data)
    assert result == [
        {"path": "data/notes/1.md", "title": "Note 1"},
        {"path": "data/notes/2.md", "title": "Note 2"},
    ]
    # Проверяем, что результат сериализуется в валидный JSON
    json_str = json.dumps(result, ensure_ascii=False)
    assert json_str  # Не должно быть ошибок


def test_serialize_nested_structures():
    """Проверяет сериализацию вложенных структур."""
    data = {
        "results": [
            {"path": Path("a.md"), "tags": ["tag1", "tag2"]},
            {"path": Path("b.md"), "tags": []},
        ],
        "meta": {"total": 2, "paths": [Path("a.md"), Path("b.md")]},
    }
    result = _serialize_tool_result(data)
    
    # Проверяем, что результат сериализуется в валидный JSON
    json_str = json.dumps(result, ensure_ascii=False)
    parsed = json.loads(json_str)
    assert parsed["meta"]["paths"] == ["a.md", "b.md"]
    assert parsed["results"][0]["tags"] == ["tag1", "tag2"]


def test_orchestrator_result_tool_results_type():
    """Проверяет, что tool_results принимает структурированные данные."""
    result = OrchestratorResult(
        success=True,
        final_answer="Done",
        steps_used=1,
        tool_results=[
            {"path": "data/notes/test.md", "title": "Test"},
            [{"id": 1}, {"id": 2}],
        ],
    )
    assert result.tool_results[0]["title"] == "Test"
    assert len(result.tool_results[1]) == 2
    
    # Проверяем, что результат сериализуется в валидный JSON
    json_str = json.dumps(result.tool_results, ensure_ascii=False)
    assert json_str


def test_serialize_unknown_type():
    """Проверяет, что неизвестные типы преобразуются в строку."""
    class CustomObject:
        def __str__(self):
            return "custom_object_repr"
    
    result = _serialize_tool_result(CustomObject())
    assert result == "custom_object_repr"
    assert isinstance(result, str)