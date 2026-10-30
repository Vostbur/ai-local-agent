# Архитектура

## Общая схема

1. Пользователь ставит цель (текстом).
2. Оркестратор передаёт цель локальной LLM.
3. LLM либо возвращает финальный ответ, либо просит вызвать инструмент.
4. Оркестратор вызывает инструмент и возвращает результат в LLM.
5. Цикл повторяется до финала или до лимита шагов.

Агент работает в изолированной среде: Ollama на `localhost`, документы и заметки — на диске пользователя, никакие данные не отправляются в интернет. Web UI доступен по локальной сети без аутентификации (осознанное решение, C8).

## Текущее состояние (после этапа B, ядро)

### Реализовано и работает

- загрузка конфигурации из TOML; относительные пути в `[paths]` резолвятся от корня проекта, а не от CWD;
- `pyproject.toml` с `pythonpath = ["."]` и `pip install -e .` — тесты и `python -m agent` работают из любой папки;
- единый CLI `python -m agent run/chat/ask/index/search/web`; `scripts/*` — deprecated-обёртки;
- логирование в файл и консоль; полные результаты инструментов в лог не пишутся;
- реестр инструментов; декларация контекста (`needs_notes_dir`, `needs_output_dir`, `needs_trash_dir`) на `ToolDefinition`;
- сборка инструментов через `build_tools(config)` — единственный источник правды для registry, `tools` LLM и `tool_context`;
- протокол LLM и фейковая LLM для тестов;
- подключение к реальной Ollama через OpenAI-совместимый endpoint; устойчивость к битому JSON, пустым `choices`, нескольким `tool_calls`;
- оркестратор с лимитом шагов, защитой от повторных вызовов, лимитом падений, тремя статусами `tool_result`, инъекцией контекста инструментов и направляющим текстом ошибки;
- `AgentService` — `Iterator[StepEvent|FinalEvent]`, единый интерфейс для CLI и web;
- **восемь инструментов заметок** (этап B): `save_note` (с категорией, возвращает `dict`), `read_notes`, `search_notes`, `list_notes`, `update_note`, `delete_note` (в корзину), `move_note`, `list_categories`; единый контракт путей (относительные от `data/notes/` + поле `category`); фолбэк резолва по заголовку (C9);
- корзина `data/trash/notes/` — сохраняет структуру категорий, добавляет таймстамп к имени;
- `search_documents` — фабрика `make_search_documents_tool(config)` без глобального состояния;
- `read_document` — чтение Markdown/TXT/PDF, защита от path traversal, обрезка до `max_chars`;
- `write_document` — обёртка над `save_note` для `data/generated/`;
- RAG по Markdown/TXT/PDF: реестр экстракторов, чанкинг с перекрытием, эмбеддинги `paraphrase-multilingual-mpnet-base-v2`, numpy-хранилище, гибридный поиск (BM25 + векторный через RRF);
- общий стеммер `src/agent/stem.py` (префикс 5 символов) для BM25 и `find_match`;
- Web UI: FastAPI + SSE, вкладки Агент / Документы / Чат (без tools);
- основная модель — `qwen2.5-7b-agent` (routing 7/7 в контрольном прогоне). 3B — опция для скорости.

### Пока не реализовано

- работа с DOCX/HTML/EPUB (сейчас RAG на Markdown/TXT/PDF);
- **прямой REST API для заметок** (`GET/POST/PUT/DELETE /notes`, `POST /notes/{path}/move`, `GET /categories`) — остаток этапа B;
- **Web UI для заметок** (вкладка «Заметки»: таблица, фильтр по категориям, CRUD, модальное окно редактирования) — остаток этапа B;
- управление документами (загрузка/удаление) и инкрементальная индексация (этап C);
- создание документа по образцу через Web UI (этап D);
- подтверждение опасных операций через CLI (`confirm_file_operations` читается, но не применяется — этап B).

## Компоненты

### Оркестратор (`src/agent/orchestrator.py`)

Управляет циклом «рассуждение → действие → наблюдение».

- Ограничивает число шагов (`max_steps`, по умолчанию 10).
- Логирует каждый шаг: тип ответа LLM, имя инструмента, краткий результат (`_summarize_for_log`).
- Поддерживает `tool_context` — словарь `{имя_инструмента: {доп_аргументы}}`. Аргументы добавляются к тем, что передала LLM, и перекрывают их. Так пути (`notes_dir`, `output_dir`, `trash_dir`) передаются из конфига, а не из модели.
- Хранит `executed_calls` (успешные вызовы) и `failed_calls` (счётчик ошибок по ключу вызова). Повторный успешный вызов → `SKIPPED`; после `max_tool_failures` неудач → `ERROR` с «giving up».
- `max_tool_failures` приходит из `SafetyConfig.max_tool_retries` (по умолчанию 2).
- Ловит исключения инструментов и возвращает их в LLM как `ERROR: ...`, не роняя цикл.
- При неизвестном `response.type` возвращает `OrchestratorResult(success=False, error=...)`, а не крутит цикл до `MaxStepsExceeded`.
- При `final` с пустым/`Nonecontent` → `success=False, error="empty final answer"` (T31).
- При превышении лимита шагов выбрасывает `MaxStepsExceeded`.
- `run(goal, on_step=None)` — `on_step: Callable[[StepEvent], None] | None`. На каждом шаге вызывается `on_step` с `StepEvent`. Используется `AgentService` для потока событий.
- `StepEvent` — датакласс: `step`, `event_type` (`"llm_call"` / `"tool_result"` / `"final"`), `tool_name`, `status` (`SUCCESS` / `ERROR` / `SKIPPED` / `ok` / `empty`), `count` (число элементов, если результат — список).
- `FinalEvent` — обёртка над `OrchestratorResult` для `AgentService`.

