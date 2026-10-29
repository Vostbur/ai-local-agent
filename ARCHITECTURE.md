# Архитектура

## Общая схема

Пользователь ставит цель (текстом).
Оркестратор передаёт цель локальной LLM.
LLM либо возвращает финальный ответ, либо просит вызвать инструмент.
Оркестратор вызывает инструмент и возвращает результат в LLM.
Цикл повторяется до финала или до лимита шагов.

## Текущее состояние (после шага 7.5)

Реализовано и работает:

- загрузка конфигурации из TOML; относительные пути в `[paths]` резолвятся от корня проекта, а не от CWD;
- `pyproject.toml` с `pythonpath = ["."]` — тесты запускаются из любой папки;
- логирование в файл и консоль; полные результаты инструментов в лог не пишутся;
- реестр инструментов и единый `ALL_TOOLS` в `build_orchestrator`;
- протокол LLM и фейковая LLM для тестов;
- подключение к реальной Ollama через OpenAI-совместимый endpoint; устойчивость к битому JSON, пустым `choices`, нескольким `tool_calls`;
- оркестратор с лимитом шагов, защитой от повторных вызовов, лимитом падений, тремя статусами `tool_result` и инъекцией контекста инструментов;
- инструмент `save_note` с защитой от перезаписи и Windows-безопасным slug;
- инструменты `read_notes` и `search_notes` (поиск по заголовкам и по содержимому, `max_results=None` и `<= 0` обрабатываются корректно);
- RAG по Markdown и TXT-документам: реестр экстракторов, чанкинг с перекрытием, эмбеддинги через `paraphrase-multilingual-mpnet-base-v2`, numpy-хранилище, гибридный поиск (BM25 + векторный через RRF), инструмент `search_documents`;
- основная модель — `qwen2.5-7b-agent` (routing инструментов 7/7 в контрольном прогоне). 3B (`qwen2.5-3b-agent`) — опция для случаев, когда скорость важнее надёжности routing.

Пока не реализовано:
- работа с PDF/DOCX/HTML (сейчас RAG работает только на Markdown и TXT);
- работа с изображениями;
- генерация новых документов по шаблону;
- подтверждение опасных операций через CLI (`confirm_file_operations` читается, но не применяется — появится в шаге 8).

## Компоненты

### Оркестратор (`src/agent/orchestrator.py`)

- Управляет циклом «рассуждение → действие → наблюдение».
- Ограничивает число шагов (`max_steps`, по умолчанию 10).
- Логирует каждый шаг: тип ответа LLM, имя инструмента, краткий результат (`_summarize_for_log`).
- Поддерживает `tool_context` — словарь `{имя_инструмента: {доп_аргументы}}`. Эти аргументы **добавляются** к тем, что передала LLM, и перекрывают их. Так пути (`notes_dir`) передаются из конфига, а не из модели.
- Хранит `executed_calls` (успешные вызовы) и `failed_calls` (счётчик ошибок по ключу вызова). Повторный успешный вызов → `SKIPPED`; после `max_tool_failures` неудач → `ERROR` с «giving up».
- `max_tool_failures` приходит из `SafetyConfig.max_tool_retries` (по умолчанию 2).
- Ловит исключения инструментов и возвращает их в LLM как `ERROR: ...`, не роняя цикл.
- При неизвестном `response.type` возвращает `OrchestratorResult(success=False, error=...)`, а не крутит цикл до `MaxStepsExceeded`.
- При превышении лимита шагов выбрасывает `MaxStepsExceeded`.

`SYSTEM_PROMPT` — результат итераций 6.1, 6.4, 7.2.1 и 7.2.2. Содержит:

1. Список инструментов с одной строкой описания каждого.
2. Правило «почти любой вопрос про проект, установку, требования, возможности, статьи, лицензию — это вопрос про документы → `search_documents`».
3. Few-shot примеры (10 пар «вопрос → инструмент»), включая провальные в 3B формулировки (версия Python, установка, запуск, лицензия).
4. Инструкцию «не выдумывай» — после `search_documents` отвечать только по фрагментам, при отсутствии ответа — честно сказать «в документах это не указано».

### LLM-слой

