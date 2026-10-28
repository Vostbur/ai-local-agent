"""Orchestrator — цикл plan-execute для агента."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from src.agent.llm import LLMClient
from src.agent.registry import ToolRegistry

SYSTEM_PROMPT = (
    "Ты — локальный ассистент с инструментами. "
    "Вызывай инструмент только если это необходимо для достижения цели. "
    "После успешного выполнения инструмента проверь, достигнута ли цель. "
    "Если да — дай финальный ответ обычным текстом, БЕЗ вызова инструментов. "
    "НИКОГДА не вызывай один и тот же инструмент с одинаковыми аргументами дважды: "
    "если инструмент уже вернул результат, используй его и двигайся дальше. "
    "Правило выбора инструмента: "
    "если пользователь спрашивает про заметку по НАЗВАНИЮ или ЗАГОЛОВКУ — используй read_notes. "
    "Если про СОДЕРЖИМОЕ или текст внутри заметок — используй search_notes."
)


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
    ) -> None:
        self.llm = llm
        self.registry = registry
        self.logger = logger
        self.max_steps = max_steps
        self.tool_context = tool_context or {}

    def run(self, goal: str) -> OrchestratorResult:
        messages: list[dict] = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": goal},
        ]
        tool_results: list[str] = []
        executed_calls: set[str] = set()

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

            if response.type == "tool_call":
                extra = self.tool_context.get(response.tool_name, {})
                arguments = {
                    **(response.tool_arguments or {}),
                    **extra,
                }
                call_key = f"{response.tool_name}:{sorted((k, str(v)) for k, v in arguments.items())}"

                if call_key in executed_calls:
                    tool_status = "SKIPPED"
                    result = "was not executed again because the same call already succeeded"
                    self.logger.info("repeated tool call skipped: %s", call_key)
                else:
                    try:
                        result = self.registry.call(
                            response.tool_name, **arguments
                        )
                        tool_status = "SUCCESS"
                        executed_calls.add(call_key)
                    except Exception as exc:
                        tool_status = "ERROR"
                        result = f"ERROR: {exc}"
                        self.logger.exception(
                            "tool %s failed", response.tool_name
                        )
                    else:
                        tool_results.append(str(result))
                        self.logger.info(
                            "tool %s -> %s", response.tool_name, result
                        )

                messages.append(
                    {
                        "role": "assistant",
                        "content": (
                            f"tool_call: {response.tool_name}({arguments})"
                        ),
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

        raise MaxStepsExceeded(
            f"Достигнут лимит шагов: {self.max_steps}"
        )
