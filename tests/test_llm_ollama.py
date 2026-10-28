"""Tests for OllamaLLM client."""

import json
import logging
import unittest.mock
import pytest

from src.agent.llm import LLMResponse
from src.agent.llm_ollama import OllamaLLM
from src.agent.registry import ToolDefinition


def _make_mock_response(json_data: dict):
    """Return a MagicMock mimicking requests.Response."""
    mock = unittest.mock.MagicMock()
    mock.json.return_value = json_data
    return mock


class TestOllamaLLMToolCall:
    def test_tool_call_response(self):
        """model returns tool_calls → type == 'tool_call', tool_name, tool_arguments is dict."""
        payload = {
            "choices": [
                {
                    "message": {
                        "role": "assistant",
                        "tool_calls": [
                            {
                                "function": {
                                    "name": "get_weather",
                                    "arguments": json.dumps({"city": "Moscow"}),
                                }
                            }
                        ],
                    }
                }
            ]
        }

        with unittest.mock.patch("src.agent.llm_ollama.requests.post") as mock_post:
            mock_post.return_value = _make_mock_response(payload)

            llm = OllamaLLM()
            response = llm.chat([{"role": "user", "content": "Weather?"}])

        assert response.type == "tool_call"
        assert response.tool_name == "get_weather"
        assert response.tool_arguments == {"city": "Moscow"}
        assert isinstance(response.tool_arguments, dict)


class TestOllamaLLMFinal:
    def test_final_response(self):
        """model returns regular text → type == 'final', content matches."""
        payload = {
            "choices": [
                {
                    "message": {
                        "role": "assistant",
                        "content": "The weather is sunny.",
                    }
                }
            ]
        }

        with unittest.mock.patch("src.agent.llm_ollama.requests.post") as mock_post:
            mock_post.return_value = _make_mock_response(payload)

            llm = OllamaLLM()
            response = llm.chat([{"role": "user", "content": "Weather?"}])

        assert response.type == "final"
        assert response.content == "The weather is sunny."


class TestOllamaLLMHTTPError:
    def test_http_error_raises_runtime_error(self):
        """HTTP error (raise_for_status raises requests.HTTPError) → RuntimeError."""
        import requests as req

        with unittest.mock.patch("src.agent.llm_ollama.requests.post") as mock_post:
            mock_resp = unittest.mock.MagicMock()
            mock_resp.raise_for_status.side_effect = req.HTTPError("404 Client Error")
            mock_post.return_value = mock_resp

            llm = OllamaLLM()

            with pytest.raises(RuntimeError):
                llm.chat([{"role": "user", "content": "Weather?"}])


class TestOllamaLLMWithTools:
    def test_tools_in_payload(self):
        """tools passed → payload has tools in correct format, tool_choice == 'auto'."""
        payload = {"choices": [{"message": {"role": "assistant", "content": "ok"}}]}

        tool_def = ToolDefinition(
            name="search",
            description="Search the web",
            parameters={"type": "object", "properties": {"query": {"type": "string"}}},
            func=lambda query: "",
        )

        with unittest.mock.patch("src.agent.llm_ollama.requests.post") as mock_post:
            mock_post.return_value = _make_mock_response(payload)

            llm = OllamaLLM(tools=[tool_def])
            llm.chat([{"role": "user", "content": "Search something"}])

            # Check the call arguments
            call_kwargs = mock_post.call_args
            sent_payload = call_kwargs.kwargs["json"]

            assert "tools" in sent_payload
            assert sent_payload["tool_choice"] == "auto"
            assert sent_payload["tools"] == [
                {
                    "type": "function",
                    "function": {
                        "name": "search",
                        "description": "Search the web",
                        "parameters": {
                            "type": "object",
                            "properties": {"query": {"type": "string"}},
                        },
                    },
                }
            ]

    def test_no_tools_in_payload(self):
        """tools not passed → payload has no 'tools' key."""
        payload = {"choices": [{"message": {"role": "assistant", "content": "ok"}}]}

        with unittest.mock.patch("src.agent.llm_ollama.requests.post") as mock_post:
            mock_post.return_value = _make_mock_response(payload)

            llm = OllamaLLM()
            llm.chat([{"role": "user", "content": "Hello"}])

            call_kwargs = mock_post.call_args
            sent_payload = call_kwargs.kwargs["json"]

            assert "tools" not in sent_payload


