# TODO

Мелкие исправления, технический долг и известные компромиссы. Не привязаны к шагам плана (`TASKS.md`), но шаги 6.5–6.7 закрыли критическую, среднюю части и T32.

Статусы: `[ ]` — не сделано, `[x]` — сделано.

Приоритеты:
- 🔴 **Критично** — исправить до шага 7. Все закрыты в шагах 6.5–6.7.
- 🟡 **Средний** — все закрыты.
- ⚪ **Низкий** — косметика и придирки, можно отложить.
- 🧩 **Компромисс** — осознанное решение, не баг.

---

## 🔴 Критично перед шагом 7

**Все критические исправления закрыты.** См. «✅ Сделано».

---

## 🟡 Средний приоритет

**Все средние исправления закрыты.** См. «✅ Сделано».

---

## ⚪ Низкий приоритет / после шага 7

### T19. Поиск только на одном уровне
**Файлы:** `read_notes.py`, `search_notes.py`
**Проблема:** вложенные папки в `notes_dir` не обходятся.
**Исправить:** опциональный параметр `recursive: bool = False`; по умолчанию — как сейчас. Когда появятся подпапки — включить.

### T28. Стем в `find_match` — подстрока, без `\b`
**Файл:** `src/agent/tools/_search.py`
**Проблема:** T4 поправил подсчёт `matches` в `search_notes` через `\b`, но `find_match_with_kind` для stem по-прежнему ищет подстроку. Возможны хиты с `matches=0` и ложные попадания внутри слов.
**Исправить:** в `find_match_with_kind` для stem искать через `re.search(rf"\b{re.escape(stem)}", text_l)`.
**Приоритет:** закроется в шаге 7 (эмбеддинги заменят стемминг).

### T29. Два канала ошибок
**Файл:** `src/agent/orchestrator.py`
**Проблема:** неизвестный `type` → `OrchestratorResult(success=False)`, лимит шагов → `MaxStepsExceeded`. Разные механизмы.
**Исправить:** либо унифицировать `MaxStepsExceeded` → `OrchestratorResult(success=False, error=...)`, либо неизвестный type → исключение.
**Приоритет:** отложить. После T23 CLI печатает обе причины.

### T30. Валидация аргументов по схеме; `needs_notes_dir`
**Файлы:** `src/agent/orchestrator.py`, `src/agent/app.py`, `src/agent/registry.py`
**Проблема:** лишний ключ или `None` от модели → `TypeError` в `func(**kwargs)` (T24 — частичная защита в инструментах). `TOOLS_WITH_NOTES_DIR` после T15 — второй список рядом с `ALL_TOOLS`.
**Исправить:**
- `needs_notes_dir: bool = False` на `ToolDefinition`;
- `build_orchestrator` собирает `tool_context` из `[t for t in ALL_TOOLS if t.needs_notes_dir]`;
- перед `registry.call` — отбрасывать `None`-значения для необязательных аргументов по схеме.
**Закрывает:** C4 полностью.

### T31. Пустой `final` считается успехом
**Файл:** `src/agent/orchestrator.py`
**Проблема:** `LLMResponse(type="final", content="")` → `success=True, final_answer=""`. Пользователь видит «Готово: ».
**Исправить:** при `final` с пустым/`None` `content` — `success=False, error="empty final answer"`.
**Приоритет:** спорно (3B может давать пустой финал как «сигнал завершения»). Отложить до данных.

### T33. Дублирующий импорт в `test_search_helper.py`
**Файл:** `tests/test_tools/test_search_helper.py`
**Проблема:** возможно, `find_match` импортирован дважды (после T6 добавились `iter_md_files`, `load_note`).
**Исправить:** проверить шапку файла, убрать дубль.

---

## 🧩 Известные компромиссы (не баги)

### C1. Самодельный формат `tool_call:` / `tool_result:` вместо OpenAI `role: "tool"`
Для 3B стандартные роли часто работают хуже. Пересмотреть при смене бэкенда (шаг 9).

### C2. Стемминг `query[:-2]` вместо `pymorphy3`
`pymorphy3` — зависимость и замедление на CPU. В RAG эмбеддинги решат семантику. Связано с T28 — оба уйдут в шаге 7.

