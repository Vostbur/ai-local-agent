import logging
from pathlib import Path

import pytest

from src.agent.llm import FakeLLM, LLMResponse
from src.agent.registry import ToolRegistry, ToolDefinition
from src.agent.orchestrator import Orchestrator, MaxStepsExceeded
from src.agent.tools.save_note import save_note, SAVE_NOTE_TOOL

logger = logging.getLogger("test")


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
            parameters={"type": "object", "properties": {"text": {"type": "string"}}},
            func=echo_tool,
        )
    )

    llm = FakeLLM([
        LLMResponse(type="tool_call", tool_name="echo", tool_arguments={"text": "hi"}),
        LLMResponse(type="final", content="echoed"),
    ])
    orchestrator = Orchestrator(llm, registry, logger)

    result = orchestrator.run("echo hi")

    assert result.success is True
    assert result.final_answer == "echoed"
    assert result.steps_used == 2
    assert len(llm.calls) == 2


def test_llm_always_returns_tool_call_raises():
    llm = FakeLLM([
        LLMResponse(type="tool_call", tool_name="noop", tool_arguments={}),
        LLMResponse(type="tool_call", tool_name="noop", tool_arguments={}),
        LLMResponse(type="tool_call", tool_name="noop", tool_arguments={}),
    ])
    registry = ToolRegistry()
    orchestrator = Orchestrator(llm, registry, logger, max_steps=3)

    with pytest.raises(MaxStepsExceeded):
        orchestrator.run("loop")


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

    llm = FakeLLM([
        LLMResponse(type="tool_call", tool_name="boom", tool_arguments={}),
        LLMResponse(type="final", content="recovered"),
    ])
    orchestrator = Orchestrator(llm, registry, logger)

    result = orchestrator.run("try boom")

    assert result.success is True
    assert result.final_answer == "recovered"
    tool_results = [m for m in llm.calls[-1] if m["role"] == "user" and m["content"].startswith("tool_result")]
    assert any("ERROR: boom" in m["content"] for m in tool_results)


def test_save_note_via_tool_context(tmp_path: Path):
    llm = FakeLLM([
        LLMResponse(
            type="tool_call",
            tool_name="save_note",
            tool_arguments={"title": "My Note", "content": "hello world"},
        ),
        LLMResponse(type="final", content="saved"),
    ])

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

    tool_call_args = llm.calls[0][-1].get("content", "")
    assert "notes_dir" not in tool_call_args


def test_system_prompt_is_added():
    llm = FakeLLM([LLMResponse(type="final", content="ok")])
    registry = ToolRegistry()
    orchestrator = Orchestrator(llm, registry, logger)

    orchestrator.run("goal")

    assert llm.calls[0][0]["role"] == "system"
    assert llm.calls[0][1]["role"] == "user"


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
            parameters={"type": "object", "properties": {"text": {"type": "string"}}},
            func=echo_tool,
        )
    )

    llm = FakeLLM([
        LLMResponse(type="tool_call", tool_name="echo", tool_arguments={"text": "hi"}),
        LLMResponse(type="tool_call", tool_name="echo", tool_arguments={"text": "hi"}),
        LLMResponse(type="final", content="done"),
    ])
    orchestrator = Orchestrator(llm, registry, logger)

    result = orchestrator.run("echo hi")

    assert call_count == 1
    tool_results = [m for m in llm.calls[-1] if m["role"] == "user" and m["content"].startswith("tool_result")]
    assert any("ALREADY_EXECUTED" in m["content"] for m in tool_results)
    assert result.success is True
    assert result.final_answer == "done"
