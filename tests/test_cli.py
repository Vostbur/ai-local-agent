"""Tests for the unified CLI (`src/agent/__main__.py`)."""

from unittest.mock import MagicMock, patch

import pytest

from src.agent import __main__ as cli_main


def _invoke(argv, config_error=None):
    """Запустить main(argv) с запатченными load_config и setup_logging."""
    with patch("src.agent.__main__.load_config") as mock_load, \
         patch("src.agent.__main__.setup_logging") as mock_log:
        if config_error is not None:
            mock_load.side_effect = config_error
        else:
            mock_load.return_value = MagicMock()
        mock_log.return_value = "logger"
        cli_main.main(argv)


class TestParseErrors:
    def test_no_command_exits_2(self):
        with pytest.raises(SystemExit) as exc:
            cli_main.main([])
        assert exc.value.code == 2

    def test_unknown_command_exits_2(self):
        with pytest.raises(SystemExit) as exc:
            cli_main.main(["nonexistent"])
        assert exc.value.code == 2


class TestDispatch:
    def test_run_dispatches_to_run_once(self, monkeypatch):
        captured = {}

        def fake(goal, config, logger):
            captured["goal"] = goal
            captured["logger"] = logger

        monkeypatch.setattr("src.agent.cli.run_once", fake)
        _invoke(["run", "hello"])

        assert captured["goal"] == "hello"
        assert captured["logger"] == "logger"

    def test_chat_dispatches_to_interactive_loop(self, monkeypatch):
        captured = {}

        def fake(config, logger):
            captured["called"] = True

        monkeypatch.setattr("src.agent.cli.interactive_loop", fake)
        _invoke(["chat"])

        assert captured.get("called") is True

    def test_index_dispatches_to_build_index_cmd(self, monkeypatch):
        captured = {}

        def fake(**kwargs):
            captured.update(kwargs)

        monkeypatch.setattr("src.agent.cli.build_index_cmd", fake)
        _invoke(["index", "--reset", "--batch-size", "16"])

        assert captured["reset"] is True
        assert captured["batch_size"] == 16
        assert captured["documents"] is None

    def test_search_dispatches_to_search_cmd(self, monkeypatch):
        captured = {}

        def fake(**kwargs):
            captured.update(kwargs)

        monkeypatch.setattr("src.agent.cli.search_cmd", fake)
        _invoke(["search", "OSPF", "--top-k", "3"])

        assert captured["query"] == "OSPF"
        assert captured["top_k"] == 3
        assert captured["truncate"] is True


class TestConfigError:
    def test_missing_config_exits_1(self, capsys):
        with patch(
            "src.agent.__main__.load_config",
            side_effect=FileNotFoundError,
        ):
            with pytest.raises(SystemExit) as exc:
                cli_main.main(["run", "hi"])

        assert exc.value.code == 1
        assert "config/settings.toml" in capsys.readouterr().out