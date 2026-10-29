"""Orchestrator — цикл plan-execute для агента."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path

from src.agent.llm import LLMClient
from src.agent.registry import ToolRegistry

SYSTEM_PROMPT = (
    "Ты — локальный ассистент с инструментами. "
    "Вызывай инструмент только если это необходимо для достижения цели. "
    "После успешного выполнения инструмента проверь, достигнута ли цель. "
    "Если да — дай финальный ответ обычным текстом, БЕЗ вызова инструментов. "
    "НИКОГДА не вызывай один и тот же инструмент с одинаковыми аргументами дважды: "
    "если инструмент уже вернул результат, используй его и двигайся дальше.\n\n"
    "Инструменты:\n"
    "- search_documents — поиск в документах пользователя (README, статьи, файлы проекта).\n"
    "- search_notes — поиск в ЛИЧНЫХ заметках пользователя (data/notes/).\n"
    "- read_notes — список заметок по названию.\n"
    "- save_note — сохранить заметку.\n\n"
    "ВАЖНО: почти любой вопрос про проект, агент, README, установку, "
    "требования, возможности, статьи, код, лицензию — это вопрос про документы. "
    "ВСЕГДА используй search_documents, даже если вопрос выглядит как общий "
    "(\"какая версия Python?\", \"как установить?\", \"что умеет?\").\n\n"
    "Примеры (это образец мышления, а не формат ответа):\n"
    "- «Какие требования к ОЗУ?» → search_documents(query=\"требования оперативная память\")\n"
    "- «Какая версия Python нужна?» → search_documents(query=\"версия Python\")\n"
    "- «Как установить агента?» → search_documents(query=\"установка\")\n"
    "- «Как запустить агента?» → search_documents(query=\"запуск run_agent\")\n"
    "- «Что умеет проект?» → search_documents(query=\"возможности что умеет\")\n"
    "- «О чём статья про PHP?» → search_documents(query=\"статья PHP\")\n"
    "- «Какая лицензия у проекта?» → search_documents(query=\"лицензия\")\n"
    "- «Что в моих заметках про X?» → search_notes(query=\"X\")\n"
    "- «Сохрани заметку X с текстом Y» → save_note(title=\"X\", content=\"Y\")\n"
    "- «Привет» → final(\"Привет! Чем помочь?\") — без инструментов\n\n"
    "После search_documents: посмотри на возвращённые фрагменты и ответь "
    "ТОЛЬКО по ним. Если в фрагментах нет прямого ответа — честно скажи "
    "«в документах это не указано». Не выдумывай факты и цифры."
)

MAX_TOOL_FAILURES = 2


def _summarize_for_log(result: object) -> str:
    """Краткое описание результата инструмента для лога.

    Не логирует содержимое списков (preview/snippet), чтобы в лог
    не попадали тексты заметок. Для ``Path`` оставляет путь —
    это не текст заметки, а адрес файла, полезен для отладки.
    """
    if isinstance(result, Path):
        return str(result)
    if isinstance(result, str) and len(result) <= 200:
        return result
    if isinstance(result, list):
        return f"list[{len(result)}]"
    return f"{type(result).__name__}, len={len(str(result))}"


class MaxStepsExceeded(Exception):
    pass


@dataclass
class OrchestratorResult:
    success: bool
    final_answer: str | None
    steps_used: int
    error: str | None = None
    tool_results: list[str] = field(default_factory=list)


class Orchestrator:
    def __init__(
        self,
        llm: LLMClient,
        registry: ToolRegistry,
        logger: logging.Logger,
        max_steps: int = 10,
        tool_context: dict[str, dict] | None = None,
        max_tool_failures: int = MAX_TOOL_FAILURES,
    ) -> None:
        self.llm = llm
        self.registry = registry
        self.logger = logger
        self.max_steps = max_steps
        self.tool_context = tool_context or {}
        self.max_tool_failures = max_tool_failures

    def run(self, goal: str) -> OrchestratorResult:
        messages: list[dict] = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": goal},
        ]
        tool_results: list[str] = []
        executed_calls: set[str] = set()
        failed_calls: dict[str, int] = {}

        for step in range(1, self.max_steps + 1):
            response = self.llm.chat(messages)
            self.logger.info("step=%d type=%s", step, response.type)

            if response.type == "final":
                self.logger.info("final: %s", response.content)
                return OrchestratorResult(
                    success=True,
                    final_answer=response.content,
                    steps_used=step,
                    tool_results=tool_results,
                )

            elif response.type == "tool_call":
                extra = self.tool_context.get(response.tool_name, {})
                arguments = {
                    **(response.tool_arguments or {}),
                    **extra,
                }
                call_key = f"{response.tool_name}:{sorted((k, str(v)) for k, v in arguments.items())}"

                if call_key in executed_calls:
                    tool_status = "SKIPPED"
                    result = (
                        "was not executed again because the same call already succeeded"
                    )
                    self.logger.info("repeated tool call skipped: %s", call_key)
                elif failed_calls.get(call_key, 0) >= self.max_tool_failures:
                    tool_status = "ERROR"
                    result = (
                        f"failed {self.max_tool_failures} times in a row, giving up. "
                        f"Do NOT call it again."
                    )
                    self.logger.info(
                        "tool %s giving up after %d failures: %s",
                        response.tool_name,
                        self.max_tool_failures,
                        call_key,
                    )
                else:
                    try:
                        result = self.registry.call(response.tool_name, **arguments)
                        tool_status = "SUCCESS"
                        executed_calls.add(call_key)
                    except Exception as exc:
                        tool_status = "ERROR"
                        failed_calls[call_key] = failed_calls.get(call_key, 0) + 1
                        result = f"ERROR: {exc}"
                        self.logger.exception(
                            "tool %s failed (attempt %d)",
                            response.tool_name,
                            failed_calls[call_key],
                        )
                    else:
                        tool_results.append(str(result))
                        self.logger.info(
                            "tool %s -> %s",
                            response.tool_name,
                            _summarize_for_log(result),
                        )

                display_args = response.tool_arguments or {}
                messages.append(
                    {
                        "role": "assistant",
                        "content": (f"tool_call: {response.tool_name}({display_args})"),
                    }
                )

                if tool_status == "SKIPPED":
                    content = (
                        f"tool_result: SKIPPED. {response.tool_name} {result}. "
                        f"Respond with a final answer now."
                    )
                else:
                    content = (
                        f"tool_result: {tool_status}. {response.tool_name} returned: "
                        f"{result}. If this satisfies the user's goal, "
                        f"respond with a final answer now."
                    )

                messages.append({"role": "user", "content": content})

            else:
                self.logger.warning(
                    "unknown response type: %r at step %d",
                    response.type,
                    step,
                )
                return OrchestratorResult(
                    success=False,
                    final_answer=None,
                    steps_used=step,
                    error=f"unknown response type: {response.type!r}",
                    tool_results=tool_results,
                )

        raise MaxStepsExceeded(f"Достигнут лимит шагов: {self.max_steps}")