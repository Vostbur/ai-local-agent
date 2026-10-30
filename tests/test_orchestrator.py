"""Tests for Orchestrator: цикл plan-execute, защита от повторов, промпты."""

import logging
from pathlib import Path

import pytest

from src.agent.llm import FakeLLM, LLMResponse
from src.agent.orchestrator import (
    SYSTEM_PROMPT,
    MaxStepsExceeded,
    Orchestrator,
)
from src.agent.registry import ToolDefinition, ToolRegistry
from src.agent.tools.save_note import SAVE_NOTE_TOOL

logger = logging.getLogger("test")


# ---------------------------------------------------------------------------
# Базовый цикл
# ---------------------------------------------------------------------------


def test_llm_returns_final_immediately():
    llm = FakeLLM([LLMResponse(type="final", content="done")])
    registry = ToolRegistry()
    orchestrator = Orchestrator(llm, registry, logger)

    result = orchestrator.run("do it")

    assert result.success is True
    assert result.final_answer == "done"
    assert result.steps_used == 1
    assert len(llm.calls) == 1


def test_llm_returns_tool_call_then_final():
    def echo_tool(text: str) -> str:
        return text

    registry = ToolRegistry()
    registry.register(
        ToolDefinition(
            name="echo",
            description="Echo the text",
            parameters={
                "type": "object",
                "properties": {"text": {"type": "string"}},
            },
            func=echo_tool,
        )
    )

    llm = FakeLLM(
        [
            LLMResponse(
                type="tool_call",
                tool_name="echo",
                tool_arguments={"text": "hi"},
            ),
            LLMResponse(type="final", content="echoed"),
        ]
    )
    orchestrator = Orchestrator(llm, registry, logger)

    result = orchestrator.run("echo hi")

    assert result.success is True
    assert result.final_answer == "echoed"
    assert result.steps_used == 2
    assert len(llm.calls) == 2


def test_llm_always_returns_tool_call_raises():
    llm = FakeLLM(
        [
            LLMResponse(type="tool_call", tool_name="noop", tool_arguments={}),
            LLMResponse(type="tool_call", tool_name="noop", tool_arguments={}),
            LLMResponse(type="tool_call", tool_name="noop", tool_arguments={}),
        ]
    )
    registry = ToolRegistry()
    orchestrator = Orchestrator(llm, registry, logger, max_steps=3)

    with pytest.raises(MaxStepsExceeded):
        orchestrator.run("loop")


# ---------------------------------------------------------------------------
# Ошибки инструментов и статусы tool_result
# ---------------------------------------------------------------------------


def test_tool_raises_error_orchestrator_continues():
    def boom_tool(**kwargs) -> str:
        raise RuntimeError("boom")

    registry = ToolRegistry()
    registry.register(
        ToolDefinition(
            name="boom",
            description="always fails",
            parameters={"type": "object", "properties": {}},
            func=boom_tool,
        )
    )

    llm = FakeLLM(
        [
            LLMResponse(type="tool_call", tool_name="boom", tool_arguments={}),
            LLMResponse(type="final", content="recovered"),
        ]
    )
    orchestrator = Orchestrator(llm, registry, logger)

    result = orchestrator.run("try boom")

    assert result.success is True
    assert result.final_answer == "recovered"
    tool_results = [
        m
        for m in llm.calls[-1]
        if m["role"] == "user" and m["content"].startswith("tool_result")
    ]
    assert any("ERROR: boom" in m["content"] for m in tool_results)


def test_successful_call_yields_success_status():
    def echo_tool(text: str) -> str:
        return text

    registry = ToolRegistry()
    registry.register(
        ToolDefinition(
            name="echo",
            description="Echo the text",
            parameters={
                "type": "object",
                "properties": {"text": {"type": "string"}},
            },
            func=echo_tool,
        )
    )

    llm = FakeLLM(
        [
            LLMResponse(
                type="tool_call",
                tool_name="echo",
                tool_arguments={"text": "hi"},
            ),
            LLMResponse(type="final", content="done"),
        ]
    )
    orchestrator = Orchestrator(llm, registry, logger)

    orchestrator.run("echo hi")

    tool_results = [
        m
        for m in llm.calls[-1]
        if m["role"] == "user" and m["content"].startswith("tool_result")
    ]
    assert any("tool_result: SUCCESS." in m["content"] for m in tool_results)
    assert not any("SKIPPED" in m["content"] for m in tool_results)
    assert not any("tool_result: ERROR." in m["content"] for m in tool_results)