**`SYSTEM_PROMPT`** содержит:

- Список из 11 инструментов с одной строкой описания каждого (`save_note`, `read_notes`, `search_notes`, `list_notes`, `update_note`, `delete_note`, `move_note`, `list_categories`, `search_documents`, `read_document`, `write_document`).
- Правило «почти любой вопрос про проект, установку, требования, возможности, статьи, лицензию → `search_documents`».
- Few-shot примеры для routing `search_documents` (без синтаксиса `tool_name(...)` — это ломает 7B, см. урок).
- Правило «не выдумывай»: после `search_documents` отвечать только по фрагментам.
- **Правило «Изменение заметок»**: `update_note`/`delete_note`/`move_note` принимают путь, не заголовок; пример формата `'категория/имя_файла'` без реальных путей (урок 2026-10-30: модель копировала буквальный путь из промпта вместо поиска); запрет угадывать путь.
- **Правило «Выбор инструмента для заметок»**: заголовок/название → `read_notes`; содержимое → `search_notes`; категория/список → `list_notes`. Без синтаксиса вызовов.
- Правило генерации по шаблону: «после `read_document` сразу вызови `write_document` через tool_call, не пиши имя инструмента текстом; content начинается с `##`, не с `# title`; не копируй placeholder-текст; отвечай на русском».

### `AgentService` (`src/agent/service.py`)

- `AgentService(config, logger)` — единый интерфейс для CLI и web.
- `ask(goal) -> Iterator[Event]` — задача с инструментами. Лениво собирает `build_orchestrator`, копит `StepEvent` через `on_step`, выдаёт события + `FinalEvent` в конце.
- `ask_plain(goal) -> Iterator[Event]` — чат без инструментов (`OllamaLLM(tools=[])`, без SYSTEM_PROMPT, без оркестратора). Один `FinalEvent` в конце.
- `Event = StepEvent | FinalEvent`.
- `MaxStepsExceeded`, `unknown type`, `RuntimeError` → `FinalEvent(success=False, error=...)`. Генератор не бросает.

Ограничение sync-генератора: события копятся во время `Orchestrator.run` и выдаются после завершения. Для CLI разницы нет. Для web SSE клиент получает все события разом, но рендерит по одному. Настоящий live-stream требует стриминга Ollama — не в текущем плане.

### LLM-слой

`src/agent/llm.py`:

- Датакласс `LLMResponse` с полями `type` (`"tool_call"` или `"final"`), `content`, `tool_name`, `tool_arguments`.
- Протокол `LLMClient` с методом `chat(messages) -> LLMResponse`.
- `FakeLLM` для детерминированных тестов.

`src/agent/llm_ollama.py`:

- Класс `OllamaLLM`, реализующий `LLMClient`.
- Использует OpenAI-совместимый endpoint `POST {base_url}/v1/chat/completions` — стабильнее нативного `/api/chat` и совместим с `llama.cpp`.
- Передаёт инструменты в формате `{"type": "function", "function": {...}}`; `tool_choice` — только если `tools` не пустой.
- Парсит `tool_calls` (аргументы приходят строкой JSON → `json.loads`).
- `temperature`/`max_tokens` передаются только если заданы в конфиге (`None` → не передаются).
- Устойчив к «кривому» ответу: `JSONDecodeError`, пустые `choices`, отсутствие `message`, несколько `tool_calls` (берётся первый с warning), невалидный JSON в `arguments`, `arguments` уже словарём.
- Полный `messages` в лог не пишется — только `model`, `messages_count`, `last_role`, `last_len`.
- Таймаут 900 секунд (на CPU модель отвечает медленно; хардкод, T35 — кандидат в конфиг).
- При сетевой ошибке выбрасывает `RuntimeError`.
- Модель — `[llm] model` в `config/settings.toml`. По умолчанию `qwen2.5-7b-agent`: на CPU в 2–3 раза медленнее 3B, но routing инструментов значительно надёжнее (7/7 против 4/7).

### Реестр инструментов (`src/agent/registry.py`)

- `ToolDefinition`: `name`, `description`, `parameters` (JSON-схема), `func`, `needs_notes_dir: bool = False`, `needs_output_dir: bool = False`, `needs_trash_dir: bool = False`.
- `ToolRegistry`: регистрация, получение по имени, список всех, вызов `call(name, **kwargs)`.
- Дубликат имени → `ValueError`. Неизвестное имя → `KeyError`.
- Агент не пишет код инструментов. Он выбирает из зарегистрированных. Новые инструменты добавляются вручную и покрываются тестами.
- `needs_notes_dir` / `needs_output_dir` / `needs_trash_dir` — декларация контекста. `build_orchestrator` собирает `tool_context` из `build_tools`, проверяя эти флаги. Единственный источник правды — список инструментов (T30, T34).

### Сборка (`src/agent/app.py`)