### C3. Один tool call за шаг
Мультитул — после того, как конфиг и статусы станут однозначными.

### C4. Дублирование списка инструментов — закрыто частично
T15 ввёл `ALL_TOOLS`, но `TOOLS_WITH_NOTES_DIR` остался вторым списком. Полное закрытие — T30. Пока: «закрыто для `ALL_TOOLS`, не закрыто для `tool_context`».

---

## 📌 После шага 7 (RAG/PDF)

- Разделить хранилище заметок/документов, retriever (эмбеддинги) и агент. Не тащить эмбеддинги внутрь `search_notes.py`.
- Убрать стемминг из `_search.py` — заменяется на семантический поиск (закроет T28 и C2).
- Ротация `logs/agent.log`.
- Подтверждение опасных файловых операций (CLI) для `move_file` — вернёт `confirm_file_operations`.
- Пересмотреть C1 при переходе на llama.cpp/OpenAI. Вернуть `provider` (шаг 9).
- Установить `temperature = 0.3` в `config/settings.toml`, если маршрутизация на 3B просядет.

---

## ✅ Сделано

### Шаги проекта
- [x] Шаг 1: каркас проекта.
- [x] Шаги 2–6: конфиг, логирование, `save_note`, `read_notes`, `search_notes`, оркестратор, подключение Ollama.
- [x] Шаг 5.5: удобная точка входа (`run_agent.py`) и фабрика оркестратора.
- [x] Шаг 5.6: русские триггеры в `SAVE_NOTE_TOOL`.
- [x] Шаги 6.1–6.4: защита от повторов, единая логика поиска, `query` опционален, маршрутизация.
- [x] Контрольный прогон шага 6: 10/10.

### Критические и средние исправления (шаги 6.5, 6.6)
- [x] **T1.** Статус `SKIPPED` для повторного вызова.
- [x] **T2.** `read_notes(notes_dir=None)`.
- [x] **T3.** `max_results` в сигнатуре и схеме `read_notes`.
- [x] **T4.** `search_notes`: граница слова для stem, суффикс `"…"`.
- [x] **T5.** Убран дубль `?` в regex `save_note`.
- [x] **T6.** Общие `load_note` и `iter_md_files` в `_search.py`.
- [x] **T7.** `load_config` читает `base_url`, `max_steps`, `confirm_file_operations`.
- [x] **T8.** Убран дубль `logs`/`logs_dir`.
- [x] **T9.** `OllamaLLM.chat` устойчив к кривому ответу.
- [x] **T10.** `temperature` и `max_tokens` пробрасываются в Ollama.
- [x] **T11.** Лимит на повторы падающих вызовов.
- [x] **T12.** `notes_dir` не попадает в историю `tool_call:`.
- [x] **T13.** `requirements.txt` — только прямые зависимости.
- [x] **T15.** Единый `ALL_TOOLS` в `build_orchestrator`.
- [x] **T16.** Неизвестный `response.type` → `OrchestratorResult(success=False)`.
- [x] **T17.** Windows-безопасный slug.
- [x] **T18.** `search_notes` прекращает чтение при `max_results`.
- [x] **T20.** Убран мёртвый `path.read_bytes()`.

### Шаг 6.7: пути, CLI, честный safety, документация
- [x] **T14 + T22.** `pyproject.toml`, `src/__init__.py`, `_PROJECT_ROOT`; `load_config` и `PathsConfig` резолвят пути от корня проекта.
- [x] **T21 + T27.** `max_tool_retries` из `SafetyConfig` в `Orchestrator.__init__`; убраны `allow_shell`, `allow_network`, `provider`; `confirm_file_operations` убран из example до шага 8.
- [x] **T23.** CLI печатает `result.error` при `success=False`.
- [x] **T24.** `max_results=None` и `<= 0` в `read_notes`/`search_notes`.
- [x] **T25.** Логи без `preview`/`snippet` — `_summarize_for_log`.
- [x] **T26.** Промпт `save_note` не просит выдумывать `title`.
- [x] **T32.** Документация синхронизирована с кодом: `README.md`, `ARCHITECTURE.md`, `config/settings.example.toml`.