def test_failed_call_yields_error_status():
    def boom_tool(**kwargs) -> str:
        raise RuntimeError("boom")

    registry = ToolRegistry()
    registry.register(
        ToolDefinition(
            name="boom",
            description="always fails",
            parameters={"type": "object", "properties": {}},
            func=boom_tool,
        )
    )

    llm = FakeLLM(
        [
            LLMResponse(type="tool_call", tool_name="boom", tool_arguments={}),
            LLMResponse(type="final", content="done"),
        ]
    )
    orchestrator = Orchestrator(llm, registry, logger)

    orchestrator.run("try boom")

    tool_results = [
        m
        for m in llm.calls[-1]
        if m["role"] == "user" and m["content"].startswith("tool_result")
    ]
    assert any("tool_result: ERROR." in m["content"] for m in tool_results)


# ---------------------------------------------------------------------------
# tool_context
# ---------------------------------------------------------------------------


def test_save_note_via_tool_context(tmp_path: Path):
    llm = FakeLLM(
        [
            LLMResponse(
                type="tool_call",
                tool_name="save_note",
                tool_arguments={"title": "My Note", "content": "hello world"},
            ),
            LLMResponse(type="final", content="saved"),
        ]
    )

    registry = ToolRegistry()
    registry.register(SAVE_NOTE_TOOL)

    orchestrator = Orchestrator(
        llm,
        registry,
        logger,
        tool_context={"save_note": {"notes_dir": tmp_path}},
    )

    result = orchestrator.run("save a note")

    assert result.success is True
    files = list(tmp_path.glob("*.md"))
    assert len(files) == 1
    assert files[0].read_text(encoding="utf-8").startswith("# My Note")

    # Во втором запросе assistant-сообщение не должно содержать notes_dir:
    # модель его не передавала, путь пришёл из tool_context.
    second_call = llm.calls[1]
    assistant_messages = [m for m in second_call if m["role"] == "assistant"]
    assert len(assistant_messages) == 1
    assert "tool_call: save_note" in assistant_messages[0]["content"]
    assert "notes_dir" not in assistant_messages[0]["content"]


# ---------------------------------------------------------------------------
# Системный промпт
# ---------------------------------------------------------------------------


def test_system_prompt_is_added():
    llm = FakeLLM([LLMResponse(type="final", content="ok")])
    registry = ToolRegistry()
    orchestrator = Orchestrator(llm, registry, logger)

    orchestrator.run("goal")

    assert llm.calls[0][0]["role"] == "system"
    assert llm.calls[0][1]["role"] == "user"


def test_system_prompt_mentions_tool_routing():
    assert "read_notes" in SYSTEM_PROMPT
    assert "search_notes" in SYSTEM_PROMPT


def test_system_prompt_has_few_shot_examples():
    """SYSTEM_PROMPT содержит few-shot примеры для routing (7.2.2)."""
    assert "search_documents" in SYSTEM_PROMPT
    assert "search_notes" in SYSTEM_PROMPT
    assert "save_note" in SYSTEM_PROMPT

    # Минимум 5 примеров (символ → в примерах)
    assert SYSTEM_PROMPT.count("→") >= 5

    # Ключевые триггеры из провальных вопросов
    assert "версия Python" in SYSTEM_PROMPT
    assert "установка" in SYSTEM_PROMPT
    assert "запуск" in SYSTEM_PROMPT
    assert "лицензия" in SYSTEM_PROMPT
    assert "статья" in SYSTEM_PROMPT


