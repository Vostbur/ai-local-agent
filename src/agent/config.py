"""Конфигурация агента: датаклассы и загрузчик из TOML."""

from __future__ import annotations

import tomllib
from dataclasses import dataclass
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _resolve_path(value: str | Path) -> Path:
    """Абсолютный путь или путь относительно корня проекта."""
    path = Path(value)
    return path if path.is_absolute() else _PROJECT_ROOT / path


@dataclass
class LLMConfig:
    """Настройки LLM-модели.

    Атрибуты:
        model: Имя модели.
        base_url: URL LLM-сервера.
        temperature: Температура генерации (0.0 – 2.0).
        max_tokens: Максимальное число токенов в ответе.
        max_steps: Максимальное число шагов оркестратора.
    """

    model: str = "qwen2.5-3b-agent"
    base_url: str = "http://localhost:11434"
    temperature: float | None = None
    max_tokens: int | None = None
    max_steps: int = 10


@dataclass
class RAGConfig:
    """Настройки RAG-поиска.

    Атрибуты:
        embedding_model: Имя модели эмбеддингов.
        chunk_size: Размер чанка при разбиении документов.
        chunk_overlap: Перекрытие между чанками.
        top_k: Число ближайших векторов при поиске.
    """

    embedding_model: str = "paraphrase-multilingual-mpnet-base-v2"
    chunk_size: int = 400
    chunk_overlap: int = 100
    top_k: int = 5


@dataclass
class PathsConfig:
    """Пути к ресурсам агента.

    Атрибуты:
        data_dir: Корневая директория данных.
        notes_dir: Путь к директории заметок.
        trash_dir: Путь к директории корзины (для удалённых заметок/документов).
        inbox_dir: Путь к входящим.
        photos_dir: Путь к фотографиям.
        documents_dir: Корпус документов для RAG (Markdown, TXT, позже PDF/DOCX).
        logs_dir: Путь к директории логов.
        memory: Путь к директории памяти.
        tools: Путь к директории инструментов.
        index_dir: Директория векторного индекса RAG.
        generated_dir: Директория для документов, созданных агентом по шаблону.
    """

    data_dir: Path = Path("data")
    notes_dir: Path = Path("data/notes")
    trash_dir: Path = Path("data/trash")
    inbox_dir: Path = Path("data/inbox")
    photos_dir: Path = Path("data/photos")
    documents_dir: Path = Path("data/documents")
    logs_dir: Path = Path("logs")
    memory: Path = Path("memory")
    tools: Path = Path("tools")
    index_dir: Path = Path("data/index")
    generated_dir: Path = Path("data/generated")


@dataclass
class SafetyConfig:
    """Настройки безопасности.

    Атрибуты:
        confirm_file_operations: Требовать подтверждение операций с файлами.
            Читается из TOML; логика подтверждения появится в шаге 8 (`move_file`).
        max_tool_retries: Максимальное число повторов падающего вызова
            инструмента перед тем, как оркестратор сдастся.
    """

    confirm_file_operations: bool = False
    max_tool_retries: int = 2


@dataclass
class AppConfig:
    """Полная конфигурация приложения.

    Атрибуты:
        llm: Настройки LLM-модели.
        paths: Пути к ресурсам.
        safety: Настройки безопасности.
        rag: Настройки RAG-поиска.
    """

    llm: LLMConfig
    paths: PathsConfig
    safety: SafetyConfig
    rag: RAGConfig


def load_config(path: Path | None = None) -> AppConfig:
    """Загружает конфигурацию из TOML-файла.

    Если *path* не указан, ищет ``config/settings.toml`` в корне проекта
    (независимо от текущего рабочего каталога). Относительные пути в
    секции ``[paths]`` резолвятся от корня проекта, а не от CWD.

    Args:
        path: Путь к TOML-файлу конфигурации.

    Returns:
        Расширенный объект AppConfig.

    Raises:
        FileNotFoundError: Если файл конфигурации не найден.
        ValueError: Если в файле отсутствует обязательная секция ``[llm]``.
    """
    if path is None:
        path = _PROJECT_ROOT / "config" / "settings.toml"

    with path.open("rb") as fh:
        raw = tomllib.load(fh)

    if "llm" not in raw:
        raise ValueError(f"Файл {path} не содержит обязательную секцию [llm]")

    llm_raw = raw["llm"]
    llm = LLMConfig(
        model=llm_raw["model"],
        base_url=llm_raw.get("base_url", "http://localhost:11434"),
        temperature=llm_raw.get("temperature"),
        max_tokens=llm_raw.get("max_tokens"),
        max_steps=llm_raw.get("max_steps", 10),
    )

    paths_raw = raw.get("paths", {})
    paths = PathsConfig(
        data_dir=_resolve_path(paths_raw.get("data_dir", "data")),
        notes_dir=_resolve_path(paths_raw.get("notes_dir", "data/notes")),
        trash_dir=_resolve_path(paths_raw.get("trash_dir", "data/trash")),
        inbox_dir=_resolve_path(paths_raw.get("inbox_dir", "data/inbox")),
        photos_dir=_resolve_path(paths_raw.get("photos_dir", "data/photos")),
        documents_dir=_resolve_path(paths_raw.get("documents_dir", "data/documents")),
        logs_dir=_resolve_path(paths_raw.get("logs_dir", "logs")),
        memory=_resolve_path(paths_raw.get("memory", "memory")),
        tools=_resolve_path(paths_raw.get("tools", "tools")),
        index_dir=_resolve_path(paths_raw.get("index_dir", "data/index")),
        generated_dir=_resolve_path(paths_raw.get("generated_dir", "data/generated")),
    )

    safety_raw = raw.get("safety", {})
    safety = SafetyConfig(
        confirm_file_operations=safety_raw.get("confirm_file_operations", False),
        max_tool_retries=safety_raw.get("max_tool_retries", 2),
    )

    rag_raw = raw.get("rag", {})
    rag_defaults = RAGConfig()
    rag = RAGConfig(
        embedding_model=rag_raw.get("embedding_model", rag_defaults.embedding_model),
        chunk_size=rag_raw.get("chunk_size", rag_defaults.chunk_size),
        chunk_overlap=rag_raw.get("chunk_overlap", rag_defaults.chunk_overlap),
        top_k=rag_raw.get("top_k", rag_defaults.top_k),
    )

    return AppConfig(llm=llm, paths=paths, safety=safety, rag=rag)