- `build_tools(config) -> list[ToolDefinition]` — собирает все 11 инструментов с учётом `config`. `search_documents` создаётся фабрикой `make_search_documents_tool(config)` (нужен `index_dir` и `embedding_model`), остальные — модульные константы.
- `build_orchestrator(config, logger)` — вызывает `build_tools(config)` один раз, использует результат трижды:
  - `registry.register(tool)` для каждого;
  - `OllamaLLM(tools=tools, ...)`;
  - `tool_context`: для каждого `tool` с `needs_notes_dir` → `{"notes_dir": config.paths.notes_dir}`, с `needs_output_dir` → `{"output_dir": config.paths.generated_dir}`, с `needs_trash_dir` → `{"trash_dir": config.paths.trash_dir}`.

### Конфигурация (`src/agent/config.py`)

- `_PROJECT_ROOT = Path(__file__).resolve().parents[2]`.
- `_resolve_path(value)` — относительные пути от `_PROJECT_ROOT`, абсолютные как есть.
- Читает `config/settings.toml` через `tomllib`; по умолчанию ищет в `_PROJECT_ROOT / "config" / "settings.toml"` — не зависит от CWD.

Датаклассы:

- `LLMConfig` — `model`, `base_url`, `temperature`, `max_tokens`, `max_steps`. Поле `provider` удалено (T27), вернётся при подключении `llama.cpp`.
- `PathsConfig` — `data_dir`, `notes_dir`, `inbox_dir`, `photos_dir`, `documents_dir`, `index_dir`, `generated_dir`, **`trash_dir`** (корзина для удалённых заметок/документов, дефолт `data/trash`), `logs_dir`, `memory`, `tools`. Все относительные — от `_PROJECT_ROOT`. `photos_dir` остаётся в конфиге (пустая папка, не используется), но инструментов для фото нет.
- `SafetyConfig` — `confirm_file_operations` (читается, применяется на этапе B), `max_tool_retries`.
- `RAGConfig` — `embedding_model`, `chunk_size`, `chunk_overlap`, `top_k`.
- `AppConfig` — обёртка.

`load_config()` бросает `FileNotFoundError` / `ValueError`. Для `[rag]` берёт дефолты из `RAGConfig()` (чтобы `load_config` и датакласс не расходились).

### Логирование (`src/agent/logging_setup.py`)

- Один логгер `"agent"`.
- Два обработчика: `logs/agent.log` (UTF-8, append) и консоль.
- Формат: `%(asctime)s | %(levelname)s | %(name)s | %(message)s`.
- Повторный вызов не добавляет дубликаты.
- Полные результаты инструментов не логируются: `_summarize_for_log` сворачивает списки в `list[N]`, `Path` оставляет как строку, dict — в `{type}, len=N`, длинные строки обрезает.

### CLI (`src/agent/__main__.py`, `src/agent/cli.py`)

`python -m agent <command>` (или `python -m src.agent <command>` без `pip install -e .`).

`argparse` с подкомандами:

- `run "цель"` — одна задача (`cli.run_once` → `AgentService.ask`).
- `chat` — интерактивный режим с инструментами (`cli.interactive_loop`).
- `ask ["вопрос"]` — чат с моделью без tools (`cli.ask_once` / `cli.ask_interactive` → `AgentService.ask_plain`). Поведение как `ollama run`.
- `index [--documents PATH] [--reset] [--batch-size N]` — пересборка RAG-индекса (`cli.build_index_cmd` → `rag.build.build_index`).
- `search "запрос" [--top-k N] [--no-truncate]` — отладка retrieval без LLM (`cli.search_cmd` → `make_search_documents_tool(config).func`).
- `web [--host HOST] [--port PORT]` — запуск FastAPI. По умолчанию `--host 0.0.0.0` (LAN) с предупреждением в логе.

Ленивые импорты внутри веток — `search` не грузит `build_orchestrator`/`OllamaLLM`, `run` не грузит `build_index`/`Embedder`, `web` не грузится до вызова.

**Прямой API ≠ агент.** CRUD заметок и управление документами (этапы B–D) идут через прямой REST API web, не через `AgentService`. Агент остаётся для «сохрани заметку про X» и «найди, что я писал про Y» — там, где естественный язык уместен. Редактирование заметки через 7B — 2–4 минуты и риск галлюцинаций; прямой API — мгновенно и предсказуемо.

### Веб-интерфейс (`src/agent/web/`)

- `app.py` — FastAPI-приложение. `create_app(config, logger, service=None) -> FastAPI`.
- `templates/index.html` — одностраничный UI (vanilla JS, `EventSource`).
- `POST /ask` → `task_id`; `GET /stream/{task_id}` → SSE (`StepEvent` / `FinalEvent`). Фоновый `threading.Thread` + `asyncio.Queue` + `loop.call_soon_threadsafe`.
- `POST /ask-plain` — без инструментов (чат).
- `POST /index` — переиндексация RAG (блокирующая, FastAPI threadpool). Возвращает `{success, chunks, error}`.
- `GET /health` — `{"status": "ok"}`.

Вкладки: Агент, Документы, Чат. Фото, Telegram, интернет — не планируются.

Запуск: `python -m agent web`. Только LAN, без аутентификации (C8). Предупреждение при старте, если `host == "0.0.0.0"`.

## Инструменты (`src/agent/tools/`)

### `_search.py` (общие хелперы заметок)

