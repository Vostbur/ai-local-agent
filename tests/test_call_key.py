"""Тесты стабильного call_key (T40)."""
from __future__ import annotations

from pathlib import Path

from src.agent.orchestrator import _make_call_key


def test_same_arguments_produce_same_key():
    """Одинаковые аргументы дают одинаковый ключ."""
    args = {"query": "python", "max_results": 5}
    assert _make_call_key("search_notes", args) == _make_call_key(
        "search_notes", args
    )


def test_different_arguments_produce_different_keys():
    """Разные аргументы дают разные ключи."""
    a = _make_call_key("search_notes", {"query": "python"})
    b = _make_call_key("search_notes", {"query": "ollama"})
    assert a != b


def test_dict_order_does_not_matter():
    """Порядок ключей в словаре не влияет на ключ (T40)."""
    a = _make_call_key("tool", {"a": 1, "b": 2, "c": 3})
    b = _make_call_key("tool", {"c": 3, "a": 1, "b": 2})
    assert a == b


def test_nested_dict_order_does_not_matter():
    """Порядок ключей во вложенных словарях не влияет на ключ (T40)."""
    a = _make_call_key(
        "tool", {"outer": {"z": 1, "a": 2}, "other": {"y": 3, "x": 4}}
    )
    b = _make_call_key(
        "tool", {"other": {"x": 4, "y": 3}, "outer": {"a": 2, "z": 1}}
    )
    assert a == b


def test_path_objects_normalize_to_posix():
    """Path-объекты дают одинаковый ключ независимо от представления (T40).

    На любой ОС ``Path('a/b.md')`` и ``Path('a') / 'b.md'`` должны
    давать одинаковый ключ. Это критично для детектора повторов.
    """
    a = _make_call_key("move_note", {"path": Path("a/b.md"), "category": "x"})
    b = _make_call_key("move_note", {"path": Path("a") / "b.md", "category": "x"})
    assert a == b
    # Ключ содержит POSIX-слэш, не Windows-слэш.
    assert "\\" not in a


def test_list_and_tuple_produce_same_key():
    """list и tuple с теми же элементами дают одинаковый ключ (T40)."""
    a = _make_call_key("tool", {"items": [1, 2, 3]})
    b = _make_call_key("tool", {"items": (1, 2, 3)})
    assert a == b


def test_tool_name_is_part_of_key():
    """Имя инструмента входит в ключ."""
    a = _make_call_key("search_notes", {"query": "x"})
    b = _make_call_key("search_documents", {"query": "x"})
    assert a != b


def test_none_value_serializes_cleanly():
    """None в аргументах сериализуется как JSON null, а не как Python-литерал."""
    key = _make_call_key("tool", {"a": None, "b": 1})
    # В ключе должен быть JSON-совместимый 'null', а не питоновское 'None'.
    assert "null" in key
    assert "None" not in key


def test_set_serializes_deterministically():
    """set сериализуется детерминированно (через list в _serialize_tool_result)."""
    a = _make_call_key("tool", {"items": {1, 2, 3}})
    b = _make_call_key("tool", {"items": {1, 2, 3}})
    assert a == b


def test_real_world_save_note_args_stable():
    """Реалистичные аргументы save_note дают стабильный ключ."""
    args = {
        "title": "Список покупок",
        "content": "- молоко\n- хлеб",
        "category": "Покупки",
    }
    k1 = _make_call_key("save_note", args)
    # Передаём в другом порядке.
    args_reordered = {
        "category": "Покупки",
        "content": "- молоко\n- хлеб",
        "title": "Список покупок",
    }
    k2 = _make_call_key("save_note", args_reordered)
    assert k1 == k2


def test_real_world_move_note_with_path_stable():
    """Реалистичные аргументы move_note с Path дают стабильный ключ (T40)."""
    args = {"path": Path("работа/вторая.md"), "category": "Архив"}
    k1 = _make_call_key("move_note", args)
    # Тот же путь, собранный иначе.
    args_alt = {"path": Path("работа") / "вторая.md", "category": "Архив"}
    k2 = _make_call_key("move_note", args_alt)
    assert k1 == k2