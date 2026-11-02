"""FastAPI-приложение для локального веб-интерфейса агента.
Запуск: `python -m agent web` (порт 8000, только localhost).
"""
from __future__ import annotations

import asyncio
import json
import logging
import time
import uuid
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from src.agent.config import AppConfig
from src.agent.orchestrator import FinalEvent, OrchestratorResult, StepEvent
from src.agent.rag.build import build_index
from src.agent.service import AgentService

TEMPLATES_DIR = Path(__file__).parent / "templates"


class HistoryMessage(BaseModel):
    """Одна реплика истории диалога (T37). Роль — только user/assistant."""

    role: Literal["user", "assistant"]
    content: str


class AskRequest(BaseModel):
    goal: str
    history: list[HistoryMessage] | None = None


class IndexRequest(BaseModel):
    reset: bool = False
    documents: str | None = None


@dataclass
class TaskState:
    """Хранилище состояния задачи для поддержки переподключений."""
    events: list = field(default_factory=list)
    created_at: float = field(default_factory=time.time)
    finished_at: float | None = None
    async_task: asyncio.Task | None = None

    def is_finished(self) -> bool:
        return bool(self.events) and self.events[-1] is None

    def mark_finished(self):
        if self.finished_at is None:
            self.finished_at = time.time()


def cleanup_expired_tasks(app: FastAPI, current_time: float) -> int:
    """
    Удаляет завершенные задачи старше 5 минут и брошенные задачи старше 2 часов.
    Возвращает количество удаленных задач.
    """
    keys_to_delete = []
    for tid, st in list(app.state.tasks.items()):
        if st.is_finished():
            # Держим завершенные задачи 5 минут для возможных поздних переподключений
            if current_time - st.finished_at > 300:
                keys_to_delete.append(tid)
        else:
            # Удаляем брошенные или зависшие задачи через 2 часа
            if current_time - st.created_at > 7200:
                # Отменяем асинхронную задачу, если она ещё жива
                if st.async_task is not None and not st.async_task.done():
                    st.async_task.cancel()
                keys_to_delete.append(tid)

    for tid in keys_to_delete:
        app.state.tasks.pop(tid, None)

    return len(keys_to_delete)


def _format_sse(event: StepEvent | FinalEvent | None) -> str:
    """Сериализовать событие в SSE-блок."""
    if isinstance(event, StepEvent):
        payload = {
            "type": "step",
            "step": event.step,
            "event_type": event.event_type,
            "tool_name": event.tool_name,
            "status": event.status,
            "count": event.count,
        }
    elif isinstance(event, FinalEvent):
        r = event.result
        payload = {
            "type": "final",
            "success": r.success,
            "final_answer": r.final_answer,
            "steps_used": r.steps_used,
            "error": r.error,
            "tool_results": r.tool_results,
        }
    else:
        payload = {"type": "unknown"}

    return f"event: {payload['type']}\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"