- `find_match_with_kind(text, query)` — точное вхождение, затем fallback на `stem(query)` с `\b`-границей. Возвращает `(start, end, kind)`, `kind` — `"exact"` или `"stem"`.
- `find_match(text, query)` — обёртка, возвращает `(start, end)`.
- `iter_md_files(notes_dir, recursive=True)` — отсортированный список `*.md`. С этапа B рекурсивный по умолчанию (категории = подпапки; закрывает T19); папки с именем `trash` в пути пропускаются. `recursive=False` — только верхний уровень.
- `load_note(path)` — `{"title": ..., "body": ...}` или `None`.
- `category_of(path, notes_dir)` — категория заметки: относительная папка или `None` для корня. Один источник правды для `list_notes`, `read_notes`, `search_notes`.
- `validate_category(category)` — валидация имени категории: запрещены `..`, `/`, `\`, пустые после фильтрации имена и зарезервированные имена Windows; возвращает нормализованное имя или `None` (корень).
- `is_safe_path(path, root)` — защита от path traversal через `resolve()`.
- `relative_path(path, root)` — POSIX-строка относительно `root`.
- `resolve_note_path(path, notes_dir)` — резолвит относительный или абсолютный путь заметки; `ValueError`, если путь вне `notes_dir`.
- `ensure_note_file(candidate, path_repr)` — `FileNotFoundError` с направляющим текстом: «'path' — это путь к файлу, не заголовок; вызови сначала list_notes или read_notes».
- `find_notes_by_title(title, notes_dir)` — заметки, чей заголовок совпадает без учёта регистра.
- `resolve_note_file(path_repr, notes_dir)` — основной резолвер для `update_note`/`move_note`/`delete_note`. Порядок: файл по пути существует → вернуть; иначе поиск по заголовку (вся строка), затем по базовому имени последней компоненты (без `.md`). Ровно одно совпадение → вернуть (с записью в лог); несколько → `FileNotFoundError` со списком кандидатов; ноль → направляющая ошибка. Фолбэк закрывает устойчивое поведение 7B передавать заголовок вместо пути (C9).

### `stub.py`

`echo(text)` — только для тестов оркестратора.

### `save_note.py`

- `save_note(title, content, notes_dir, category=None) -> dict`. Пустой `title` → `ValueError`.
- `validate_category(category)`: категория → подпапка `notes_dir/<category>/`, `mkdir(parents=True, exist_ok=True)`.
- Slug: lower, пробелы → `_`, удаление `<>:"/\|?*` и управляющих, сохранение Unicode, обрезка до 100, `rstrip(" .")`, префикс `_` для Windows-зарезервированных (`_WINDOWS_RESERVED` в нижнем регистре — сравнение после `lower()`). Пустой slug → `"note"`.
- Существующий файл → `_1`, `_2`, … Никогда не перезаписывает.
- `# {title}\n\n{content}\n`, UTF-8.
- Возвращает `{"path": относительный от notes_dir, "title", "category"}`.
- В промпте `title` — «do NOT invent one — ask the user for clarification»; `category` — «не выдумывай, если пользователь не назвал».
- `SAVE_NOTE_TOOL(needs_notes_dir=True)`.

### `read_notes.py`

- `read_notes(query="", notes_dir=None, max_results=50)`. `None` → 50, `<= 0` → `[]`. `notes_dir=None` → `Path("data/notes")`.
- Фильтр по `title` и `path.name` через `find_match`. Обход рекурсивный (категории).
- Возвращает `{"path" (относительный), "title", "category", "preview"}`.
- Описание инструмента ограничено 400 символами (шаг 6.4) — расширения формулировать коротко.
- `READ_NOTES_TOOL(needs_notes_dir=True)`.

### `search_notes.py`

- `search_notes(query, notes_dir, max_results=5)`. `None` → 5, `<= 0` → `[]`.
- `find_match_with_kind(body, query)`; для `kind="stem"` `matches` считается через `re.findall(rf"\b{re.escape(stem(query.lower()))}", body.lower())`.
- Snippet: строка с совпадением ± одна до и одна после, суффикс `"…"` при обрезке или при контенте после.
- `{"path" (относительный), "title", "category", "snippet", "matches"}`. Чтение прекращается при `max_results`.
- Известное ограничение стеммера (C10): многословный запрос стеммится целиком («текст два» → «текст»); словоформы с изменением 5-го символа («единый»/«единого») не склеиваются.
- `SEARCH_NOTES_TOOL(needs_notes_dir=True)`.

### `list_notes.py`

- `list_notes(notes_dir, category=None, max_results=50)` — список заметок, опционально из одной категории. `category` через `validate_category`; несуществующая категория → `[]`.
- Возвращает `{"path" (относительный), "title", "category", "modified" (ISO, секунды), "size_chars"}`.
- `LIST_NOTES_TOOL(needs_notes_dir=True)`. Триггеры: «покажи все заметки», «заметки в категории».

### `update_note.py`

- `update_note(path, notes_dir, title=None, content=None) -> dict`.
- Оба аргумента `None` → `ValueError("Nothing to update...")`; пустой `title` → `ValueError`.
- Резолв через `resolve_note_file` (фолбэк по заголовку). Нет файла → `FileNotFoundError`; не `.md` → `ValueError`.
- `title` заменяет заголовок, `content` ПОЛНОСТЬЮ заменяет тело (не дополняет). Если `content` начинается с `# ` — первая строка убирается (дубль заголовка).
- Файл НЕ переименовывается и НЕ перемещается при смене заголовка — осознанно (предсказуемость для модели и простота).
- Возвращает `{"path", "title", "size_chars"}`.
- Описание `path`: «FILE PATH ... NOT the note title» + фолбэк по заголовку заявлен явно.
- `UPDATE_NOTE_TOOL(needs_notes_dir=True)`.

