"""Тесты для load_config из src.agent.config."""

from __future__ import annotations

import pytest
from pathlib import Path

from src.agent.config import AppConfig, LLMConfig, PathsConfig, SafetyConfig, load_config


class TestLoadConfig:
    """Проверки функции load_config."""

    def test_success(self, tmp_path: Path) -> None:
        """Успешная загрузка из существующего файла."""
        toml_file = tmp_path / "settings.toml"
        toml_file.write_text(
            """\
[llm]
model = "gpt-4"
temperature = 0.5
max_tokens = 2048

[paths]
memory = "my_memory"
tools = "my_tools"
logs = "my_logs"

[safety]
max_tool_retries = 5
allow_shell = true
allow_network = true
""",
            encoding="utf-8",
        )

        result = load_config(toml_file)

        assert isinstance(result, AppConfig)
        assert result.llm == LLMConfig(model="gpt-4", temperature=0.5, max_tokens=2048)
        assert result.paths == PathsConfig(
            memory=Path("my_memory"),
            tools=Path("my_tools"),
            logs=Path("my_logs"),
        )
        assert result.safety == SafetyConfig(
            max_tool_retries=5,
            allow_shell=True,
            allow_network=True,
        )

    def test_file_not_found(self, tmp_path: Path) -> None:
        """FileNotFoundError при отсутствии файла."""
        missing = tmp_path / "nonexistent.toml"

        with pytest.raises(FileNotFoundError):
            load_config(missing)

    def test_missing_llm_section(self, tmp_path: Path) -> None:
        """ValueError при отсутствии секции [llm]."""
        toml_file = tmp_path / "settings.toml"
        toml_file.write_text(
            """\
[paths]
memory = "mem"

[safety]
allow_shell = false
""",
            encoding="utf-8",
        )

        with pytest.raises(ValueError, match="не содержит обязательную секцию \\[llm\\]"):
            load_config(toml_file)