def test_system_prompt_has_template_generation_rules():
    """SYSTEM_PROMPT содержит правила генерации документа по шаблону (7.3)."""
    assert "read_document" in SYSTEM_PROMPT
    assert "write_document" in SYSTEM_PROMPT

    prompt_lower = SYSTEM_PROMPT.lower()
    assert "не спрашивай подтверждения" in prompt_lower
    assert "не копируй" in prompt_lower
    assert "на русском" in prompt_lower


def test_system_prompt_does_not_contain_write_document_few_shot():
    """Few-shot вида '→ write_document(...)' провоцирует 7B писать вызов
    инструмента текстом вместо tool_call (регрессия 7.3).

    Описания сигнатур в списке инструментов
    ('- write_document(title, content) — ...') допустимы.
    Запрещён именно паттерн «вопрос → вызов(...)».
    """
    assert "→ write_document(" not in SYSTEM_PROMPT
    assert "→ read_document(" not in SYSTEM_PROMPT


# ---------------------------------------------------------------------------
# Защита от повторных вызовов
# ---------------------------------------------------------------------------


def test_repeated_identical_tool_call_is_skipped():
    call_count = 0

    def echo_tool(text: str) -> str:
        nonlocal call_count
        call_count += 1
        return text

    registry = ToolRegistry()
    registry.register(
        ToolDefinition(
            name="echo",
            description="Echo the text",
            parameters={
                "type": "object",
                "properties": {"text": {"type": "string"}},
            },
            func=echo_tool,
        )
    )

    llm = FakeLLM(
        [
            LLMResponse(
                type="tool_call",
                tool_name="echo",
                tool_arguments={"text": "hi"},
            ),
            LLMResponse(
                type="tool_call",
                tool_name="echo",
                tool_arguments={"text": "hi"},
            ),
            LLMResponse(type="final", content="done"),
        ]
    )
    orchestrator = Orchestrator(llm, registry, logger)

    result = orchestrator.run("echo hi")

    assert call_count == 1
    tool_results = [
        m
        for m in llm.calls[-1]
        if m["role"] == "user" and m["content"].startswith("tool_result")
    ]
    assert any("tool_result: SKIPPED." in m["content"] for m in tool_results)
    assert result.success is True
    assert result.final_answer == "done"


def test_failing_tool_gives_up_after_max_failures():
    call_count = 0

    def boom_tool(**kwargs) -> str:
        nonlocal call_count
        call_count += 1
        raise RuntimeError("boom")

    registry = ToolRegistry()
    registry.register(
        ToolDefinition(
            name="boom",
            description="always fails",
            parameters={"type": "object", "properties": {}},
            func=boom_tool,
        )
    )

    llm = FakeLLM(
        [
            LLMResponse(type="tool_call", tool_name="boom", tool_arguments={}),
            LLMResponse(type="tool_call", tool_name="boom", tool_arguments={}),
            LLMResponse(type="tool_call", tool_name="boom", tool_arguments={}),
            LLMResponse(type="final", content="done"),
        ]
    )
    orchestrator = Orchestrator(llm, registry, logger)

    result = orchestrator.run("try boom")

    assert call_count == 2
    assert result.success is True
    assert result.final_answer == "done"
    tool_results = [
        m
        for m in llm.calls[-1]
        if m["role"] == "user" and m["content"].startswith("tool_result")
    ]
    assert any("giving up" in m["content"] for m in tool_results)
    assert any("Do NOT call it again" in m["content"] for m in tool_results)


def test_failed_call_does_not_block_success_after_retry():
    call_count = 0

    def flaky_tool(**kwargs) -> str:
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise RuntimeError("first attempt fails")
        return "ok"

    registry = ToolRegistry()
    registry.register(
        ToolDefinition(
            name="flaky",
            description="fails once, then works",
            parameters={"type": "object", "properties": {}},
            func=flaky_tool,
        )
    )

    llm = FakeLLM(
        [
            LLMResponse(
                type="tool_call", tool_name="flaky", tool_arguments={}
            ),
            LLMResponse(
                type="tool_call", tool_name="flaky", tool_arguments={}
            ),
            LLMResponse(type="final", content="recovered"),
        ]
    )
    orchestrator = Orchestrator(llm, registry, logger)

    result = orchestrator.run("try flaky")

    assert call_count == 2
    assert result.success is True
    assert result.final_answer == "recovered"
    assert result.tool_results == ["ok"]


