from __future__ import annotations
from pathlib import Path
from typing import Any
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

BASE = Path(__file__).parent
templates = Jinja2Templates(directory=BASE / "templates")

def make_dashboard_app(config: Any = None, logger: Any = None) -> FastAPI:
    app = FastAPI(title="Dashboard UI", docs_url=None, redoc_url=None, openapi_url=None)

    def _render(request: Request, name: str, extra: dict | None = None) -> HTMLResponse:
        ctx = {"request": request, **(extra or {})}
        return templates.TemplateResponse(request, name, ctx)

    # Главная страница дашборда (по умолчанию рендерит Агента)
    @app.get("/", response_class=HTMLResponse)
    def index(request: Request):
        # Рендерим base.html и вставляем внутрь views/agent.html
        # В реальном проекте можно сделать наследование Jinja2, но здесь просто вернем базовый шаблон
        return _render(request, "index.html")

    # Эндпоинты для подгрузки views
    @app.get("/views/agent", response_class=HTMLResponse)
    def view_agent(request: Request):
        return _render(request, "views/agent.html")

    @app.get("/views/notes", response_class=HTMLResponse)
    def view_notes(request: Request):
        return _render(request, "views/notes.html")

    @app.get("/views/docs", response_class=HTMLResponse)
    def view_docs(request: Request):
        return _render(request, "views/docs.html")

    return app