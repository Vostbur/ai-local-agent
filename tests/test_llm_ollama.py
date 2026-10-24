"""Tests for OllamaLLM client."""

import json
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