def test_max_tool_failures_from_constructor():
    """max_tool_failures управляет числом повторов падающего вызова."""
    call_count = 0

    def boom_tool(**kwargs) -> str:
        nonlocal call_count
        call_count += 1
        raise RuntimeError("boom")

    registry = ToolRegistry()
    registry.register(
        ToolDefinition(
            name="boom",
            description="always fails",
            parameters={"type": "object", "properties": {}},
            func=boom_tool,
        )
    )

    llm = FakeLLM(
        [
            LLMResponse(type="tool_call", tool_name="boom", tool_arguments={}),
            LLMResponse(type="tool_call", tool_name="boom", tool_arguments={}),
            LLMResponse(type="tool_call", tool_name="boom", tool_arguments={}),
            LLMResponse(type="tool_call", tool_name="boom", tool_arguments={}),
            LLMResponse(type="final", content="done"),
        ]
    )
    orchestrator = Orchestrator(
        llm, registry, logger, max_tool_failures=3
    )

    result = orchestrator.run("try boom")

    assert call_count == 3
    assert result.success is True
    tool_results = [
        m
        for m in llm.calls[-1]
        if m["role"] == "user" and m["content"].startswith("tool_result")
    ]
    assert any("failed 3 times" in m["content"] for m in tool_results)


# ---------------------------------------------------------------------------
# Неизвестный response.type
# ---------------------------------------------------------------------------


def test_unknown_response_type_returns_error():
    """Неизвестный response.type → OrchestratorResult с ошибкой, не зацикливание."""
    llm = FakeLLM([LLMResponse(type="unknown")])  # type: ignore[arg-type]
    registry = ToolRegistry()
    orchestrator = Orchestrator(llm, registry, logger)

    result = orchestrator.run("goal")

    assert result.success is False
    assert result.error is not None
    assert "unknown" in result.error
    assert result.steps_used == 1
    assert len(llm.calls) == 1


# ---------------------------------------------------------------------------
# Логирование
# ---------------------------------------------------------------------------


def test_tool_result_not_logged_in_full(caplog):
    """Содержимое списка (preview/snippet) не попадает в INFO-лог."""

    def secret_tool(**kwargs):
        return [{"title": "t", "preview": "SECRET_NOTE_TEXT"}]

    registry = ToolRegistry()
    registry.register(
        ToolDefinition(
            name="secret",
            description="returns sensitive data",
            parameters={"type": "object", "properties": {}},
            func=secret_tool,
        )
    )

    llm = FakeLLM(
        [
            LLMResponse(
                type="tool_call", tool_name="secret", tool_arguments={}
            ),
            LLMResponse(type="final", content="done"),
        ]
    )
    orchestrator = Orchestrator(llm, registry, logger)

    with caplog.at_level(logging.INFO, logger="test"):
        result = orchestrator.run("x")

    assert result.success is True
    assert "SECRET_NOTE_TEXT" not in caplog.text
    assert "list[1]" in caplog.text


def test_empty_final_yields_error():
    """final с пустым content → success=False, error='empty final answer'."""
    llm = FakeLLM([LLMResponse(type="final", content="")])
    registry = ToolRegistry()
    orchestrator = Orchestrator(llm, registry, logger)

    result = orchestrator.run("goal")

    assert result.success is False
    assert result.final_answer is None
    assert result.error == "empty final answer"
    assert result.steps_used == 1


def test_whitespace_only_final_yields_error():
    """final с пробелами/переносами → тоже empty."""
    llm = FakeLLM([LLMResponse(type="final", content="   \n\n  ")])
    registry = ToolRegistry()
    orchestrator = Orchestrator(llm, registry, logger)

    result = orchestrator.run("goal")

    assert result.success is False
    assert result.error == "empty final answer"


