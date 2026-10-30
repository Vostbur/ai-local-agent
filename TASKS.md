# Задачи

## Шаг 1. Каркас проекта ✅
- [x] Создать структуру каталогов.
- [x] Создать README, ARCHITECTURE, TASKS.
- [x] Настроить .gitignore.
- [x] Сделать первый git-коммит.

## Шаг 2. Каркас приложения без LLM ✅
- [x] Создать конфиг и логирование.
- [x] Создать реестр инструментов с заглушкой `echo`.
- [x] Написать тесты конфига и реестра.
- [x] Smoke-скрипт `smoke_step2.py`.

## Шаг 3. Первый инструмент `save_note` ✅
- [x] Реализовать `save_note` с защитой от перезаписи.
- [x] Unit-тесты без LLM (7 тестов).
- [x] Smoke-скрипт `smoke_step3.py`.
- [x] Проверить кириллицу в именах файлов.

## Шаг 4. Оркестратор с фейковой LLM ✅
- [x] Реализовать `Orchestrator` с циклом и лимитом шагов.
- [x] `FakeLLM` и `LLMClient` протокол.
- [x] Инъекция `tool_context` (пути из конфига, а не из LLM).
- [x] Тесты оркестратора (5 сценариев).
- [x] Smoke-скрипт `smoke_step4.py`.

## Шаг 5. Подключение реальной Ollama ✅
- [x] `OllamaLLM` через OpenAI-совместимый endpoint.
- [x] Тесты с моком HTTP (без реальной сети).
- [x] Модель `qwen2.5-3b-agent` с `num_ctx=8192` через `Modelfile`.
- [x] Smoke-скрипт `smoke_step5.py` с реальной моделью.
- [x] Обновить `requirements.txt` (добавлен `requests`).

## Шаг 5.1. Актуализация документации ✅
- [x] Обновить `README.md` под текущее состояние.
- [x] Обновить `ARCHITECTURE.md`.
- [x] Обновить `TASKS.md`.

## Шаг 5.5. Удобная точка входа ✅
- [x] `src/agent/app.py` — `build_orchestrator`.
- [x] `scripts/run_agent.py` — режим одной задачи и интерактивный режим.
- [x] Обработка типичных ошибок.
- [x] Тесты `test_app.py`.

## Шаг 5.6. Уточнение `SAVE_NOTE_TOOL` ✅
- [x] Русские триггеры в описании.
- [x] Примеры в `parameters`.
- [x] Тест на описание.

## Шаг 6. Инструменты работы с заметками ✅
- [x] `read_notes(query) -> list[dict]`.
- [x] `search_notes(query, max_results=5) -> list[dict]`.
- [x] Unit-тесты без LLM.
- [x] Регистрация в `build_orchestrator`.
- [x] Smoke через `run_agent.py`.

## Шаг 6.1. Защита от повторных вызовов ✅
- [x] Системный промпт в `Orchestrator`.
- [x] Детектор `executed_calls` по ключу вызова.
- [x] Статус `SUCCESS` / `ERROR` / `SKIPPED` в `tool_result`.
- [x] Тесты на повторный вызов и системный промпт.

## Шаг 6.2. Единая логика поиска ✅
- [x] `src/agent/tools/_search.py` — `find_match`, `find_match_with_kind`.
- [x] `read_notes` ищет только по title и filename.
- [x] `search_notes` использует стемминг.
- [x] Тесты хелпера и инструментов.

## Шаг 6.3. `query` опционален в `read_notes` ✅
- [x] Default `query=""`.
- [x] Убрано `required` из схемы параметров.

## Шаг 6.4. Уточнение маршрутизации ✅
- [x] Противопоставление `read_notes` / `search_notes` в описаниях.
- [x] Правило маршрутизации в `SYSTEM_PROMPT`.

## Шаг 6. Контрольный прогон ✅
- [x] 10/10 сценариев пройдено (2026-10-26).
- [x] Маршрутизация `read_notes` vs `search_notes` стабильна.
- [x] Защита от повторных вызовов не сработала ни разу.
- [x] Известное ограничение 3B: галлюцинация заголовка на неполных запросах.

