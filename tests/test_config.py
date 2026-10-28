"""Тесты для load_config из src.agent.config."""

from __future__ import annotations

import pytest
from pathlib import Path

from src.agent.config import (
    AppConfig,
    LLMConfig,
    PathsConfig,
    SafetyConfig,
    _PROJECT_ROOT,
    load_config,
)


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
logs_dir = "my_logs"

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

        assert result.paths.memory == _PROJECT_ROOT / "my_memory"
        assert result.paths.tools == _PROJECT_ROOT / "my_tools"
        assert result.paths.logs_dir == _PROJECT_ROOT / "my_logs"
        assert result.paths.notes_dir == _PROJECT_ROOT / "data" / "notes"
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

    def test_load_config_from_non_project_cwd(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        """load_config() ищет settings.toml от _PROJECT_ROOT, а не от CWD."""
        import src.agent.config as cfg_module

        fake_root = tmp_path / "fake_project"
        (fake_root / "config").mkdir(parents=True)
        (fake_root / "config" / "settings.toml").write_text(
            '[llm]\nmodel = "fake"\n', encoding="utf-8"
        )

        elsewhere = tmp_path / "elsewhere"
        elsewhere.mkdir()

        monkeypatch.setattr(cfg_module, "_PROJECT_ROOT", fake_root)
        monkeypatch.chdir(elsewhere)

        config = load_config()

        assert config.llm.model == "fake"
        assert config.paths.notes_dir == fake_root / "data" / "notes"
        assert config.paths.logs_dir == fake_root / "logs"

    def test_relative_paths_resolved_from_project_root(
        self, tmp_path: Path
    ) -> None:
        """Относительные пути в TOML резолвятся от _PROJECT_ROOT; абсолютные — как есть."""
        abs_logs = tmp_path / "absolute_logs"
        toml_file = tmp_path / "settings.toml"
        toml_file.write_text(
            f"""\
[llm]
model = "m"

[paths]
notes_dir = "custom/notes"
logs_dir = "{abs_logs.as_posix()}"
""",
            encoding="utf-8",
        )

        result = load_config(toml_file)

        from src.agent.config import _PROJECT_ROOT

        assert result.paths.notes_dir == _PROJECT_ROOT / "custom" / "notes"
        assert result.paths.logs_dir == abs_logs