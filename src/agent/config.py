"""Конфигурация агента: датаклассы и загрузчик из TOML."""

from __future__ import annotations

import tomllib
from dataclasses import dataclass
from pathlib import Path


@dataclass
class LLMConfig:
    """Настройки LLM-модели.

    Атрибуты:
        provider: Провайдер LLM (например, "ollama").
        model: Имя модели.
        base_url: URL LLM-сервера.
        temperature: Температура генерации (0.0 – 2.0).
        max_tokens: Максимальное число токенов в ответе.
        max_steps: Максимальное число шагов оркестратора.
    """

    provider: str = "ollama"
    model: str = "qwen2.5-3b-agent"
    base_url: str = "http://localhost:11434"
    temperature: float = 0.7
    max_tokens: int = 4096
    max_steps: int = 10


@dataclass
class PathsConfig:
    """Пути к ресурсам агента.

    Атрибуты:
        data_dir: Корневая директория данных.
        notes_dir: Путь к директории заметок.
        inbox_dir: Путь к входящим.
        photos_dir: Путь к фотографиям.
        logs_dir: Путь к логам.
        memory: Путь к директории памяти.
        tools: Путь к директории инструментов.
        logs: Путь к файлу или директории логов.
    """

    data_dir: Path = Path("data")
    notes_dir: Path = Path("data/notes")
    inbox_dir: Path = Path("data/inbox")
    photos_dir: Path = Path("data/photos")
    logs_dir: Path = Path("logs")
    memory: Path = Path("memory")
    tools: Path = Path("tools")
    logs: Path = Path("logs")


@dataclass
class SafetyConfig:
    """Настройки безопасности.

    Атрибуты:
        confirm_file_operations: Требовать подтверждение операций с файлами.
        max_tool_retries: Максимальное число повторов выполнения инструмента.
        allow_shell: Разрешить выполнение shell-команд.
        allow_network: Разрешить сетевые запросы.
    """

    confirm_file_operations: bool = False
    max_tool_retries: int = 3
    allow_shell: bool = False
    allow_network: bool = False


@dataclass
class AppConfig:
    """Полная конфигурация приложения.

    Атрибуты:
        llm: Настройки LLM-модели.
        paths: Пути к ресурсам.
        safety: Настройки безопасности.
    """

    llm: LLMConfig
    paths: PathsConfig
    safety: SafetyConfig


def load_config(path: Path | None = None) -> AppConfig:
    """Загружает конфигурацию из TOML-файла.

    Если *path* не указан, ищет ``config/settings.toml``
    относительно текущего рабочего каталога.

    Args:
        path: Путь к TOML-файлу конфигурации.

    Returns:
        Расширенный объект AppConfig.

    Raises:
        FileNotFoundError: Если файл конфигурации не найден.
        ValueError: Если в файле отсутствует обязательная секция ``[llm]``.
    """
    if path is None:
        path = Path("config", "settings.toml")

    with path.open("rb") as fh:
        raw = tomllib.load(fh)

    if "llm" not in raw:
        raise ValueError(
            f"Файл {path} не содержит обязательную секцию [llm]"
        )

    llm_raw = raw["llm"]
    llm = LLMConfig(
        provider=llm_raw.get("provider", "ollama"),
        model=llm_raw["model"],
        base_url=llm_raw.get("base_url", "http://localhost:11434"),
        temperature=llm_raw.get("temperature", 0.7),
        max_tokens=llm_raw.get("max_tokens", 4096),
        max_steps=llm_raw.get("max_steps", 10),
    )

    paths_raw = raw.get("paths", {})
    paths = PathsConfig(
        data_dir=Path(paths_raw.get("data_dir", "data")),
        notes_dir=Path(paths_raw.get("notes_dir", "data/notes")),
        inbox_dir=Path(paths_raw.get("inbox_dir", "data/inbox")),
        photos_dir=Path(paths_raw.get("photos_dir", "data/photos")),
        logs_dir=Path(paths_raw.get("logs_dir", "logs")),
        memory=Path(paths_raw.get("memory", "memory")),
        tools=Path(paths_raw.get("tools", "tools")),
        logs=Path(paths_raw.get("logs", "logs")),
    )

    safety_raw = raw.get("safety", {})
    safety = SafetyConfig(
        confirm_file_operations=safety_raw.get(
            "confirm_file_operations", False
        ),
        max_tool_retries=safety_raw.get("max_tool_retries", 3),
        allow_shell=safety_raw.get("allow_shell", False),
        allow_network=safety_raw.get("allow_network", False),
    )

    return AppConfig(llm=llm, paths=paths, safety=safety)