### `delete_note.py`

- `delete_note(path, notes_dir, trash_dir) -> dict`.
- Резолв через `resolve_note_file`; нет файла → `FileNotFoundError`.
- Перемещение `shutil.move` в `trash_dir/notes/<категория>/<ГГГГММДД_ЧЧММСС>_<имя>`; структура категорий сохраняется; при коллизии — суффикс `_1`, `_2`. Физического удаления нет.
- Возвращает `{"path" (относительный), "moved_to" (абсолютный)}`.
- `DELETE_NOTE_TOOL(needs_notes_dir=True, needs_trash_dir=True)`.

### `move_note.py`

- `move_note(path, category, notes_dir) -> dict`.
- Резолв через `resolve_note_file`; `validate_category(category)`; `None`/`""` → корень.
- Уже в целевой категории → `moved=False`, файл не трогается.
- Конфликт имени в целевой категории → суффикс `_1`, `_2`; `shutil.move`.
- Возвращает `{"path" (новый относительный), "category", "moved"}`.
- `MOVE_NOTE_TOOL(needs_notes_dir=True)`.

### `list_categories.py`

- `list_categories(notes_dir)` — подпапки верхнего уровня `notes_dir` + число заметок в каждой (рекурсивно); первой строкой — заметки без категории (`name=""`).
- Нет `notes_dir` → `[]`.
- `LIST_CATEGORIES_TOOL(needs_notes_dir=True)`.

### `search_documents.py` (фабрика, T34)

- `_RagContext(index_dir, embedding_model)` — ленивая загрузка `VectorStore` и `Embedder` в `_ensure_loaded()`. Свойства `store` и `embedder` триггерят загрузку. Никакого глобального состояния — два вызова фабрики дают два независимых контекста.
- `make_search_documents_tool(config) -> ToolDefinition` — создаёт `_RagContext` в замыкании.
- `search_documents(query, top_k=5)` внутри фабрики: пустой query → `[]` без загрузки; иначе `embedder.embed_one(query)` → `store.search_hybrid(query, query_vec, top_k)`.
- Возвращает `{"path", "section", "text", "score"}`. `score` — RRF-score (0.01–0.05, не cosine).
- `FileNotFoundError` из `VectorStore.load` пробрасывается — `AgentService` ловит как `FinalEvent(error=...)`.
- `SEARCH_DOCUMENTS_TOOL(needs_notes_dir=False, needs_output_dir=False)`.

### `read_document.py`

- `read_document(path, max_chars=4000) -> dict`.
- Путь: абсолютный — как есть; относительный — от `_PROJECT_ROOT`; `resolve()`. Вне `_PROJECT_ROOT` → `ValueError("path must be inside project: ...")` (path traversal защита).
- Нет файла → `ValueError("cannot read ...: file does not exist")`.
- Нет экстрактора для suffix → `ValueError("no extractor for suffix ...")`.
- `extract_text` вернул `None` → `ValueError("cannot read ...: extraction failed")`.
- Склейка: `## {section}\n\n{text}` для каждого сегмента с непустым `text`, через `\n\n`. Пустые сегменты (скан-PDF) пропускаются.
- `total = len(text)`; если `> max_chars` → `text[:max_chars]`, `truncated=True`.
- Возвращает `{"path", "text", "truncated", "total_chars", "suffix"}`.
- `READ_DOCUMENT_TOOL(needs_notes_dir=False, needs_output_dir=False)`.

### `write_document.py`

- `write_document(title, content, output_dir) -> dict`.
- Если `content.lstrip()` начинается с `#`, первая строка убирается (дубль `# title`, `save_note` добавит сам).
- `save_note(title, content, output_dir)` — переиспользование slug/защиты от перезаписи; результат-`dict` склеивается в абсолютный путь (`output_dir / result["path"]`) — внешний контракт `write_document` не менялся.
- Возвращает `{"path" (абсолютный), "title", "size_chars"}`.
- `WRITE_DOCUMENT_TOOL(needs_output_dir=True)`.

## Извлечение текста (`src/agent/extractors/`)

Реестр экстракторов — расширяемая архитектура для новых форматов без изменения RAG.

### `base.py`

- `Segment`: `text`, `section` (заголовок раздела или `None`).
- `ExtractedDocument`: `path`, `segments`, `metadata`.
- `TextExtractor` — протокол: `supported_suffixes() -> set[str]`, `extract(path) -> ExtractedDocument | None`.

### `__init__.py`

- `EXTRACTORS: dict[str, TextExtractor]`.
- `register(suffixes, extractor)` — нормализует суффикс (lower, с точкой), `ValueError` на дубликат.
- `extract_text(path)` — диспатчер по suffix. Нет экстрактора → warning и `None`. Исключение → `logger.exception` и `None`. Один битый файл не роняет обход.

Регистрация всех — в конце файла. Новый формат = новый модуль + одна строка `register(...)`.

### `markdown.py`

`.md`, `.markdown`. Чтение `utf-8-sig` → cp1251 → `None`. Разбиение по `^#{1,6}\s+(.+)$`. Текст до первого заголовка — сегмент с `section=None`. Очистка: fenced code blocks, inline code, изображения, разворот ссылок, inline-разметка, HTML-теги, нормализация пробелов. Пустые сегменты пропускаются.

