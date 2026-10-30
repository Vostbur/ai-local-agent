"""Orchestrator — цикл plan-execute для агента."""

from __future__ import annotations

import logging
from collections.abc import Callable
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
    "- list_notes — список заметок: все или по категории.\n"
    "- save_note — сохранить заметку (опционально в категорию).\n"
    "- update_note — изменить заголовок и/или текст существующей заметки.\n"
    "- delete_note — удалить заметку (перемещает в корзину, не стирает безвозвратно).\n"
    "- move_note — переместить заметку в другую категорию или в корень.\n"
    "- list_categories — список категорий заметок и число заметок в каждой.\n\n"
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
    "«в документах это не указано». Не выдумывай факты и цифры.\n\n"
    "Инструменты работы с документами:\n"
    "- read_document(path) — прочитать шаблон или документ целиком (или первые N символов).\n"
    "- write_document(title, content) — создать новый Markdown-документ.\n\n"
    "Изменение заметок (ОБЯЗАТЕЛЬНО):\n"
    "Заметки у каждого пользователя свои, и ты НЕ знаешь их пути наперёд. "
    "update_note, delete_note и move_note принимают аргумент 'path' — ПУТЬ к файлу "
    "заметки относительно data/notes/ (формат: 'категория/имя_файла'), "
    "а НЕ название заметки. НЕ угадывай путь по названию.\n"
    "Если у тебя ещё нет пути к заметке из результата инструмента в текущем диалоге — "
    "сначала вызови list_notes или read_notes, найди нужную заметку и возьми её путь "
    "из результата, и только потом вызывай update_note, delete_note или move_note.\n\n"
    "Выбор инструмента для заметок (ОБЯЗАТЕЛЬНО):\n"
    "ЗАГОЛОВОК или НАЗВАНИЕ («найди заметку с заголовком», «есть ли заметка под "
    "названием», «покажи заметку с названием») — используй read_notes.\n"
    "СОДЕРЖИМОЕ заметки («в какой заметке упоминается», «что я писал про», «найди "
    "текст про») — используй search_notes.\n"
    "КАТЕГОРИЯ или список («заметки в категории», «покажи все заметки») — "
    "используй list_notes.\n\n"    
    "Правило для генерации документа по шаблону (ОБЯЗАТЕЛЬНО):\n"
    "1. Вызови read_document(path=...) — увидишь структуру шаблона.\n"
    "2. Сразу после этого ВЫЗОВИ инструмент write_document через tool_call. "
    "НЕ пиши имя инструмента или его аргументы текстом в ответе — "
    "это ошибка. Инструмент вызывается только через tool_call.\n"
    "3. Заполни каждую секцию НОВЫМ содержанием по теме пользователя. "
    "НЕ копируй placeholder-текст шаблона («Краткое описание проекта», "
    "«Список целей», «Что достигнуто», «Итоги»).\n"
    "4. Заголовок — из задачи пользователя, НЕ из шаблона.\n"
    "5. content должен начинаться с «## » (первый раздел шаблона), "
    "НЕ с «# {title}» — write_document добавит заголовок сам.\n"
    "6. Отвечай на русском.\n\n"
    "Не спрашивай подтверждения. Не показывай структуру в тексте ответа. "
    "Не пиши имя инструмента в тексте — вызывай его."
)

MAX_TOOL_FAILURES = 2


def _summarize_for_log(result: object) -> str:
    """Краткое описание результата инструмента для лога.

    Не логирует содержимое списков (preview/snippet), чтобы в лог
    не попадали тексты заметок. Для ``Path`` оставляет путь.
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
class StepEvent:
    """Событие одного шага оркестратора (для CLI / SSE / UI).

    Атрибуты:
        step: номер шага (1-based).
        event_type: ``"llm_call"`` (перед вызовом LLM), ``"tool_result"``
            (после выполнения инструмента), ``"final"`` (LLM вернула финал).
        tool_name: имя инструмента (для ``tool_result``).
        status: для ``tool_result`` — ``"SUCCESS"``/``"ERROR"``/``"SKIPPED"``;
            для ``final`` — ``"ok"`` или ``"empty"``.
        count: число элементов, если результат инструмента — список.
    """

    step: int
    event_type: str
    tool_name: str | None = None
    status: str | None = None
    count: int | None = None


@dataclass
class OrchestratorResult:
    success: bool
    final_answer: str | None
    steps_used: int
    error: str | None = None
    tool_results: list[str] = field(default_factory=list)


@dataclass
class FinalEvent:
    """Финальное событие: обёртка над OrchestratorResult."""

    result: OrchestratorResult


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

    def run(
        self,
        goal: str,
        on_step: Callable[[StepEvent], None] | None = None,
    ) -> OrchestratorResult:
        """Выполнить цель, опционально сообщая о каждом шаге через ``on_step``."""

        def emit(event: StepEvent) -> None:
            if on_step is not None:
                on_step(event)

        messages: list[dict] = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": goal},
        ]
        tool_results: list[str] = []
        executed_calls: set[str] = set()
        failed_calls: dict[str, int] = {}

        for step in range(1, self.max_steps + 1):
            emit(StepEvent(step=step, event_type="llm_call"))
            response = self.llm.chat(messages)
            self.logger.info("step=%d type=%s", step, response.type)

            if response.type == "final":
                if not response.content or not response.content.strip():
                    self.logger.warning(
                        "empty final answer at step %d", step
                    )
                    emit(
                        StepEvent(
                            step=step, event_type="final", status="empty"
                        )
                    )
                    return OrchestratorResult(
                        success=False,
                        final_answer=None,
                        steps_used=step,
                        error="empty final answer",
                        tool_results=tool_results,
                    )
                self.logger.info("final: %s", response.content)
                emit(
                    StepEvent(step=step, event_type="final", status="ok")
                )
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

                emit(
                    StepEvent(
                        step=step,
                        event_type="tool_result",
                        tool_name=response.tool_name,
                        status=tool_status,
                        count=len(result) if isinstance(result, list) else None,
                    )
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
                elif tool_status == "ERROR":
                    content = (
                        f"tool_result: ERROR. {response.tool_name} failed: {result} "
                        f"Read the error message carefully: it explains what is wrong. "
                        f"Fix the arguments or use another tool, then try again."
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