**`src/agent/llm.py`:**
- Датакласс `LLMResponse` с полями `type` (`"tool_call"` или `"final"`), `content`, `tool_name`, `tool_arguments`.
- Протокол `LLMClient` с методом `chat(messages) -> LLMResponse`.
- `FakeLLM` для детерминированных тестов: возвращает заранее заданные ответы, сохраняет переданные `messages` в `self.calls`.

**`src/agent/llm_ollama.py`:**
- Класс `OllamaLLM`, реализующий `LLMClient`.
- Использует **OpenAI-совместимый endpoint** `POST {base_url}/v1/chat/completions` — стабильнее нативного `/api/chat` для tool calling и совместим с `llama.cpp`.
- Передаёт инструменты в формате `{"type": "function", "function": {...}}`.
- Парсит `tool_calls` (аргументы приходят строкой JSON → `json.loads`).
- `temperature` и `max_tokens` передаются в payload только если заданы в конфиге (`None` → не передаются).
- Устойчив к «кривому» ответу: `JSONDecodeError`, пустые `choices`, отсутствие `message`, несколько `tool_calls` (берётся первый с warning), невалидный JSON в `arguments`, `arguments` уже словарём (не строка).
- Полный `messages` в лог не пишется — только `model`, `messages_count`, `last_role`, `last_len`.
- Таймаут 300 секунд (на CPU модель отвечает медленно).
- При сетевой ошибке выбрасывает `RuntimeError`.
- Модель выбирается в `config/settings.toml` (`[llm] model`). По умолчанию — `qwen2.5-7b-agent`: на CPU в 2–3 раза медленнее 3B, но routing инструментов значительно надёжнее (7/7 против 4/7 в контрольном прогоне из 7 вопросов).

### Реестр инструментов (`src/agent/registry.py`)

- `ToolDefinition`: имя, описание, JSON-схема параметров, функция-исполнитель.
- `ToolRegistry`: регистрация, получение по имени, список всех, вызов `call(name, **kwargs)`.
- Дубликат имени → `ValueError`. Неизвестное имя → `KeyError`.
- Агент **не пишет код инструментов**. Он выбирает из зарегистрированных. Новые инструменты добавляются вручную и покрываются тестами.
- В `src/agent/app.py` — единый `ALL_TOOLS` (сейчас 4 инструмента: `save_note`, `read_notes`, `search_notes`, `search_documents`), из него собираются реестр, `tools` для LLM и `tool_context`.

### Конфигурация (`src/agent/config.py`)

- `_PROJECT_ROOT = Path(__file__).resolve().parents[2]` — корень проекта.
- `_resolve_path(value)` — относительные пути резолвятся от `_PROJECT_ROOT`, абсолютные остаются как есть.
- Читает `config/settings.toml` через `tomllib` (стандартная библиотека Python 3.11+). По умолчанию ищет файл в `_PROJECT_ROOT / "config" / "settings.toml"` — **не зависит от CWD**.
- Датаклассы:
  - `LLMConfig` — `model`, `base_url`, `temperature`, `max_tokens`, `max_steps`. Поле `provider` удалено (T27) — клиент сейчас только `OllamaLLM`. Вернётся в шаге 9, при подключении `llama.cpp`.
  - `PathsConfig` — `data_dir`, `notes_dir`, `inbox_dir`, `photos_dir`, `documents_dir`, `index_dir`, `logs_dir`, `memory`, `tools`. Все относительные пути — от `_PROJECT_ROOT`.
  - `SafetyConfig` — `confirm_file_operations` (читается, но не применяется до шага 8), `max_tool_retries`. Поля `allow_shell`/`allow_network` удалены (T21) — они не использовались.
  - `RAGConfig` — `embedding_model`, `chunk_size`, `chunk_overlap`, `top_k`. Параметры RAG вынесены из `LLMConfig`, потому что не зависят от модели.
  - `AppConfig` — обёртка над всеми четырьмя.
- `load_config()` выбрасывает `FileNotFoundError` или `ValueError` с понятным сообщением.

### Логирование (`src/agent/logging_setup.py`)

