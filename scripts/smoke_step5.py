"""Smoke-тест шага 5: Orchestrator + OllamaLLM + save_note."""

import logging
import sys
from pathlib import Path

# Добавляем корень проекта в sys.path, чтобы импорты из src работали
# из любого рабочего каталога.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.agent.logging_setup import setup_logging
from src.agent.registry import ToolRegistry
from src.agent.llm_ollama import OllamaLLM
from src.agent.orchestrator import Orchestrator
from src.agent.tools.save_note import SAVE_NOTE_TOOL


def main() -> None:
    setup_logging(Path("logs"))

    registry = ToolRegistry()
    registry.register(SAVE_NOTE_TOOL)

    llm = OllamaLLM(model="qwen2.5-3b-agent", tools=[SAVE_NOTE_TOOL])

    orch = Orchestrator(
        llm=llm,
        registry=registry,
        logger=logging.getLogger("agent"),
        max_steps=5,
        tool_context={"save_note": {"notes_dir": Path("data/notes")}},
    )

    result = orch.run(
        "Сохрани заметку с заголовком 'Из Ollama' и текстом "
        "'Привет от локальной модели'"
    )

    print(result.success)
    print(result.final_answer)
    print(result.steps_used)

    notes_dir = Path("data/notes")
    print(list(notes_dir.iterdir()))


if __name__ == "__main__":
    main()