### `txt.py`

`.txt`. Один сегмент с `section=None`. Чтение `utf-8-sig` → cp1251 → `None`.

### `pdf.py`

`.pdf` через PyMuPDF (`import pymupdf`, не `import fitz` — `fitz` deprecated). `pymupdf.open(path)`; `FileDataError` / `FileNotFoundError` / `RuntimeError` (пароль) → warning и `None`. Для каждой страницы: `page.get_text("text").strip()`; пустой → страница пропускается (скан). Иначе `Segment(text, section=f"Страница {i}")`. `metadata={"pages": total, "suffix": ".pdf"}`. `try/finally: doc.close()`.

## Индексатор (`src/agent/indexer.py`)

- `IndexResult` — `files_found`, `files_processed`, `files_skipped`, `segments_total`, `files_with_zero_segments`. `summary()` для печати.
- `iter_document_files(root)` — `sorted(root.rglob("*"))`, фильтр по `suffix in EXTRACTORS`.
- `index_documents(root, logger, on_progress=None)` — обход, `extract_text`, подсчёт. `on_progress` — колбэк для печати.

На этапе C: `build_index(..., incremental=True)` — `data/index/meta.json` хранит `{path: {mtime, size, hash, chunk_count}}`. Новые → добавить, изменённые → удалить старые чанки + добавить, удалённые → удалить чанки, неизменённые → пропустить.

## RAG (`src/agent/rag/`)

### `chunker.py`

- `Chunk` — `text`, `path`, `section`, `chunk_index`.
- `split_text(text, chunk_size, overlap)` — скользящее окно с попыткой не рвать на полуслове.
- `chunk_document(doc, chunk_size, overlap)` — режет сегменты; `chunk_index` глобальный по документу.

### `embedder.py`

`Embedder(model_name)` — ленивая загрузка `SentenceTransformer`. `embed(texts)` → `np.ndarray` `(N, D)`, `float32`, L2-нормализовано. `embed_one(text)` → `(D,)`. Пустой вход → `(0, 0)` без загрузки.

### `bm25.py`

- `BM25Index(chunks, k1=1.5, b=0.75)` — строится из чанков при `VectorStore.load`.
- `_tokenize`: lower + regex `[а-яёa-z0-9]+`, затем `stem(t)` из `src/agent/stem.py`.
- IDF сглаженный: `log((N - df + 0.5) / (df + 0.5) + 1)`.
- `_chunk_text`: `section + text` — заголовок даёт лексический буст.
- `search(query, top_k, min_idf=2.0)` — отбрасывает токены запроса с IDF ниже порога. Если все ниже — fallback на оригинальные.

На этапе C: метод `remove_by_path(path)` для инкрементальной индексации.

### `stem.py` (в `src/agent/`, не в `rag/`)

`stem(token)` — если `len <= 5` — как есть; иначе `token[:5]`. Сводит «установить»/«установка» → «устан». Используется в BM25 (`_tokenize`) и в `find_match` (`_search.py`). Ограничения — в `TODO.md` (C2, C10).

### `store.py`

- `VectorStore(vectors, chunks, meta)` — numpy-хранилище.
- `save(directory)` — `vectors.npy`, `chunks.json`, `meta.json`.
- `load(directory)` — читает три файла, строит `BM25Index` из `chunks`. Нет `vectors.npy` → `FileNotFoundError`.
- `search(query_vector, top_k)` — чистый векторный поиск.
- `search_hybrid(query_text, query_vector, top_k=5, candidate_k=20, rrf_k=60)` — `if not query_text.strip(): return []`; кандидаты от vector и BM25; RRF: `score(chunk) = Σ 1 / (rrf_k + rank_i)`.

На этапе C: `remove_by_path(path) -> VectorStore` — фильтрация `vectors` и `chunks`.

### `build.py`

- `build_index(root, config, reset=False, batch_size=32, logger=None) -> VectorStore` — чистая функция, без `sys.exit`. Нет `root` → `FileNotFoundError`. Существующий индекс без `reset` → `FileExistsError`. Пустой корпус → пустой `VectorStore` без записи.

На этапе C: `incremental=True` — читает `data/index/meta.json`, сравнивает mtime/size/hash, обновляет только изменённые файлы. Запись индекса — атомарно (`os.replace`).

- `main()` — CLI-обёртка (deprecated; основной путь — `python -m agent index`).

## Память

Долговременной памяти «агент помнит прошлые сессии» нет. Контекст задачи живёт в `messages` внутри одного `Orchestrator.run`. История действий пишется в лог, но не используется моделью. В `chat` каждая цель также начинается с чистого контекста — пути к заметкам модель должна получать из результатов инструментов (или через фолбэк по заголовку).

Долговременная память для документов — RAG-индекс: эмбеддинги чанков в `data/index/`. Агент «помнит» содержимое документов не в модели, а в индексе — `search_documents` находит релевантные чанки заново при каждом запросе.

Планируется:

- краткосрочная память: расширение `messages` (уже есть);
- память между сессиями для заметок: сейчас `data/notes/` — файлы, `read_notes`/`search_notes`/`list_notes` работают по ним каждый раз;
- векторное хранилище: numpy `VectorStore` (`data/index/`). ChromaDB/FAISS — при росте корпуса.

## Статусы `tool_result` в истории