## Шаг 6.5. Ревью и критические исправления ✅
- [x] **T1.** Статус `SKIPPED` для повторного вызова.
- [x] **T7.** `load_config` читает `base_url`, `max_steps`, `confirm_file_operations`.
- [x] **T8.** Убран дубль `logs`/`logs_dir`.
- [x] **T9.** `OllamaLLM.chat` устойчив к кривому ответу.
- [x] **T10.** `temperature` и `max_tokens` пробрасываются в Ollama.
- [x] **T11.** Лимит на повторы падающих вызовов.
- [x] **T12.** `notes_dir` не попадает в историю `tool_call:`.
- [x] **T20.** Убран мёртвый `path.read_bytes()`.

## Шаг 6.6. Средние и низкие исправления ✅
- [x] **T2.** `read_notes(notes_dir=None)`.
- [x] **T3.** `max_results` в сигнатуре и схеме `read_notes`.
- [x] **T4.** `search_notes`: граница слова для stem, суффикс `"…"`.
- [x] **T5.** Убран дубль `?` в regex `save_note`.
- [x] **T6.** Общие `load_note` и `iter_md_files` в `_search.py`.
- [x] **T13.** `requirements.txt` — только прямые зависимости.
- [x] **T15.** Единый `ALL_TOOLS` в `build_orchestrator`.
- [x] **T16.** Неизвестный `response.type` → `OrchestratorResult(success=False)`.
- [x] **T17.** Windows-безопасный slug.
- [x] **T18.** `search_notes` прекращает чтение при `max_results`.

## Шаг 6.7. Пути, CLI и честный safety ✅
- [x] **T14 + T22.** `pyproject.toml`, `src/__init__.py`, `_PROJECT_ROOT`; пути от корня проекта, а не от CWD.
- [x] **T21 + T27.** `max_tool_retries` из `SafetyConfig` в `Orchestrator.__init__`; убраны `allow_shell`, `allow_network`, `provider`; `confirm_file_operations` убран из example до этапа B.
- [x] **T23.** CLI печатает `result.error` при `success=False`.
- [x] **T24.** `max_results=None` и `<= 0` в `read_notes`/`search_notes`.
- [x] **T25.** Логи без `preview`/`snippet` — `_summarize_for_log`.
- [x] **T26.** Промпт `save_note` не просит выдумывать `title`.
- [x] **T32.** Документация синхронизирована с кодом.

## Шаг 7. Документы и RAG
- [x] **7.0.** Реестр экстракторов + Markdown + TXT.
- [x] **7.0.1.** `index_documents.py`, `documents_dir` в конфиге.
- [x] **7.1.** Chunker, Embedder, VectorStore (numpy).
- [x] **7.1.1.** Модель эмбеддингов → `paraphrase-multilingual-mpnet-base-v2` (768-dim).
- [x] **7.1.2.** Contextual chunking + `chunk_size=400`.
- [x] **7.1.3.** Гибридный поиск BM25 + RRF.
- [x] **7.1.4.** Стемминг в BM25 (префикс 5 символов).
- [x] **7.1.5.** IDF-фильтр в BM25 (`min_idf=2.0`).
- [x] **7.2.** `search_documents` как инструмент.
- [x] **7.2.1, 7.2.2.** Итерации промптов (routing на 3B: 4/7).
- [x] **7.5.** 7B как основная модель (routing 7/7, synthesis 6/7).
- [x] **7.4.** `PdfExtractor` через реестр (PyMuPDF). Smoke: `EcoRouter-UserGuide.pdf` → 3116 чанков, OSPF → `Страница 117`.
- [x] **7.3.** Генерация по шаблону: `read_document` + `write_document`. Smoke 2/2. Ограничения 7B — C6 (галлюцинации), C7 (2 tool_calls).

## Tech debt: T28–T34 ✅
- [x] **T28.** Общий `stem.py` (префикс 5 символов), `\b` в `find_match`.
- [x] **T33.** Убран дубль импорта в `test_search_helper.py`.
- [x] **T31.** Пустой `final` → `success=False, error="empty final answer"`.
- [x] **T30.** `needs_notes_dir` / `needs_output_dir` на `ToolDefinition`; `tool_context` из `ALL_TOOLS`.
- [x] **T34.** `make_search_documents_tool(config)` — фабрика вместо глобального `_rag_service`; `build_tools(config)`.

