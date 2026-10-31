"""Sub-app для работы с документами. Монтируется в create_app по пути /documents."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import FastAPI, Request, UploadFile, File, HTTPException, Form
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from agent.web.documents import deps

BASE = Path(__file__).parent
templates = Jinja2Templates(directory=BASE / "templates")

def _render(request: Request, name: str, extra: dict, **kw) -> HTMLResponse:
    ctx = {"request": request, **extra}
    return templates.TemplateResponse(request, name, ctx, **kw)

def make_documents_app(config: Any = None, logger: Any = None) -> FastAPI:
    app = FastAPI(title="Documents UI", docs_url=None, redoc_url=None, openapi_url=None)

    @app.get("/", response_class=HTMLResponse)
    def index(request: Request):
        return _render(
            request,
            "index.html",
            {"documents": deps.list_files(config)},
        )

    @app.get("/api/list", response_class=HTMLResponse)
    def list_view(request: Request):
        return _render(
            request,
            "partials/doc_table.html",
            {"documents": deps.list_files(config)},
        )

    @app.post("/api/upload", response_class=HTMLResponse)
    def upload(request: Request, files: list[UploadFile] = File(...)):
        for file in files:
            if file.filename:
                deps.save_uploaded_file(config, file.filename, file.file)
        
        # Автоматическая переиндексация после загрузки
        res = deps.rebuild_index(config, reset=True)
        
        headers = {"HX-Trigger": '{"show-toast": {"message": "Файлы загружены и проиндексированы", "type": "success"}}'}
        if not res["success"]:
            headers = {"HX-Trigger": f'{{"show-toast": {{"message": "Ошибка индексации: {res["error"]}", "type": "error"}}}}'}

        return _render(
            request,
            "partials/doc_table.html",
            {"documents": deps.list_files(config)},
            headers=headers,
        )

    @app.post("/api/reindex", response_class=HTMLResponse)
    def reindex(request: Request):
        res = deps.rebuild_index(config, reset=True)
        headers = {"HX-Trigger": '{"show-toast": {"message": "Индекс пересобран", "type": "success"}}'}
        if not res["success"]:
            headers = {"HX-Trigger": f'{{"show-toast": {{"message": "Ошибка: {res["error"]}", "type": "error"}}}}'}

        return _render(
            request,
            "partials/doc_table.html",
            {"documents": deps.list_files(config)},
            headers=headers,
        )

    @app.delete("/api/{path:path}", response_class=HTMLResponse)
    def delete(request: Request, path: str):
        success = deps.delete_file(config, path)
        if not success:
            raise HTTPException(404, "File not found")
            
        deps.rebuild_index(config, reset=True)
        headers = {"HX-Trigger": '{"show-toast": {"message": "Файл удалён и индекс обновлён", "type": "success"}}'}

        return _render(
            request,
            "partials/doc_table.html",
            {"documents": deps.list_files(config)},
            headers=headers,
        )

    return app