class TestOllamaLLMMalformedResponse:
    def test_invalid_json_in_arguments_raises(self):
        """arguments — невалидный JSON → RuntimeError, не JSONDecodeError."""
        payload = {
            "choices": [
                {
                    "message": {
                        "role": "assistant",
                        "tool_calls": [
                            {
                                "function": {
                                    "name": "save_note",
                                    "arguments": "{not valid json",
                                }
                            }
                        ],
                    }
                }
            ]
        }

        with unittest.mock.patch("src.agent.llm_ollama.requests.post") as mock_post:
            mock_post.return_value = _make_mock_response(payload)

            with pytest.raises(RuntimeError, match="invalid JSON arguments"):
                OllamaLLM().chat([{"role": "user", "content": "x"}])

    def test_empty_choices_raises(self):
        """choices == [] → RuntimeError."""
        payload = {"choices": []}

        with unittest.mock.patch("src.agent.llm_ollama.requests.post") as mock_post:
            mock_post.return_value = _make_mock_response(payload)

            with pytest.raises(RuntimeError, match="no choices"):
                OllamaLLM().chat([{"role": "user", "content": "x"}])

    def test_missing_message_raises(self):
        """choices[0] без message → RuntimeError."""
        payload = {"choices": [{"foo": "bar"}]}

        with unittest.mock.patch("src.agent.llm_ollama.requests.post") as mock_post:
            mock_post.return_value = _make_mock_response(payload)

            with pytest.raises(RuntimeError, match="no message"):
                OllamaLLM().chat([{"role": "user", "content": "x"}])

    def test_invalid_response_json_raises(self):
        """resp.json() падает → RuntimeError, не ValueError."""
        with unittest.mock.patch("src.agent.llm_ollama.requests.post") as mock_post:
            mock_resp = unittest.mock.MagicMock()
            mock_resp.raise_for_status.return_value = None
            mock_resp.json.side_effect = ValueError("not json")
            mock_post.return_value = mock_resp

            with pytest.raises(RuntimeError, match="invalid JSON"):
                OllamaLLM().chat([{"role": "user", "content": "x"}])

    def test_multiple_tool_calls_uses_first(self, caplog):
        """Несколько tool_calls → берётся первый, в логе warning."""
        payload = {
            "choices": [
                {
                    "message": {
                        "role": "assistant",
                        "tool_calls": [
                            {
                                "function": {
                                    "name": "first",
                                    "arguments": json.dumps({"a": 1}),
                                }
                            },
                            {
                                "function": {
                                    "name": "second",
                                    "arguments": json.dumps({"b": 2}),
                                }
                            },
                        ],
                    }
                }
            ]
        }

        with unittest.mock.patch("src.agent.llm_ollama.requests.post") as mock_post:
            mock_post.return_value = _make_mock_response(payload)

            with caplog.at_level(logging.WARNING, logger="agent"):
                response = OllamaLLM().chat([{"role": "user", "content": "x"}])

        assert response.tool_name == "first"
        assert response.tool_arguments == {"a": 1}
        assert any(
            "2 tool_calls" in r.message or "tool_calls" in r.message
            for r in caplog.records
        )


class TestOllamaLLMLogging:
    def test_messages_content_not_logged(self, caplog):
        """Полный текст сообщения не попадает в INFO-лог."""
        payload = {"choices": [{"message": {"role": "assistant", "content": "ok"}}]}

        with unittest.mock.patch("src.agent.llm_ollama.requests.post") as mock_post:
            mock_post.return_value = _make_mock_response(payload)

            with caplog.at_level(logging.INFO, logger="agent"):
                OllamaLLM().chat(
                    [{"role": "user", "content": "SECRET_NOTE_TEXT"}]
                )

        assert "SECRET_NOTE_TEXT" not in caplog.text


class TestOllamaLLMTemperatureMaxTokens:
    def _sent_payload(self, **llm_kwargs) -> dict:
        payload = {"choices": [{"message": {"role": "assistant", "content": "ok"}}]}
        with unittest.mock.patch("src.agent.llm_ollama.requests.post") as mock_post:
            mock_post.return_value = _make_mock_response(payload)
            OllamaLLM(**llm_kwargs).chat([{"role": "user", "content": "x"}])
            return mock_post.call_args.kwargs["json"]

    def test_temperature_in_payload(self):
        sent = self._sent_payload(temperature=0.3)
        assert sent["temperature"] == 0.3

    def test_max_tokens_in_payload(self):
        sent = self._sent_payload(max_tokens=1024)
        assert sent["max_tokens"] == 1024

    def test_no_temperature_when_none(self):
        sent = self._sent_payload()
        assert "temperature" not in sent

    def test_no_max_tokens_when_none(self):
        sent = self._sent_payload()
        assert "max_tokens" not in sent
