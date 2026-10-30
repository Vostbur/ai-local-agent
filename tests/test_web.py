"""Tests for the FastAPI web interface."""

from __future__ import annotations

import logging
from pathlib import Path

from fastapi.testclient import TestClient

from src.agent.config import (
    AppConfig,
    LLMConfig,
    PathsConfig,
    RAGConfig,
    SafetyConfig,
)
from src.agent.orchestrator import FinalEvent, OrchestratorResult, StepEvent
from src.agent.web.app import create_app

logger = logging.getLogger("test")


def _make_config(tmp_path: Path) -> AppConfig:
    return AppConfig(
        llm=LLMConfig(model="test-model", max_steps=3),
        paths=PathsConfig(
            data_dir=tmp_path / "data",
            notes_dir=tmp_path / "data" / "notes",
            inbox_dir=tmp_path / "data" / "inbox",
            photos_dir=tmp_path / "data" / "photos",
            documents_dir=tmp_path / "data" / "documents",
            logs_dir=tmp_path / "logs",
            generated_dir=tmp_path / "data" / "generated",
            index_dir=tmp_path / "data" / "index",
        ),
        safety=SafetyConfig(),
        rag=RAGConfig(),
    )


class _MockService:
    """Простой AgentService-мок: одна задача — одно финальное событие."""

    def __init__(self, final_answer: str = "ok"):
        self.final_answer = final_answer
        self.calls: list[tuple[str, str]] = []  # (use_tools, goal)

    def _events(self, goal: str, use_tools: bool):
        self.calls.append(("tools" if use_tools else "plain", goal))
        yield StepEvent(step=1, event_type="llm_call")
        yield FinalEvent(
            OrchestratorResult(
                success=True,
                final_answer=self.final_answer,
                steps_used=1,
            )
        )

    def ask(self, goal: str):
        yield from self._events(goal, use_tools=True)

    def ask_plain(self, goal: str):
        yield from self._events(goal, use_tools=False)


def _client(tmp_path: Path, service=None) -> TestClient:
    app = create_app(_make_config(tmp_path), logger, service=service)
    return TestClient(app)


def test_index_page_returns_html(tmp_path):
    client = _client(tmp_path)
    resp = client.get("/")
    assert resp.status_code == 200
    assert "AI Local Agent" in resp.text
    assert "Агент" in resp.text
    assert "Документы" in resp.text
    assert "Чат" in resp.text


def test_health(tmp_path):
    client = _client(tmp_path)
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_ask_returns_task_id(tmp_path):
    service = _MockService()
    client = _client(tmp_path, service=service)
    resp = client.post("/ask", json={"goal": "test goal"})
    assert resp.status_code == 200
    data = resp.json()
    assert "task_id" in data
    assert isinstance(data["task_id"], str)


def test_ask_plain_returns_task_id(tmp_path):
    service = _MockService()
    client = _client(tmp_path, service=service)
    resp = client.post("/ask-plain", json={"goal": "hello"})
    assert resp.status_code == 200
    assert "task_id" in resp.json()


def test_stream_returns_sse_events(tmp_path):
    service = _MockService(final_answer="final answer")
    client = _client(tmp_path, service=service)
    resp = client.post("/ask", json={"goal": "test"})
    task_id = resp.json()["task_id"]

    with client.stream("GET", f"/stream/{task_id}") as stream:
        text = stream.read().decode("utf-8")

    assert "event: step" in text
    assert "event: final" in text
    assert "final answer" in text
    assert service.calls[0] == ("tools", "test")


def test_stream_plain_uses_ask_plain(tmp_path):
    service = _MockService(final_answer="plain answer")
    client = _client(tmp_path, service=service)
    resp = client.post("/ask-plain", json={"goal": "hello"})
    task_id = resp.json()["task_id"]

    with client.stream("GET", f"/stream/{task_id}") as stream:
        text = stream.read().decode("utf-8")

    assert "plain answer" in text
    assert service.calls[0] == ("plain", "hello")


def test_stream_unknown_task_returns_404(tmp_path):
    client = _client(tmp_path)
    resp = client.get("/stream/nonexistent-id")
    assert resp.status_code == 404


def test_index_endpoint_propagates_errors(tmp_path, monkeypatch):
    """Если build_index бросает FileNotFoundError — эндпоинт вернёт success=False."""

    def fake_build(*args, **kwargs):
        raise FileNotFoundError("documents root does not exist: /fake")

    monkeypatch.setattr("src.agent.web.app.build_index", fake_build)
    client = _client(tmp_path)
    resp = client.post("/index", json={"reset": True, "documents": None})
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is False
    assert "does not exist" in data["error"]