async def _run_task_async(
    task_id: str,
    goal: str,
    state: TaskState,
    service: AgentService,
    use_tools: bool,
    history: list[dict] | None = None,
) -> None:
    """Асинхронная задача: прогнать цель, сохранить события в TaskState."""
    def add_event(ev):
        state.events.append(ev)
        if ev is None:
            state.mark_finished()

    try:
        events_iter = (
            service.ask_async(goal, history=history)
            if use_tools
            else service.ask_plain_async(goal, history=history)
        )
        async for event in events_iter:
            add_event(event)
    except asyncio.CancelledError:
        # Задача была отменена пользователем или фоновой очисткой
        fallback = FinalEvent(
            OrchestratorResult(
                success=False,
                final_answer=None,
                steps_used=0,
                error="cancelled",
            )
        )
        add_event(fallback)
        raise  # Пробрасываем, чтобы задача считалась отменённой
    except Exception as exc:  # noqa: BLE001
        fallback = FinalEvent(
            OrchestratorResult(
                success=False,
                final_answer=None,
                steps_used=0,
                error=f"internal: {exc}",
            )
        )
        add_event(fallback)
    finally:
        add_event(None)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Фоновая очистка зависших и завершенных задач для предотвращения утечки памяти."""
    async def cleanup_loop():
        while True:
            await asyncio.sleep(60)  # Проверка каждую минуту
            cleanup_expired_tasks(app, time.time())

    cleanup_task = asyncio.create_task(cleanup_loop())
    try:
        yield
    finally:
        cleanup_task.cancel()


def create_app(
    config: AppConfig,
    logger: logging.Logger,
    service: AgentService | None = None,
) -> FastAPI:
    """Собрать FastAPI-приложение."""
    app = FastAPI(title="AI Local Agent", docs_url="/api/docs", lifespan=lifespan)
    app.state.config = config
    app.state.logger = logger
    app.state.service = service or AgentService(config, logger)
    app.state.tasks: dict[str, TaskState] = {}

    @app.get("/health")
    def health() -> dict:
        return {"status": "ok"}

    def _start_task(
        goal: str,
        use_tools: bool,
        history: list[dict] | None = None,
    ) -> str:
        task_id = str(uuid.uuid4())
        state = TaskState()
        app.state.tasks[task_id] = state

        async_task = asyncio.create_task(
            _run_task_async(
                task_id, goal, state, app.state.service, use_tools, history
            )
        )
        state.async_task = async_task

        return task_id

    def _history_to_dicts(
        history: list[HistoryMessage] | None,
    ) -> list[dict] | None:
        if not history:
            return None
        return [m.model_dump() for m in history]

    @app.post("/ask")
    async def ask(payload: AskRequest) -> dict:
        """Запустить агента с инструментами. Возвращает task_id для /stream."""
        history = _history_to_dicts(payload.history)
        task_id = _start_task(payload.goal, use_tools=True, history=history)
        return {"task_id": task_id}

    @app.post("/ask-plain")
    async def ask_plain(payload: AskRequest) -> dict:
        """Запустить чат без инструментов. Возвращает task_id."""
        history = _history_to_dicts(payload.history)
        task_id = _start_task(payload.goal, use_tools=False, history=history)
        return {"task_id": task_id}

    @app.post("/cancel/{task_id}")
    async def cancel(task_id: str) -> dict:
        """Отменить выполняющуюся задачу."""
        if task_id not in app.state.tasks:
            raise HTTPException(status_code=404, detail="task not found")

        state = app.state.tasks[task_id]
        if state.is_finished():
            return {"status": "already_finished"}

        if state.async_task is not None and not state.async_task.done():
            state.async_task.cancel()
            return {"status": "cancelled"}

        return {"status": "no_active_task"}

    @app.get("/stream/{task_id}")
    async def stream(task_id: str) -> StreamingResponse:
        """SSE-поток событий задачи с поддержкой переподключений."""
        if task_id not in app.state.tasks:
            raise HTTPException(status_code=404, detail="task not found")

        state = app.state.tasks[task_id]

        async def gen():
            last_idx = 0
            try:
                while True:
                    if last_idx < len(state.events):
                        ev = state.events[last_idx]
                        if ev is None:
                            yield "event: end\ndata: {}\n\n"
                            return
                        yield _format_sse(ev)
                        last_idx += 1
                    else:
                        # Если задача завершена и больше событий не будет
                        if last_idx > 0 and state.is_finished():
                            return
                        # Простой опрос раз в 100 мс
                        await asyncio.sleep(0.1)
            finally:
                # Если клиент отключился после завершения задачи, удаляем её сразу
                if state.is_finished():
                    app.state.tasks.pop(task_id, None)

        return StreamingResponse(gen(), media_type="text/event-stream")

    @app.post("/index")
    def run_index(payload: IndexRequest) -> dict:
        """Пересобрать RAG-индекс. Блокирующий (FastAPI закроет в threadpool)."""
        root = (
            Path(payload.documents).resolve()
            if payload.documents
            else config.paths.documents_dir
        )
        try:
            store = build_index(
                root=root,
                config=config,
                reset=payload.reset,
                batch_size=32,
                logger=logger,
            )
            return {"success": True, "chunks": len(store), "error": None}
        except FileNotFoundError as exc:
            return {"success": False, "chunks": 0, "error": str(exc)}
        except FileExistsError as exc:
            return {
                "success": False,
                "chunks": 0,
                "error": f"{exc}. Используйте 'reset: true'.",
            }
        except Exception as exc:  # noqa: BLE001
            logger.exception("index failed")
            return {
                "success": False,
                "chunks": 0,
                "error": f"internal: {exc}",
            }

    # ВАЖНО: используем src.agent для всех импортов, чтобы избежать конфликта имен
    from src.agent.web.notes.app import make_notes_app
    app.mount("/notes", make_notes_app(config, logger))

    from src.agent.web.documents.app import make_documents_app
    app.mount("/documents", make_documents_app(config, logger))

    from src.agent.web.dashboard.app import make_dashboard_app
    app.mount("/", make_dashboard_app(config, logger))

    return app