def test_on_step_called_for_tool_call():
    """on_step получает StepEvent для tool_result."""
    def echo_tool(text: str) -> str:
        return text

    registry = ToolRegistry()
    registry.register(
        ToolDefinition(
            name="echo",
            description="Echo the text",
            parameters={
                "type": "object",
                "properties": {"text": {"type": "string"}},
            },
            func=echo_tool,
        )
    )

    llm = FakeLLM(
        [
            LLMResponse(
                type="tool_call", tool_name="echo", tool_arguments={"text": "hi"}
            ),
            LLMResponse(type="final", content="done"),
        ]
    )
    orchestrator = Orchestrator(llm, registry, logger)

    events: list = []
    orchestrator.run("echo hi", on_step=events.append)

    tool_events = [e for e in events if e.event_type == "tool_result"]
    assert len(tool_events) == 1
    assert tool_events[0].tool_name == "echo"
    assert tool_events[0].status == "SUCCESS"
    assert tool_events[0].step == 1


def test_on_step_called_for_final():
    """on_step получает StepEvent final со status='ok'."""
    llm = FakeLLM([LLMResponse(type="final", content="done")])
    registry = ToolRegistry()
    orchestrator = Orchestrator(llm, registry, logger)

    events: list = []
    orchestrator.run("goal", on_step=events.append)

    final_events = [e for e in events if e.event_type == "final"]
    assert len(final_events) == 1
    assert final_events[0].status == "ok"

def test_system_prompt_lists_crud_tools() -> None:
    """SYSTEM_PROMPT перечисляет CRUD-инструменты заметок (этап B)."""
    for tool in (
        "list_notes",
        "update_note",
        "delete_note",
        "move_note",
        "list_categories",
    ):
        assert tool in SYSTEM_PROMPT, f"{tool} отсутствует в SYSTEM_PROMPT"


def test_system_prompt_requires_path_lookup_before_crud() -> None:
    """Правило: для update/delete/move_note нужен путь, а не заголовок.

    Страховка от сценария smoke 2026-10-30: модель передавала заголовок
    'Тест B1' вместо пути и сдавалась после ошибки. Проверка на точную
    фразу — по уроку про documentation rot.
    """
    assert "а НЕ название заметки" in SYSTEM_PROMPT
    assert "сначала вызови" in SYSTEM_PROMPT


def test_system_prompt_no_call_syntax_for_crud_tools() -> None:
    """Урок 7.3: синтаксиса вызова новых инструментов в промпте быть не должно."""
    for snippet in (
        "list_notes(",
        "update_note(",
        "delete_note(",
        "move_note(",
        "list_categories(",
    ):
        assert snippet not in SYSTEM_PROMPT


class _StubResponse:
    def __init__(self, type_, content=None, tool_name=None, tool_arguments=None):
        self.type = type_
        self.content = content
        self.tool_name = tool_name
        self.tool_arguments = tool_arguments


class _StubLLM:
    def __init__(self, responses):
        self._responses = list(responses)
        self.calls: list[list[dict]] = []

    def chat(self, messages):
        self.calls.append([dict(m) for m in messages])
        return self._responses.pop(0)


def test_error_tool_result_message_encourages_retry() -> None:
    """После ошибки инструмента модель получает призыв исправиться,
    а не предложение завершить задачу (итог smoke 2026-10-30)."""

    def _boom(**kwargs):
        raise FileNotFoundError("note not found")

    registry = ToolRegistry()
    registry.register(
        ToolDefinition(
            name="update_note",
            description="d",
            parameters={"type": "object", "properties": {}},
            func=_boom,
        )
    )
    llm = _StubLLM(
        [
            _StubResponse(
                "tool_call",
                tool_name="update_note",
                tool_arguments={"path": "Тест B1", "title": "X"},
            ),
            _StubResponse("final", content="готово"),
        ]
    )

    orchestrator = Orchestrator(
        llm=llm,
        registry=registry,
        logger=logging.getLogger("test"),
        max_steps=5,
    )
    result = orchestrator.run("измени заметку")

    assert result.success is True
    # Второй вызов chat: messages = [system, user, assistant, tool_result]
    error_message = llm.calls[1][3]["content"]
    assert "ERROR" in error_message
    assert "try again" in error_message
    assert "final answer now" not in error_message