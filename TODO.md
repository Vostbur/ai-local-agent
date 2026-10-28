# TODO

Мелкие исправления, технический долг и известные компромиссы. Не привязаны к шагам плана (`TASKS.md`), но шаг 6.7 их группирует.

Статусы: `[ ]` — не сделано, `[x]` — сделано.

Приоритеты:
- 🔴 **Критично** — исправить до шага 7 (RAG/PDF). Влияет на корректность конфига, путей или стабильность агента.
- 🟡 **Средний** — исправить в шаге 6.7 или по мере необходимости, не блокирует шаг 7.
- ⚪ **Низкий** — косметика и придирки, можно отложить.
- 🧩 **Компромисс** — осознанное решение, не баг. Пересмотреть при смене бэкенда или в RAG.

---

## 🔴 Критично перед шагом 7

### T14 + T22. Пакет, корень путей, `pyproject.toml`
**Файлы:** `pyproject.toml`, `src/__init__.py`, `src/agent/config.py`, `scripts/run_agent.py`, `tests/`
**Проблема (T14):** импорты держатся на `sys.path` и на том, что pytest запускают из корня. `from src.agent.tools.read_notes import ...` сработает не всегда.
**Проблема (T22):** `load_config()` ищет `config/settings.toml` относительно текущей папки. Запуск не из корня ломает и настройки, и `data/notes`. Дефолты `Path("data/notes")` в `read_notes`/`save_note` тоже зависят от CWD.
**Исправить:**
- `pyproject.toml` с `[tool.pytest.ini_options] pythonpath = ["."]`;
- `src/__init__.py` (пустой);
- `_PROJECT_ROOT = Path(__file__).resolve().parents[2]` в `config.py`;
- `load_config()` по умолчанию ищет `_PROJECT_ROOT / "config" / "settings.toml"`;
- дефолт `notes_dir` (если не задан в конфиге) — от `_PROJECT_ROOT`;
- убрать `sys.path.insert` из `scripts/run_agent.py` (становится ненужным при запуске из корня, но сохранить совместимость);
- проверить, что `python scripts/run_agent.py` из `D:\` находит конфиг.
**Тесты:** `pytest` из любой подпапки проходит; `test_load_config_from_non_project_cwd` через `monkeypatch.chdir`.

### T21 + T27. Честный `SafetyConfig`, убрать мёртвый `provider`
**Файлы:** `src/agent/config.py`, `src/agent/orchestrator.py`, `config/settings.example.toml`
**Проблема:**
- `confirm_file_operations = true` в example, в коде не используется;
- `allow_shell`, `allow_network`, `max_tool_retries` читаются, но не влияют на поведение;
- `MAX_TOOL_FAILURES = 2` — константа, а `SafetyConfig.max_tool_retries = 3` — дефолт, рассинхрон;
- `provider` читается из TOML, но `build_orchestrator` всегда `OllamaLLM`.
**Исправить:**
- `max_tool_retries` из `config.safety` передаётся в `Orchestrator` (параметр конструктора), `MAX_TOOL_FAILURES` становится дефолтом этого параметра;
- `allow_shell`, `allow_network` удалить из `SafetyConfig` и `settings.example.toml` (вернуть в шаге 8, если понадобятся для `move_file`/shell);
- `confirm_file_operations` оставить, но убрать `= true` из example и в комментарии пометить «будет использовано в шаге 8 для `move_file`»;
- `provider` убрать из `LLMConfig` и TOML до шага 9 (llama.cpp). В шаге 9 вернуть вместе с ветвлением клиента.
**Тесты:** `test_orchestrator_uses_max_tool_retries_from_config`; `test_provider_not_in_llm_config`.

---

## 🟡 Средний приоритет (шаг 6.7)

### T23. CLI печатает `result.error`
**Файл:** `scripts/run_agent.py`
**Проблема:** при `success=False` печатается только число шагов. Текст `unknown response type` пользователь не видит.
**Исправить:** в `_run_one` при `not result.success` печатать `result.error`, если есть.
**Тесты:** `test_run_one_prints_error` через `capsys` и `FakeLLM` с `type="unknown"`.

### T24. `max_results <= 0` даёт одну заметку
**Файлы:** `src/agent/tools/read_notes.py`, `src/agent/tools/search_notes.py`
**Проблема:** сначала `append`, потом сравнение `len(results) >= max_results`. При `max_results=0` возвращается одна заметка, при отрицательном — тоже.
**Исправить:** ранний `return []` в начале функции (после проверки `notes_dir.exists()`), если `max_results <= 0`.
**Тесты:** `test_read_notes_zero_max_results_returns_empty`, `test_search_notes_negative_max_results_returns_empty`.

### T25. Логи содержат `preview`/`snippet`
**Файл:** `src/agent/orchestrator.py`
**Проблема:** `logger.info("tool %s -> %s", tool_name, result)` пишет полный результат. Для `read_notes`/`search_notes` это тексты заметок. Противоречит `ARCHITECTURE.md`.
**Исправить:** логировать тип результата, длину (`len(str(result))`), число элементов для списков — но не содержимое. Для `save_note` можно оставить путь (это не текст заметки).
**Тесты:** `test_orchestrator_does_not_log_note_content` через `caplog` и инструмент, возвращающий список с «SECRET».

### T26. Промпт `save_note` просит выдумать заголовок
**Файл:** `src/agent/tools/save_note.py`
**Проблема:** в `parameters.title` описание «extract a short descriptive phrase (3-7 words) from their request» — прямо противоречит тому, что галлюцинация в `TASKS.md` списана на 3B.
**Исправить:** заменить на «If the user did not specify an explicit title, do NOT invent one — ask the user for clarification». Описание самого инструмента оставить, добавить фразу про «ask for clarification».
**Тесты:** `test_save_note_tool_description_does_not_suggest_inventing` (проверка, что «invent» или «ask for clarification» есть).

---

## ⚪ Низкий приоритет / после шага 7

### T19. Поиск только на одном уровне
**Файлы:** `read_notes.py`, `search_notes.py`
**Проблема:** вложенные папки в `notes_dir` не обходятся.
**Исправить:** опциональный параметр `recursive: bool = False`; по умолчанию — как сейчас. Когда появятся подпапки — включить.

### T28. Стем в `find_match` — подстрока, без `\b`
**Файл:** `src/agent/tools/_search.py`
**Проблема:** T4 поправил подсчёт `matches` в `search_notes` через `\b`, но `find_match_with_kind` для stem по-прежнему ищет подстроку. Возможны хиты с `matches=0` и ложные попадания внутри слов («недокументированный»).
**Исправить:** в `find_match_with_kind` для stem искать через `re.search(rf"\b{re.escape(stem)}", text_l)`. Тест на `недокументированный` — не должен матчиться по «документы».
**Приоритет:** закроется в шаге 7 (эмбеддинги заменят стемминг). Если не успеваем — отложить.

### T29. Два канала ошибок
**Файл:** `src/agent/orchestrator.py`
**Проблема:** неизвестный `type` → `OrchestratorResult(success=False)`, лимит шагов → `MaxStepsExceeded`. Разные механизмы.
**Исправить:** либо `MaxStepsExceeded` → `OrchestratorResult(success=False, error=...)`, либо неизвестный type → исключение. Унификация ломает тесты, менять рискованно.
**Приоритет:** отложить. После T23 CLI уже печатает обе причины (одна через `result.error`, другая через `except MaxStepsExceeded`).

### T30. Валидация аргументов по схеме; `needs_notes_dir` вместо `TOOLS_WITH_NOTES_DIR`
**Файлы:** `src/agent/orchestrator.py`, `src/agent/app.py`, `src/agent/registry.py`
**Проблема:** лишний ключ от модели → `TypeError` в `func(**kwargs)`. `TOOLS_WITH_NOTES_DIR` после T15 — второй список рядом с `ALL_TOOLS`. Закрывает неполноту C4.
**Исправить:**
- добавить `needs_notes_dir: bool = False` в `ToolDefinition`;
- `build_orchestrator` собирает `tool_context` из `[t for t in ALL_TOOLS if t.needs_notes_dir]`, а не из отдельного списка имён;
- перед `registry.call` — минимальная валидация: `required` поля присутствуют, типы `str`/`int` совпадают. Лишние ключи — отбрасывать с warning.
**Тесты:** `test_unknown_argument_dropped_with_warning`; `test_tool_context_built_from_needs_notes_dir`.

### T31. Пустой `final` считается успехом
**Файл:** `src/agent/orchestrator.py`
**Проблема:** `LLMResponse(type="final", content="")` → `success=True`, `final_answer=""`. Пользователь видит «Готово: ».
**Исправить:** при `final` с пустым/None `content` — `success=False, error="empty final answer"`.
**Тесты:** `test_empty_final_yields_failure`.
**Приоритет:** спорно — 3B может давать пустой финал как «сигнал завершения». Отложить до контрольного прогона.

### T32. Дрифт документации
**Файлы:** `README.md`, `ARCHITECTURE.md`, `config/settings.example.toml`
**Проблема:**
- README утверждает, что «документы» не найдёт «документация» — `query[:-2]` = «документ», это подстрока, найдёт;
- `settings.example.toml` с `:latest`, README без тега;
- `ARCHITECTURE.md` не отражает `SKIPPED`, `ALL_TOOLS`, T16.
**Исправить:** одним коммитом после шага 6.7. Сверить README с кодом, `:latest` унифицировать, добавить в ARCHITECTURE подразделы про статусы `tool_result` и `ALL_TOOLS`.

### T33. Дублирующий импорт в `test_search_helper.py`
**Файл:** `tests/test_tools/test_search_helper.py`
**Проблема:** возможно, `find_match` импортирован дважды (после T6 добавились `iter_md_files`, `load_note`).
**Исправить:** проверить шапку файла, убрать дубль.

---

## 🧩 Известные компромиссы (не баги)

### C1. Самодельный формат `tool_call:` / `tool_result:` вместо OpenAI `role: "tool"`
Для 3B стандартные роли `assistant.tool_calls` + `role=tool` часто работают хуже простых текстовых маркеров. Оставляем. Пересмотреть при смене бэкенда.

### C2. Стемминг `query[:-2]` вместо `pymorphy3`
`pymorphy3` — зависимость и замедление на CPU. Для заметок эвристики хватает. В RAG эмбеддинги решат семантику. Связано с T28 — оба уйдут в шаге 7.

### C3. Один tool call за шаг
Мультитул и параллельные вызовы — после того, как конфиг и статусы станут однозначными.

### C4. Дублирование списка инструментов — закрыто частично
T15 ввёл `ALL_TOOLS`, но `TOOLS_WITH_NOTES_DIR` остался вторым списком. Полное закрытие — T30 (`needs_notes_dir` на `ToolDefinition`). Пока фиксируем как «закрыто для `ALL_TOOLS`, не закрыто для `tool_context`».

---

## 📌 После шага 7 (RAG/PDF)

- Разделить хранилище заметок/документов, retriever (эмбеддинги) и агент. Не тащить эмбеддинги внутрь `search_notes.py`.
- Убрать стемминг из `_search.py` — заменяется на семантический поиск (закроет T28 и C2).
- Ротация `logs/agent.log`.
- Подтверждение опасных файловых операций (CLI) для `move_file` — вернёт `confirm_file_operations`, `allow_shell` (если понадобится).
- Пересмотреть C1 (формат `tool_call`/`tool_result`) при переходе на llama.cpp/OpenAI. Вернуть `provider` (шаг 9).
- Установить `temperature = 0.3` в `config/settings.toml`, если маршрутизация на 3B просядет.

---

## ✅ Сделано

### Шаги проекта
- [x] Шаг 1: каркас проекта.
- [x] Шаги 2–6: конфиг, логирование, `save_note`, `read_notes`, `search_notes`, оркестратор, подключение Ollama.
- [x] Шаг 5.5: удобная точка входа (`run_agent.py`) и фабрика оркестратора (`build_orchestrator`).
- [x] Шаг 5.6: русские триггеры в `SAVE_NOTE_TOOL`.
- [x] Шаг 6.1: защита от повторных вызовов.
- [x] Шаг 6.2: единая логика поиска со стеммингом.
- [x] Шаг 6.3: `query` опционален в `read_notes`.
- [x] Шаг 6.4: уточнение маршрутизации.
- [x] Контрольный прогон шага 6: 10/10.

### Критические исправления (шаг 6.5)
- [x] **T1.** Статус `SKIPPED` для повторного вызова.
- [x] **T7.** `load_config` читает `provider`, `base_url`, `max_steps`, `confirm_file_operations`.
- [x] **T8.** Убран дубль `logs`/`logs_dir`.
- [x] **T9.** `OllamaLLM.chat` устойчив к кривому ответу.
- [x] **T10.** `temperature` и `max_tokens` пробрасываются в Ollama.
- [x] **T11.** Лимит на повторы падающих вызовов.
- [x] **T12.** `notes_dir` не попадает в историю `tool_call:`.
- [x] **T20.** Убран мёртвый `path.read_bytes()`.

### Средние и низкие исправления (шаг 6.6)
- [x] **T2.** `read_notes(notes_dir=None)` вместо `Path = ...`.
- [x] **T3.** `max_results` в сигнатуре и схеме `read_notes`.
- [x] **T4.** `search_notes`: граница слова для stem, суффикс `"…"`.
- [x] **T5.** Убран дубль `?` в regex `save_note`.
- [x] **T6.** Общие `load_note` и `iter_md_files` в `_search.py`.
- [x] **T13.** `requirements.txt` — только прямые зависимости.
- [x] **T15.** Единый `ALL_TOOLS` в `build_orchestrator`.
- [x] **T16.** Неизвестный `response.type` → `OrchestratorResult(success=False)`.
- [x] **T17.** Windows-безопасный slug.
- [x] **T18.** `search_notes` прекращает чтение при `max_results`.