После вызова инструмента в `messages` добавляется пара `assistant(tool_call) + user(tool_result)`. У `tool_result` три статуса:

| Статус | Когда | Что видит модель |
| --- | --- | --- |
| `SUCCESS` | Инструмент вернул результат | `tool_result: SUCCESS. <name> returned: <result>. If this satisfies the user's goal, respond with a final answer now.` |
| `ERROR` | Инструмент бросил исключение или исчерпал `max_tool_failures` | `tool_result: ERROR. <name> failed: <result>. Read the error message carefully: it explains what is wrong. Fix the arguments or use another tool, then try again.` |
| `SKIPPED` | Тот же вызов с теми же аргументами уже был успешно выполнен | `tool_result: SKIPPED. <name> was not executed again... Respond with a final answer now.` |

Три статуса вместо одного `SUCCESS`/`ERROR` — следствие ревью (шаг 6.5, T1). Текст `ERROR` изменён в этапе B: раньше он предлагал «завершить задачу, если цель достигнута», что подталкивало модель сдаться после первой ошибки.

## Инструменты: статус

| Инструмент | `needs_notes_dir` | `needs_output_dir` | `needs_trash_dir` | Статус |
| --- | --- | --- | --- | --- |
| `echo` | — | — | — | готов (только тесты) |
| `save_note` | ✅ | — | — | готов (с категорией, возвращает `dict`) |
| `read_notes` | ✅ | — | — | готов (относительный путь + `category`) |
| `search_notes` | ✅ | — | — | готов (относительный путь + `category`) |
| `list_notes` | ✅ | — | — | готов |
| `update_note` | ✅ | — | — | готов (фолбэк по заголовку) |
| `delete_note` | ✅ | — | ✅ | готов (в корзину, фолбэк по заголовку) |
| `move_note` | ✅ | — | — | готов (фолбэк по заголовку) |
| `list_categories` | ✅ | — | — | готов |
| `search_documents` | — | — | — | готов (фабрика) |
| `read_document` | — | — | — | готов |
| `write_document` | — | ✅ | — | готов |

`build_tools(config)` собирает все 11 готовых. `tool_context` — только для инструментов с флагами. `search_documents` и `read_document` — без контекста.

Единый контракт заметок: все инструменты заметок возвращают пути относительно `data/notes/` (POSIX-слэши) и поле `category` (`None`/отсутствие — корень). Результат любого инструмента можно передать в `update_note`/`move_note`/`delete_note` без преобразований.

## Гибридный поиск (детали)

`search_hybrid` объединяет два ранжирования через Reciprocal Rank Fusion:

- Векторный поиск: косинус между эмбеддингом запроса и эмбеддингами чанков.
- BM25: лексическое совпадение токенов (со стеммингом) с IDF-взвешиванием.

Почему RRF, а не взвешенная сумма score: BM25 неограничен сверху, cosine ∈ [−1, 1]. Нормализация на малом корпусе нестабильна. RRF использует ранги, а не score.

Формула: `score(chunk) = Σ 1 / (k + rank_i)`, `k = 60`, `rank_i` — позиция чанка в i-м списке (1-based).

Кандидаты: каждый поиск возвращает `candidate_k = max(top_k * 4, 20)`. RRF объединяет, возвращается `top_k`.

Ограничение (C5): vector доминирует на семантически близких запросах («как установить» vs «как понять, что агент…»). Причина — модель, не размер корпуса (проверено на 94 и 3116 чанках). Обход — уточнять запрос; долгосрочно — e5-small или реранкер.

## Модель: 3B vs 7B

Основная — `qwen2.5-7b-agent`. 3B — опция.

|  | 3B | 7B |
| --- | --- | --- |
| Routing | 4/7 | 7/7 |
| Synthesis | 2/7 | 6/7 |
| Скорость (CPU) | 1–2 мин | 2–4 мин |
| RAM | ~2–3 ГБ | ~6 ГБ |

Почему 7B: на 7 вопросах 3B не вызывала `search_documents` в 3 случаях. 7B вызвала правильно во всех 7. Дальнейшие итерации промптов для 3B — тупик; 7B — решение на данных.

Переключение: `[llm] model` в `config/settings.toml`. Индекс RAG и BM25 не зависят от LLM — переиндексация не нужна.

Оптимизация скорости (`TODO.md`): `llama.cpp` (−20–30%), `Q4_0` вместо `Q4_K_M` (−10–15%), `num_ctx=4096` (−5–10%), интерактивный режим.

## Изоляция и сетевая безопасность

Агент работает в изолированной среде:

- Ollama — на `localhost`, без внешних вызовов.
- RAG-индекс, заметки, документы, корзина — на диске пользователя.
- Никакие данные не отправляются в интернет. Нет Telegram, мессенджеров, облачных API, планов по работе с фото.
- Web UI — только локальная сеть, без аутентификации. Осознанное решение (C8 в `TODO.md`). Не открывать порт 8000 в интернет.

При старте `python -m agent web` с `host=0.0.0.0` в лог пишется предупреждение: «Web UI доступен по локальной сети БЕЗ аутентификации. Любой, кто в вашей сети, может пользоваться агентом. Не открывайте порт в интернет».

## Ограничения текущей версии