## U1. Единый CLI ✅
- [x] **U1.** `python -m src.agent run/chat/index/search`; `scripts/*` — deprecated-обёртки.
- [x] **U1.1.** `pip install -e .` — `python -m agent` без `src.`.
- [x] **U1.2.** `python -m agent ask ["вопрос"]` — чат с моделью без tools.

## U4. `AgentService` ✅
- [x] `src/agent/service.py` — `AgentService(config, logger)`.
- [x] `ask(goal) -> Iterator[Event]` и `ask_plain(goal)`.
- [x] `StepEvent`, `FinalEvent`; `Orchestrator.run(on_step=...)`.
- [x] `cli.py` через `AgentService`.
- [x] `MaxStepsExceeded` / `unknown type` / `RuntimeError` → `FinalEvent(success=False, error=...)`.

## U5. Веб-интерфейс ✅
- [x] `src/agent/web/app.py` — FastAPI, SSE.
- [x] `GET /`, `POST /ask`, `POST /ask-plain`, `GET /stream/{task_id}`.
- [x] `POST /index` — переиндексация (блокирующая).
- [x] Вкладки: Агент, Документы, Чат (без tools).
- [x] `python -m agent web` (порт 8000).

## Этап A. Изоляция и чистка планов ✅
- [x] Убрать все планы по фотографиям (`analyze_image`, `move_file`, `moondream`/`llava`, шаг 8).
- [x] Убрать `POST /analyze-image` (501) и вкладку «Фото» из UI.
- [x] Убрать Telegram, мессенджеры, интернет-интеграции из планов.
- [x] Web UI: `host=0.0.0.0` по умолчанию, предупреждение при старте.
- [x] Раздел «Безопасность» в `README.md`: LAN без аутентификации, не открывать в интернет.

## Этап B. Заметки: CRUD + категории — следующий
- [ ] `update_note(path, title=None, content=None) -> dict`.
- [ ] `delete_note(path) -> dict` — в `data/trash/notes/`.
- [ ] `list_notes(category=None) -> list[dict]`.
- [ ] `move_note(path, category) -> dict`.
- [ ] Категории через папки: `data/notes/<category>/<slug>.md`.
- [ ] `save_note(..., category=None)`.
- [ ] `iter_md_files` → рекурсивный (закрывает T19).
- [ ] Прямой API: `GET /notes`, `GET /notes/{path}`, `PUT /notes/{path}`, `DELETE /notes/{path}`, `POST /notes`, `POST /notes/{path}/move`, `GET /categories`.
- [ ] UI: вкладка «Заметки» — таблица, фильтр по категории, кнопки «Создать», «Редактировать», «Удалить», «Переместить». Модальное окно редактирования.
- [ ] Тесты: `test_notes_crud.py`, `test_web_notes.py`.
- [ ] Обновить `ARCHITECTURE.md` (новые инструменты), `README.md` (вкладка «Заметки»).

## Этап C. Документы: управление + инкрементальная индексация
- [ ] `VectorStore.remove_by_path(path)` — фильтрация `vectors` и `chunks`.
- [ ] Инкрементальная индексация: `data/index/meta.json` (`{path: {mtime, size, hash, chunk_count}}`). При `index` без `--reset`: новые → добавить, изменённые → удалить старые чанки + добавить новые, удалённые → удалить чанки, неизменённые → пропустить.
- [ ] `build_index(..., incremental=True)`.
- [ ] Прямой API: `GET /documents`, `POST /documents/upload` (multipart), `DELETE /documents/{path}` (в `data/trash/documents/`).
- [ ] `POST /index` → SSE-прогресс по файлам (не блокирующий).
- [ ] UI: вкладка «Документы» — дерево файлов, размер, дата, статус индексации, кнопки «Загрузить», «Удалить», «Переиндексировать» с SSE-прогрессом.
- [ ] Тесты: `test_indexer_incremental.py`, `test_web_documents.py`.
- [ ] Обновить `ARCHITECTURE.md`, `README.md`.

