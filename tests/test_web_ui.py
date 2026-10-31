import pytest
from unittest.mock import MagicMock
from fastapi import FastAPI
from fastapi.testclient import TestClient
from agent.web.notes.app import make_notes_app
from agent.web.documents.app import make_documents_app
from agent.config import AppConfig, PathsConfig


@pytest.fixture
def test_config(tmp_path):
    paths = PathsConfig(
        notes_dir=tmp_path / "notes",
        documents_dir=tmp_path / "documents",
        trash_dir=tmp_path / "trash",
        index_dir=tmp_path / "index",
    )
    # Передаем заглушки для обязательных полей
    return AppConfig(
        paths=paths,
        llm=MagicMock(),
        safety=MagicMock(),
        rag=MagicMock()
    )

@pytest.fixture
def notes_client(test_config):
    app = FastAPI()
    app.mount("/notes", make_notes_app(test_config))
    return TestClient(app)

@pytest.fixture
def docs_client(test_config):
    app = FastAPI()
    app.mount("/documents", make_documents_app(test_config))
    return TestClient(app)


class TestNotesUI:
    def test_index_renders(self, notes_client):
        res = notes_client.get("/notes/")
        assert res.status_code == 200
        assert "Заметки" in res.text

    def test_create_and_delete_note(self, notes_client):
        # Создаем
        res = notes_client.post("/notes/api/notes", data={
            "title": "Тестовая заметка",
            "content": "Содержимое",
            "category": "тест"
        })
        assert res.status_code == 200
        assert "Тестовая заметка" in res.text
        assert "note-saved" in res.headers.get("HX-Trigger", "")

        # Проверяем, что появилась в списке
        res = notes_client.get("/notes/api/notes")
        assert "Тестовая заметка" in res.text

        # Удаляем
        res = notes_client.delete("/notes/api/notes?path=тест/тестовая_заметка.md")
        assert res.status_code == 200
        assert "Тестовая заметка" not in res.text


class TestDocumentsUI:
    def test_index_renders_empty(self, docs_client):
        res = docs_client.get("/documents/")
        assert res.status_code == 200
        assert "Нет документов" in res.text

    def test_upload_and_delete_document(self, docs_client):
        # Загрузка файла (в multipart)
        file_content = b"Test document content"
        res = docs_client.post(
            "/documents/api/upload",
            files={"files": ("test.txt", file_content, "text/plain")}
        )
        assert res.status_code == 200
        assert "test.txt" in res.text
        
        # Удаление
        res = docs_client.delete("/documents/api/test.txt")
        assert res.status_code == 200
        assert "test.txt" not in res.text