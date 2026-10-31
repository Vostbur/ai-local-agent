"""Sub-app для работы с заметками. Монтируется в create_app по пути /notes."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

from fastapi import FastAPI, Form, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from agent.web.notes import deps

BASE = Path(__file__).parent
templates = Jinja2Templates(directory=BASE / "templates")

_CATEGORY_PALETTE = [
    ("#fee2e2", "#b91c1c", "#7f1d1d"),
    ("#ffedd5", "#c2410c", "#7c2d12"),
    ("#fef3c7", "#b45309", "#78350f"),
    ("#dcfce7", "#15803d", "#14532d"),
    ("#ccfbf1", "#0f766e", "#134e4a"),
    ("#e0f2fe", "#0369a1", "#0c4a6e"),
    ("#e0e7ff", "#4338ca", "#312e81"),
    ("#ede9fe", "#6d28d9", "#4c1d95"),
    ("#fce7f3", "#be185d", "#831843"),
]


def category_color(name: str | None) -> dict:
    if not name:
        return {"bg": "#f5f5f4", "fg": "#57534e", "border": "#e7e5e4"}
    h = sum(ord(c) for c in name) % len(_CATEGORY_PALETTE)
    bg, fg, border = _CATEGORY_PALETTE[h]
    return {"bg": bg, "fg": fg, "border": border}


def _render(request: Request, name: str, extra: dict, **kw) -> HTMLResponse:
    ctx = {"request": request, "category_color": category_color, **extra}
    # ВАЖНО: новый синтаксис Starlette — request первым аргументом
    return templates.TemplateResponse(request, name, ctx, **kw)


def _grid_response(request: Request, notes: list[dict], headers: dict | None = None) -> HTMLResponse:
    return _render(
        request,
        "partials/notes_grid.html",
        {"notes": notes, "active_category": None, "query": ""},
        headers=headers or {},
    )


def make_notes_app(config: Any = None, logger: Any = None) -> FastAPI:
    """Фабрика sub-app. `logger` принимается для совместимости с create_app."""
    app = FastAPI(title="Notes UI", docs_url=None, redoc_url=None, openapi_url=None)
    app.mount("/static", StaticFiles(directory=BASE / "static"), name="notes-static")

    # --- главная страница ---
    @app.get("/", response_class=HTMLResponse)
    def index(request: Request):
        return _render(
            request,
            "index.html",
            {
                "notes": deps.fetch_notes(config, None, None),
                "categories": deps.all_categories(config),
                "active_category": None,
                "query": "",
            },
        )

    # --- партиал: список заметок ---
    @app.get("/api/notes", response_class=HTMLResponse)
    def list_view(request: Request, category: Optional[str] = None, q: Optional[str] = None):
        notes = deps.fetch_notes(config, category or None, q or None)
        return _render(
            request,
            "partials/notes_grid.html",
            {"notes": notes, "active_category": category, "query": q or ""},
        )

    # --- партиал: сайдбар с категориями ---
    @app.get("/api/notes/sidebar", response_class=HTMLResponse)
    def sidebar_view(request: Request, category: Optional[str] = None):
        return _render(
            request,
            "partials/sidebar.html",
            {"categories": deps.all_categories(config), "active_category": category},
        )

    # --- партиал: форма (создание или редактирование) ---
    @app.get("/api/notes/form", response_class=HTMLResponse)
    def form_view(request: Request, path: Optional[str] = None):
        note = None
        if path:
            note = deps.find_one(config, path)
            if note is None:
                raise HTTPException(404, "Note not found")
            # подгружаем ПОЛНОЕ тело заметки с диска для textarea
            note["body"] = deps.read_body(config, path)
        cats = [c["name"] for c in deps.all_categories(config)]
        return _render(
            request,
            "partials/note_form.html",
            {"note": note, "categories": cats},
        )

    # --- создание ---
    @app.post("/api/notes", response_class=HTMLResponse)
    def create(
        request: Request,
        title: str = Form(...),
        content: str = Form(""),
        category: str = Form(""),
    ):
        deps.save_note(
            title=title.strip(),
            content=content,
            notes_dir=deps.notes_dir(config),
            category=(category.strip() or None),
        )
        return _grid_response(
            request,
            deps.fetch_notes(config, None, None),
            headers={"HX-Trigger": '{"note-saved": {}}'},
        )

    # --- обновление (query: path, form: title/content/category) ---
    @app.put("/api/notes", response_class=HTMLResponse)
    def update(
        request: Request,
        path: str,
        title: str = Form(...),
        content: str = Form(""),
        category: str = Form(""),
    ):
        nd = deps.notes_dir(config)
        current = deps.find_one(config, path)
        if current is None:
            raise HTTPException(404, "Note not found")

        deps.update_note(path=path, notes_dir=nd, title=title.strip(), content=content)

        new_cat = category.strip() or None
        if current.get("category") != new_cat:
            deps.move_note(path=path, category=new_cat, notes_dir=nd)

        return _grid_response(
            request,
            deps.fetch_notes(config, None, None),
            headers={"HX-Trigger": '{"note-saved": {}}'},
        )

    # --- удаление ---
    @app.delete("/api/notes", response_class=HTMLResponse)
    def delete(request: Request, path: str):
        deps.delete_note(
            path=path,
            notes_dir=deps.notes_dir(config),
            trash_dir=deps.trash_dir(config),
        )
        return _grid_response(
            request,
            deps.fetch_notes(config, None, None),
            headers={"HX-Trigger": '{"note-deleted": {}}'},
        )

    return app