- Один логгер с именем `"agent"`.
- Два обработчика: файл `logs/agent.log` (UTF-8, append) и консоль.
- Формат: `%(asctime)s | %(levelname)s | %(name)s | %(message)s`.
- Повторный вызов не добавляет дубликаты обработчиков.
- Полные результаты инструментов не логируются: `_summarize_for_log` в оркестраторе сворачивает списки в `list[N]`, `Path` оставляет как строку, длинные строки — обрезает. Для `search_documents` это значит, что в лог попадает `list[5]`, а не тексты чанков.

### Инструменты (`src/agent/tools/`)

**`_search.py`** (общие хелперы для заметок):
- `find_match_with_kind(text, query)` — точное вхождение, затем fallback на стем (`query[:-2]`) для запросов длиной ≥ 5; возвращает `(start, end, kind)`, где `kind` — `"exact"` или `"stem"`.
- `find_match(text, query)` — обёртка, возвращает `(start, end)`.
- `iter_md_files(notes_dir)` — отсортированный список `*.md` в каталоге.
- `load_note(path)` — `{"title": ..., "body": ...}` или `None` при ошибке чтения.

**`stub.py`:**
- `echo(text)` — тестовый инструмент. Используется только в тестах оркестратора.

**`save_note.py`:**
- `save_note(title, content, notes_dir) -> Path`.
- Пустой `title` → `ValueError`.
- Slug: нижний регистр, пробелы → `_`, удаление `<>:"/\|?*` и управляющих символов, сохранение Unicode, обрезка до 100 символов, `rstrip(" .")`, экранирование зарезервированных Windows-имён (`CON`, `NUL`, `COM1..9`, `LPT1..9`) префиксом `_`. Пустой slug → `"note"`.
- Если файл существует — добавляет `_1`, `_2`, … Никогда не перезаписывает.
- Содержимое: `# {title}\n\n{content}\n`, UTF-8.
- В промпте `title` — «if the user did not specify an explicit title, do NOT invent one — ask the user for clarification instead» (шаг 6.7, T26).

**`read_notes.py`:**
- `read_notes(query="", notes_dir=None, max_results=50)`.
- `notes_dir=None` → `Path("data/notes")`.
- `max_results=None` → дефолт 50; `<= 0` → `[]`. Это защита от модели, которая передаёт `null` для опциональных полей.
- `query=""` → вернуть все заметки, иначе фильтр по `title` и `path.name` через `find_match`.
- Возвращает `{"path", "title", "preview"}`.

**`search_notes.py`:**
- `search_notes(query, notes_dir, max_results=5)`.
- `max_results=None` → дефолт 5; `<= 0` → `[]`.
- `find_match_with_kind(body, query)`; для `kind="stem"` `matches` считается по `\b`-границе, чтобы «недокументированный» не считался за «документ».
- Snippet: строка с совпадением ± одна до и одна после, суффикс `"…"` при обрезке или при наличии контента после.
- Возвращает `{"path", "title", "snippet", "matches"}`.
- Чтение прекращается, когда набрано `max_results`.

**`search_documents.py`** (RAG):
- `search_documents(query, top_k=5) -> list[dict]`.
- Ленивая загрузка `_rag_service = (VectorStore, Embedder)` при первом вызове. `config = load_config()`, `VectorStore.load(config.paths.index_dir)`, `Embedder(config.rag.embedding_model)`.
- Пустой `query` → `[]` без загрузки модели.
- Вызывает `store.search_hybrid(query, query_vec, top_k=top_k)` — гибридный поиск.
- Возвращает `{"path", "section", "text", "score"}`. `score` — RRF-score (маленькие числа 0.01–0.05, не cosine).
- Если индекс не найден — `FileNotFoundError` пробрасывается, оркестратор ловит как `ERROR` и возвращает модели `tool_result: ERROR. search_documents returned: ERROR: index not found...`.
- `_reset_rag_service()` — для тестов.

### RAG (`src/agent/rag/`)

**`chunker.py`:**
- `Chunk` — датакласс: `text`, `path`, `section`, `chunk_index`.
- `split_text(text, chunk_size, overlap)` — скользящее окно с попыткой не рвать на полуслове (ищет `. `, `\n\n`, `\n`, ` ` в последних 200 символах).
- `chunk_document(doc, chunk_size, overlap)` — режет `ExtractedDocument` на чанки. `chunk_index` глобальный по документу.

