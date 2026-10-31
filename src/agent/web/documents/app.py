"""Sub-app для работы с документами. Монтируется в create_app по пути /documents."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Request, UploadFile, File, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from agent.web.documents import deps

BASE = Path(__file__).parent
templates = Jinja2Templates(directory=BASE / "templates")


def _render(request: Request, name: str, extra: dict, **kw) -> HTMLResponse:
    ctx = {"request": request, **extra}
    return templates.TemplateResponse(request, name, ctx, **kw)


def _toast_header(message: str, type_: str = "success") -> dict:
    """HTTP-заголовки должны быть ASCII, поэтому экранируем кириллицу в JSON."""
    payload = json.dumps({"show-toast": {"message": message, "type": type_}}, ensure_ascii=True)
    return {"HX-Trigger": payload}


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
        
        res = deps.rebuild_index(config, reset=True)
        
        if res["success"]:
            headers = _toast_header("Файлы загружены и проиндексированы", "success")
        else:
            headers = _toast_header(f"Ошибка индексации: {res['error']}", "error")

        return _render(
            request,
            "partials/doc_table.html",
            {"documents": deps.list_files(config)},
            headers=headers,
        )

    @app.post("/api/reindex", response_class=HTMLResponse)
    def reindex(request: Request):
        res = deps.rebuild_index(config, reset=True)
        if res["success"]:
            headers = _toast_header("Индекс пересобран", "success")
        else:
            headers = _toast_header(f"Ошибка: {res['error']}", "error")

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
        headers = _toast_header("Файл удалён и индекс обновлён", "success")

        return _render(
            request,
            "partials/doc_table.html",
            {"documents": deps.list_files(config)},
            headers=headers,
        )

    return app