## Этап D. Создание документа по образцу через UI
- [ ] UI: вкладка «Документы» → секция «Создать по образцу»: dropdown шаблон, поле «Тема», кнопка «Создать».
- [ ] `POST /generate-from-template` с `{template_path, topic}` → `AgentService.ask` → SSE-прогресс (`read_document` → `write_document` → `final`).
- [ ] Показать результат: ссылка «Открыть в вкладке Заметки?» / «Скачать».
- [ ] Предупреждение C6: «Содержание сгенерировано моделью, проверьте факты».
- [ ] Тесты: `test_web_generate.py`.
- [ ] Обновить `README.md`.

## Этап E. Документация
- [ ] `README.md`: новые вкладки (Заметки, Документы), CRUD, категории, загрузка/удаление документов, создание по образцу. Раздел «Безопасность».
- [ ] `ARCHITECTURE.md`: новые инструменты, категории, инкрементальная индексация, API-эндпоинты.
- [ ] `TASKS.md`: отметить A–E.
- [ ] `TODO.md`: актуализировать.

## Идеи на будущее (не в текущем плане)
- Мультиагентность.
- Самодописывание инструментов с подтверждением человеком и песочницей.
- OCR для скан-PDF (документы).
- Смена эмбеддинга на `intfloat/multilingual-e5-small` — если C5 станет блокером.
- Cross-encoder реранкер после RRF.
- Кэширование BM25 на диск — при росте корпуса до 100 000+ чанков.

## Известные проблемы и наблюдения

### Модель qwen2.5-3b: нестабильный tool calling — решено переходом на 7B (шаги 6.1–7.5)
**Обнаружено:** 2026-10-25
**Закрыто:** 2026-10-29

**Симптомы (исторически):**
- Зацикливалась на повторных вызовах.
- Генерировала бессмысленный контент.
- Файлы сохранялись с суффиксами `_1.md`, `_2.md` из-за повторов.

**Причина:** 3B слишком мала для надёжного tool calling.

**Что сделано (для 3B):**
1. Системный промпт (6.1).
2. Детектор `executed_calls` (6.1) → `SKIPPED`.
3. Три статуса `tool_result` (6.5, T1).
4. Уточнённые описания и `SYSTEM_PROMPT` (6.4, 7.2.1).
5. Лимит падений (6.5, T11).
6. Неизвестный `response.type` (6.6, T16).
7. `max_results=None` (6.7, T24).
8. Промпт `save_note` (6.7, T26).
9. Few-shot (7.2.2) — не помог 3B (4/7 routing).

**Решение — 7B (7.5):** `qwen2.5-7b-agent` — routing 7/7, synthesis 6/7. Стоимость: скорость −2–3×, RAM ~6 ГБ. 3B — опция.

### RAG: качество поиска — итерации (шаги 7.1–7.2)
**Что сделано:**
1. 7.1.1: модель → `mpnet-base-v2` (768-dim).
2. 7.1.2: contextual chunking + `chunk_size=400`.
3. 7.1.3: гибридный поиск BM25 + RRF.
4. 7.1.4: стемминг BM25.
5. 7.1.5: IDF-фильтр `min_idf=2.0`.

**Результат:** retrieval находит правильный раздел в 6/7 случаев. Оставшийся провал — C5.

### C5. Hybrid search доминируется vector на семантически близких запросах
BM25 в изоляции находит «Установка с нуля» по «Как установить агента?» со score 8.766. `search_hybrid` возвращает «Как понять, что агент…» — `mpnet` ставит этот чанк vector top-1, «Установка» не в vector top-10.

**Причина:** семантика `mpnet`, не размер корпуса (проверено на 94 и 3116 чанках).

**Обход:** уточнять запрос. **Возможные решения (отложить):** e5-small, cross-encoder реранкер.
**Приоритет:** низкий.

### C6. 7B галлюцинирует в содержании при генерации по шаблону
На «создай отчёт про AI-агента по шаблону» 7B заполняет секции типичными фразами («Интеграция с CRM успешно завершена»), не зная реального контекста проекта.

**Обход:** уточнять конкретику в задаче. В UI (этап D) — предупреждение «проверьте факты».
**Приоритет:** низкий.

### C7. 7B возвращает 2 tool_calls, используется первый
`OllamaLLM` берёт первый `tool_call` (осознанно, T9). Второй теряется. Связано с C3.
**Приоритет:** низкий.

## Технический долг
См. `TODO.md`. Все 🔴 и 🟡 закрыты. Открытые пункты — ⚪ (T29, C5–C7) и этапы B–E.