**`embedder.py`:**
- `Embedder(model_name)` — ленивая загрузка `SentenceTransformer`. Модель грузится при первом `embed`/`embed_one`.
- `embed(texts)` → `np.ndarray` `(N, D)`, `float32`, L2-нормализовано (`normalize_embeddings=True`).
- `embed_one(text)` → `(D,)`.
- Пустой вход → `(0, 0)` без загрузки модели.

**`bm25.py`:**
- `BM25Index(chunks, k1=1.5, b=0.75)` — строится из чанков при загрузке `VectorStore`.
- Токенизация: lower + regex `[а-яёa-z0-9]+`. Пунктуация отбрасывается.
- IDF сглаженный: `log((N - df + 0.5) / (df + 0.5) + 1)`.
- `_chunk_text` использует `section + text` — заголовок раздела даёт лексический буст («требования» матчит «Требования»).
- `search(query, top_k)` → `[(chunk, score)]`, только чанки со score > 0.

**`store.py`:**
- `VectorStore(vectors, chunks, meta)` — numpy-хранилище.
- `save(directory)` — пишет `vectors.npy`, `chunks.json`, `meta.json`.
- `load(directory)` — читает три файла, строит `BM25Index` из `chunks`. При отсутствии `vectors.npy` — `FileNotFoundError` с понятным текстом.
- `search(query_vector, top_k)` — чистый векторный поиск (косинус через скалярное произведение нормализованных векторов). Используется в `search_hybrid` и в тестах.
- `search_hybrid(query_text, query_vector, top_k=5, candidate_k=20, rrf_k=60)` — гибридный поиск:
  - `if not query_text.strip(): return []`.
  - Берёт `candidate_k` кандидатов от векторного и от BM25.
  - Объединяет через RRF: `score(chunk) = Σ 1 / (rrf_k + rank_i)`.
  - Возвращает `top_k` с наибольшим RRF-score.
- BM25 на диск не пишется — пересчитывается при `load`. Для 1000 чанков это миллисекунды.

**`build.py`:**
- `build_index(root, config, reset=False, batch_size=32, logger=None) -> VectorStore` — чистая функция, без `sys.exit`.
- При отсутствии `root` → `FileNotFoundError`. При существующем индексе без `reset` → `FileExistsError`. При пустом корпусе → пустой `VectorStore` без записи на диск.
- Обходит `iter_document_files(root)`, `extract_text(path)`, `chunk_document(...)`, `embedder.embed(texts)`, `store.save(config.paths.index_dir)`.
- `main()` — CLI-обёртка с `argparse`, ловит `FileNotFoundError`/`FileExistsError` → `sys.exit(1)`.

### Извлечение текста (`src/agent/extractors/`)

Реестр экстракторов — расширяемая архитектура для добавления новых форматов без изменения RAG.

**`base.py`:**
- `Segment` — датакласс: `text`, `section` (заголовок раздела, `None` если нет).
- `ExtractedDocument` — датакласс: `path`, `segments`, `metadata` (dict для будущих полей: page, mtime, suffix).
- `TextExtractor` — протокол: `supported_suffixes() -> set[str]`, `extract(path) -> ExtractedDocument | None`.

**`__init__.py`:**
- `EXTRACTORS: dict[str, TextExtractor]` — плоский словарь «расширение → экстрактор».
- `register(suffixes, extractor)` — нормализует суффикс (lower, с точкой), `ValueError` при дубликате.
- `extract_text(path)` — диспатчер по suffix. Нет экстрактора → warning и `None`. Исключение экстрактора → `logger.exception` и `None`. Один битый файл не роняет обход.
- Регистрация всех экстракторов — в конце `__init__.py`. Новый формат = новый модуль + одна строка `register(...)`.

**`markdown.py`:**
- `MarkdownExtractor` для `.md`, `.markdown`.
- Чтение: `utf-8-sig` → cp1251 → `None` с warning.
- Разбиение по заголовкам `^#{1,6}\s+(.+)$`. Текст до первого заголовка — сегмент с `section=None`.
- Очистка тела: вырезать fenced code blocks, inline code, изображения, развернуть ссылки `[text](url)` → `text`, убрать inline-разметку `**`/`*`/`_`/`~~`, вырезать HTML-теги, нормализовать пробелы.
- Пустые сегменты пропускаются.

