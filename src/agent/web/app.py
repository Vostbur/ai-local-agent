"""FastAPI-приложение для локального веб-интерфейса агента.

Запуск: `python -m agent web` (порт 8000, только localhost).
"""

from __future__ import annotations

import asyncio
import json
import logging
import threading
import uuid
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, StreamingResponse
from pydantic import BaseModel

from src.agent.config import AppConfig
from src.agent.orchestrator import FinalEvent, OrchestratorResult, StepEvent
from src.agent.rag.build import build_index
from src.agent.service import AgentService

TEMPLATES_DIR = Path(__file__).parent / "templates"


class AskRequest(BaseModel):
    goal: str


class IndexRequest(BaseModel):
    reset: bool = False
    documents: str | None = None


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


def _run_task(
    task_id: str,
    goal: str,
    loop: asyncio.AbstractEventLoop,
    queue: asyncio.Queue,
    service: AgentService,
    use_tools: bool,
) -> None:
    """Фоновый поток: прогнать задачу, положить события в asyncio.Queue."""
    try:
        events = service.ask(goal) if use_tools else service.ask_plain(goal)
        for event in events:
            try:
                loop.call_soon_threadsafe(queue.put_nowait, event)
            except RuntimeError:
                return
    except Exception as exc:  # noqa: BLE001
        fallback = FinalEvent(
            OrchestratorResult(
                success=False,
                final_answer=None,
                steps_used=0,
                error=f"internal: {exc}",
            )
        )
        try:
            loop.call_soon_threadsafe(queue.put_nowait, fallback)
        except RuntimeError:
            return
    finally:
        try:
            loop.call_soon_threadsafe(queue.put_nowait, None)
        except RuntimeError:
            pass


def create_app(
    config: AppConfig,
    logger: logging.Logger,
    service: AgentService | None = None,
) -> FastAPI:
    """Собрать FastAPI-приложение.

    Args:
        config: конфигурация приложения (для `build_index`).
        logger: логгер для записи.
        service: если передан — используется вместо нового `AgentService`
            (для тестов).
    """
    app = FastAPI(title="AI Local Agent", docs_url="/api/docs")
    app.state.config = config
    app.state.logger = logger
    app.state.service = service or AgentService(config, logger)
    app.state.tasks: dict[str, asyncio.Queue] = {}

    index_html = (TEMPLATES_DIR / "index.html").read_text(encoding="utf-8")

    @app.get("/", response_class=HTMLResponse)
    def index_page() -> str:
        return index_html

    @app.get("/health")
    def health() -> dict:
        return {"status": "ok"}

    def _start_task(
        goal: str, use_tools: bool, loop: asyncio.AbstractEventLoop
    ) -> str:
        task_id = str(uuid.uuid4())
        queue: asyncio.Queue = asyncio.Queue()
        app.state.tasks[task_id] = queue
        threading.Thread(
            target=_run_task,
            args=(
                task_id,
                goal,
                loop,
                queue,
                app.state.service,
                use_tools,
            ),
            daemon=True,
        ).start()
        return task_id

    @app.post("/ask")
    async def ask(payload: AskRequest) -> dict:
        """Запустить агента с инструментами. Возвращает task_id для /stream."""
        loop = asyncio.get_running_loop()
        task_id = _start_task(payload.goal, use_tools=True, loop=loop)
        return {"task_id": task_id}

    @app.post("/ask-plain")
    async def ask_plain(payload: AskRequest) -> dict:
        """Запустить чат без инструментов. Возвращает task_id."""
        loop = asyncio.get_running_loop()
        task_id = _start_task(payload.goal, use_tools=False, loop=loop)
        return {"task_id": task_id}

    @app.get("/stream/{task_id}")
    async def stream(task_id: str) -> StreamingResponse:
        """SSE-поток событий задачи."""
        if task_id not in app.state.tasks:
            raise HTTPException(status_code=404, detail="task not found")

        queue = app.state.tasks[task_id]

        async def gen():
            try:
                while True:
                    event = await queue.get()
                    if event is None:
                        break
                    yield _format_sse(event)
            finally:
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

    @app.post("/analyze-image")
    def analyze_image() -> dict:
        raise HTTPException(
            status_code=501,
            detail=(
                "image analysis not yet implemented. "
                "См. TASKS.md, шаг 8."
            ),
        )

    return app