- **7B на CPU — медленно.** 1.5–4 минуты на вопрос при `num_ctx=8192`. Холодный старт первой сессии — >5 минут (таймаут клиента 900 с; кандидат в конфиг — T35). Оптимизация — в `TODO.md`.
- **Web UI без аутентификации.** Доступен по LAN любому. Не открывать в интернет. См. «Изоляция и сетевая безопасность».
- **Web UI: SSE по шагам, но не стриминг токенов.** Ответ появляется в конце генерации. Прогресс «[шаг 1] модель думает… → tool_result → Готово» виден, но сам текст — нет.
- **C5: hybrid search доминируется vector** на семантически близких запросах. Обход — уточнять запрос; долгосрочно — e5-small/реранкер.
- **C6: 7B галлюцинирует в содержании при генерации по шаблону.** Обход — уточнять конкретику в задаче; в UI (этап D) — предупреждение «проверьте факты».
- **C7: 7B возвращает 2 `tool_calls`, используется первый.** Связано с C3 (один tool call за шаг).
- **C9: 7B передаёт заголовок заметки вместо пути** в `update_note`/`move_note`/`delete_note`. Закрыто фолбэком `resolve_note_file`; при неоднозначных заголовках инструмент возвращает список кандидатов. Промпт-итерации против этого поведения не сработали (урок в `TODO.md`).
- **C10: стеммер** — многословные запросы стеммятся целиком; словоформы с изменением 5-го символа не склеиваются. Обход — запрос словом из текста.
- **Галлюцинации на неполных запросах.** На «Запиши заметку в файл» без содержания модель может придумать заголовок. Промпт `save_note` просит уточнения, но не устраняет полностью.
- **Дрейф 7B в другие языки** в финалах после ошибок/неоднозначностей. Ограничение модели; снижается с уменьшением числа ошибок.
- **`update_note` заменяет тело целиком.** «Дополнить заметку» без чтения текущего тела невозможен; инструмента дописывания нет (осознанно).
- **Корзина без инструмента восстановления.** Восстановление из `data/trash/notes/` — вручную.
- **Прямой REST API для заметок отсутствует** — остаток этапа B. CRUD через агента работает, но прямой путь — мгновенный и предсказуемый — появится вместе с вкладкой «Заметки».
- **RAG только Markdown/TXT/PDF.** DOCX/HTML/EPUB — в планах.
- **Скан-PDF не извлекается.** Нужен OCR (отдельный шаг, документы).
- **Индекс RAG не инкрементальный.** Любое изменение корпуса — `python -m agent index --reset`. Этап C.
- **`ask` может ошибаться на общих знаниях.** Ограничение 7B, не проекта.
- **`confirm_file_operations` читается, но не применяется.** `delete_note`/`move_note` работают без подтверждения; страховка — корзина.
- **Один агент, без мультиагентности.** Без самодописывания кода.
- **Нет автоматического ретрая при сетевых ошибках Ollama.**
- **`search_notes.matches` для exact-совпадений** всё ещё `body.count(query)`.

## Принципы разработки

- **Маленькие шаги с тестами.** Каждый инструмент сначала покрывается unit-тестами без LLM, потом smoke с реальной моделью.
- **Детерминированные тесты.** Оркестратор и LLM-слой — `FakeLLM` и моки. RAG — мок `Embedder` и `tmp_path`. Web — `TestClient` + мок `AgentService`. Реальная модель — только в smoke.
- **Безопасность данных.** `data/` и `logs/` не попадают в git. Логи без полных текстов (`_summarize_for_log`). Path traversal защита в `read_document` и `resolve_note_path`.
- **Один инструмент за раз.** Не добавлять несколько инструментов в одном шаге (в этапе B сделано исключение для связки CRUD — покрыта общим тестовым файлом).
- **Пути от корня проекта, а не от CWD.**
- **Расширяемость через реестр.** Новый формат — модуль в `extractors/` + `register(...)`. Новый инструмент — `build_tools` в одном месте.
- **Библиотека бросает исключения, `sys.exit` — только в `main`.**
- **Один источник правды.** `build_tools(config)` — единственное место со списком инструментов; `category_of` — единственное место вычисления категории; `resolve_note_file` — единственный резолвер пути заметки для CRUD; `RAGConfig()` — дефолты RAG.
- **Few-shot без синтаксиса вызова.** Новые правила промпта — текстом, без `tool_name(...)`. Тесты `test_system_prompt_does_not_contain_write_document_few_shot` и `test_system_prompt_no_call_syntax_for_crud_tools` страхуют.
- **В промпте не бывает реальных путей.** Примеры вида `'категория/имя_файла'` — абстрактные: модель копирует буквальные примеры вместо поиска. Тест `test_system_prompt_does_not_contain_real_note_paths`.
- **Лимиты описаний инструментов.** `read_notes` — ≤400 символов (маршрутизация малых моделей, шаг 6.4). Расширения — аддитивные и короткие.
- **Инженерная защита против поведения модели.** Если поведение 7B стабильно плохое (заголовок вместо пути, нет восстановления после ошибки) — защита переносится в код инструмента (фолбэк), а не в очередную итерацию промпта.
- **Прямой API для CRUD, агент для естественного языка.** Прямой REST для заметок — остаток этапа B. Агент — для «сохрани заметку про X» и «найди, что я писал про Y».
- **Удаление — в корзину, не физически.** `delete_note` перемещает в `data/trash/notes/` с таймстампом; восстановление — вручную. На этапе C та же схема для документов.
- **Изоляция по умолчанию.** Никаких внешних вызовов, кроме Ollama на `localhost`. Web UI — только LAN, с предупреждением.