**`txt.py`:**
- `TxtExtractor` для `.txt`. Один сегмент с `section=None`, нормализация пробелов.
- Чтение: `utf-8-sig` → cp1251 → `None`.

### Индексатор (`src/agent/indexer.py`)

- `IndexResult` — датакласс для статистики: `files_found`, `files_processed`, `files_skipped`, `segments_total`, `files_with_zero_segments`. Метод `summary()` для печати.
- `iter_document_files(root)` — `sorted(root.rglob("*"))`, фильтр по `suffix in EXTRACTORS`.
- `index_documents(root, logger, on_progress=None)` — обход, вызов `extract_text`, подсчёт статистики. `on_progress` — колбэк для печати прогресса. Не падает на битых файлах (они идут в `files_skipped`).

## Память

Пока нет долговременной памяти в смысле «агент помнит прошлые сессии». Контекст задачи живёт в `messages` внутри одного вызова `Orchestrator.run`. История действий пишется в лог, но не используется моделью.

Долговременная память для документов — это RAG-индекс: эмбеддинги чанков в `data/index/`. Агент «помнит» содержимое документов не в модели, а в индексе — при каждом запросе `search_documents` находит релевантные чанки заново.

Планируется:
- краткосрочная память: расширение `messages` (уже есть);
- память между сессиями для заметок: сейчас `data/notes/` — это файлы, `read_notes`/`search_notes` работают по ним каждый раз;
- векторное хранилище: numpy `VectorStore` (плоский файл `data/index/`). ChromaDB или FAISS — при росте корпуса (десятки тысяч чанков).

## Статусы `tool_result` в истории

После вызова инструмента в `messages` добавляется пара `assistant(tool_call) + user(tool_result)`. У `tool_result` три статуса:

| Статус | Когда | Что видит модель |
| :--- | :--- | :--- |
| `SUCCESS` | Инструмент вернул результат | `tool_result: SUCCESS. <name> returned: <result>. If this satisfies...` |
| `ERROR` | Инструмент бросил исключение или исчерпал `max_tool_failures` | `tool_result: ERROR. <name> returned: ...` |
| `SKIPPED` | Тот же вызов с теми же аргументами уже был успешно выполнен | `tool_result: SKIPPED. <name> was not executed again... Respond with a final answer now.` |

Три статуса вместо одного `SUCCESS`/`ERROR` — прямое следствие ревью (шаг 6.5, T1): раньше при пропуске повторного вызова модели уходил `SUCCESS` с текстом `ALREADY_EXECUTED`, что противоречило смыслу.

## Инструменты: план и статус

| Инструмент | Статус | Шаг |
| :--- | :--- | :--- |
| `echo` | готов (только для тестов) | 2 |
| `save_note` | готов | 3, 5.6, 6.6–6.7 |
| `read_notes` | готов | 6, 6.3–6.7 |
| `search_notes` | готов | 6, 6.6–6.7 |
| `search_documents` | готов | 7.2 |
| `extract_pdf_text` | план | 7.4 |
| `generate_document` | план | 7.3 |
| `analyze_image` | план | 8 |
| `move_file` | план | 8 |

`search_documents` работает через `VectorStore.search_hybrid` (BM25 + векторный). Добавление `extract_pdf_text` в 7.4 не потребует изменений в RAG — только новый модуль в `extractors/` и регистрация.

## Гибридный поиск (детали)

`search_hybrid` объединяет два ранжирования через **Reciprocal Rank Fusion**:

- Векторный поиск: косинус между эмбеддингом запроса и эмбеддингами чанков.
- BM25: лексическое совпадение токенов с IDF-взвешиванием.

**Почему RRF, а не взвешенная сумма score:** BM25 неограничен сверху (зависит от длины запроса и корпуса), cosine ограничен `[-1, 1]`. Нормализация на малом корпусе нестабильна. RRF использует **ранги**, а не score — работает «из коробки».

**Формула:** `score(chunk) = Σ 1 / (k + rank_i)`, где `k = 60`, `rank_i` — позиция чанка в i-м списке (1-based). Стандартная константа, эмпирически даёт хороший баланс.

