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

    def test_reads_all_llm_fields_from_toml(self, tmp_path: Path) -> None:
        """Все поля [llm] из TOML попадают в LLMConfig."""
        toml_file = tmp_path / "settings.toml"
        toml_file.write_text(
            """\
[llm]
provider = "llamacpp"
model = "custom-model"
base_url = "http://custom:8080"
max_steps = 5
temperature = 0.3
max_tokens = 1024
""",
            encoding="utf-8",
        )

        result = load_config(toml_file)

        assert result.llm.provider == "llamacpp"
        assert result.llm.model == "custom-model"
        assert result.llm.base_url == "http://custom:8080"
        assert result.llm.max_steps == 5
        assert result.llm.temperature == 0.3
        assert result.llm.max_tokens == 1024

    def test_reads_confirm_file_operations_from_toml(
        self, tmp_path: Path
    ) -> None:
        """Поле confirm_file_operations читается из [safety]."""
        toml_file = tmp_path / "settings.toml"
        toml_file.write_text(
            """\
[llm]
model = "m"

[safety]
confirm_file_operations = true
""",
            encoding="utf-8",
        )

        result = load_config(toml_file)

        assert result.safety.confirm_file_operations is True

    def test_confirm_file_operations_default_false(
        self, tmp_path: Path
    ) -> None:
        """Если в TOML нет поля — confirm_file_operations = False."""
        toml_file = tmp_path / "settings.toml"
        toml_file.write_text(
            """\
[llm]
model = "m"
""",
            encoding="utf-8",
        )

        result = load_config(toml_file)

        assert result.safety.confirm_file_operations is False