**Кандидаты:** каждый поиск возвращает `candidate_k = max(top_k * 4, 20)`. Для 94 чанков корпуса — 20 хватает. Для больших корпусов — параметр растёт.

**Что это даёт:** BM25 находит точные термины («16 ГБ», «Ollama»), векторный — семантику («оперативная память» ≈ «требования к памяти»). Запросы, где один из поисков проваливается, вытягиваются другим.

**Ограничение:** BM25 без стемминга. «Установить» не матчит «Установка» (разные токены: `установить` vs `установка`). Решение — стемминг в токенизаторе (шаг 7.1.4). Сейчас частично компенсируется эмбеддингами.

## Модель: 3B vs 7B

Основная модель — `qwen2.5-7b-agent`. 3B (`qwen2.5-3b-agent`) — опция для скорости.

| | 3B | 7B |
| :--- | :--- | :--- |
| Routing инструментов | 4/7 | **7/7** |
| Synthesis | 2/7 | 6/7 |
| Скорость (CPU) | 1–2 мин на вопрос | 2–4 мин на вопрос |
| RAM | ~2–3 ГБ | ~6 ГБ |

**Почему 7B:** в контрольном прогоне из 7 вопросов 3B не вызывала `search_documents` в 3 случаях (пустые финалы, путаница с `search_notes`). 7B вызвала правильно во всех 7. Few-shot (7.2.2) помог 3B частично (4/7), но не решил проблему. Дальнейшие итерации промптов для 3B — тупик; 7B — решение на данных, а не на догадках.

**Переключение:** в `config/settings.toml` `[llm] model`. Индекс RAG и BM25 не зависят от LLM — переиндексация не нужна.

**Оптимизация скорости** (в `TODO.md`): `llama.cpp` (−20–30%), `Q4_0` вместо `Q4_K_M` (−10–15%), `num_ctx=4096` (−5–10%), интерактивный режим (модель остаётся в памяти).

## Ограничения текущей версии

- **7B на CPU — медленно.** 1.5–4 минуты на вопрос при `num_ctx=8192`. Оптимизация — в `TODO.md`.
- **RAG работает только на Markdown и TXT.** PDF, DOCX, HTML, EPUB — в шаге 7.4, через реестр экстракторов.
- **Стем в `_search.find_match` — подстрочный.** `\b`-граница применяется только в `search_notes.matches`. BM25 для документов использует токенизацию без стемминга (7.1.4 — стемминг).
- **`confirm_file_operations` читается из TOML, но не применяется.** Ждёт `move_file` в шаге 8.
- Один агент, без мультиагентности.
- Без самодописывания кода.
- Файловые операции — только `save_note`, без перемещения и удаления.
- Нет UI: запуск через скрипты.
- Нет стриминга ответов.
- Нет автоматического ретрая при ошибках Ollama.
- Индекс RAG не инкрементальный: любое изменение корпуса — пересборка `build_index.py --reset`.

## Принципы разработки

1. **Маленькие шаги с тестами.** Каждый инструмент сначала покрывается unit-тестами без LLM, потом проверяется smoke-скриптом с реальной моделью.
2. **Детерминированные тесты.** Тесты оркестратора и LLM-слоя используют `FakeLLM` и моки HTTP. Тесты RAG мокают `Embedder` и пишут в `tmp_path`. Реальная модель — только в smoke-скриптах.
3. **Безопасность данных.** `data/` и `logs/` не попадают в git. Логи не содержат полных текстов заметок и документов (`_summarize_for_log`).
4. **Один инструмент за раз.** Не добавлять несколько инструментов в одном шаге, чтобы проще было отлаживать выбор модели.
5. **Пути от корня проекта, а не от CWD.** Конфиг, данные и логи не зависят от того, из какой папки запущен скрипт.
6. **Расширяемость через реестр.** Новый формат документа — новый модуль в `extractors/` + одна строка `register(...)`. RAG не меняется. Тот же принцип применим к новым инструментам: `ALL_TOOLS` — единственное место регистрации.
7. **Честные исключения в библиотеке, `sys.exit` только в `main`.** `build_index` бросает `FileNotFoundError`/`FileExistsError`, `main` их ловит и делает `sys.exit`. Иначе функцию нельзя тестировать и переиспользовать.