# TODO

Мелкие исправления, технический долг и известные компромиссы. Не привязаны к шагам плана (`TASKS.md`).

Статусы: `[ ]` — не сделано, `[x]` — сделано.

Приоритеты:
- 🔴 **Критично** — исправить до шага 7 (RAG/PDF). Влияет на корректность конфига или стабильность агента.
- 🟡 **Средний** — исправить по мере необходимости, не блокирует шаг 7.
- ⚪ **Низкий** — косметика и придирки, можно отложить.
- 🧩 **Компромисс** — осознанное решение, не баг. Пересмотреть при смене бэкенда или в RAG.

---

## 🔴 Критично перед шагом 7

### T1. Статус `SKIPPED` при повторном вызове инструмента
**Файл:** `src/agent/orchestrator.py`
**Проблема:** при `call_key in executed_calls` инструмент не выполняется, но `tool_succeeded` остаётся `True`, и модели уходит `tool_result: SUCCESS. ... ALREADY_EXECUTED ...`. Противоречие: статус «успех», текст «пропущено».
**Исправить:** ввести третий статус — `SKIPPED`. Возвращать модели `tool_result: SKIPPED. <name> was not executed again because the same call already succeeded. Respond with a final answer now.`
**Тесты:** обновить `test_repeated_identical_tool_call_is_skipped` — проверять `"SKIPPED"` в `tool_result`. Добавить тест, что успешный вызов даёт `SUCCESS`, а исключение — `ERROR`.

### T7. `load_config` игнорирует ключевые поля TOML
**Файл:** `src/agent/config.py`
**Проблема:** в `settings.example.toml` есть `provider`, `base_url`, `max_steps`, `confirm_file_operations`. `load_config` читает из `[llm]` только `model`, `temperature`, `max_tokens`. Следствия: смена `max_steps` не работает (всегда дефолт 10), `base_url` не работает, `provider` мёртв, `confirm_file_operations` не читается.
**Исправить:** привести `LLMConfig`/`SafetyConfig` в соответствие с TOML. Все поля, описанные в `settings.example.toml`, должны читаться. `base_url` и `max_steps` — в `LLMConfig`; `confirm_file_operations` — в `SafetyConfig`.
**Тесты:** добавить в `test_config.py` проверки, что `base_url`, `max_steps`, `provider`, `confirm_file_operations` из файла попадают в `AppConfig`. Добавить в `test_app.py` тест «TOML → `AppConfig` → `Orchestrator.max_steps` и `OllamaLLM.base_url` совпадают с файлом».

### T8. Логи пишутся не в `logs_dir`, дубль полей в `PathsConfig`
**Файл:** `src/agent/config.py`, `scripts/run_agent.py`
**Проблема:** `setup_logging` в `run_agent.py` вызывается с `config.paths.logs`, а не с `logs_dir`. В датаклассе два поля (`logs` и `logs_dir`) с одним дефолтом `"logs"`. Пока пути совпадают — «везёт». Если в TOML поменять только `logs_dir`, логи уйдут в другое место.
**Исправить:** оставить одно поле `logs_dir`. `run_agent.py` использует `config.paths.logs_dir`. Обновить `settings.example.toml`, если в нём есть `logs`.
**Тесты:** проверить, что `setup_logging` получает путь из `logs_dir`; в `test_config.py` — что в `PathsConfig` нет дублирующего поля.

### T9. `OllamaLLM.chat` не устойчив к «кривому» ответу
**Файл:** `src/agent/llm_ollama.py`
**Проблема:**
- `json.loads(arguments)` может бросить `JSONDecodeError` (подкласс `ValueError`). В `run_agent` ловится только `RuntimeError` → вылетит трейсбек.
- Пустые `choices` или отсутствие `message` → `IndexError`/`KeyError`.
- Несколько `tool_calls` — берётся только первый, остальные молча отбрасываются.
- Полный `messages` логируется на INFO — в лог попадают тексты заметок.
**Исправить:**
- Обработать `JSONDecodeError` → вернуть `LLMResponse(type="final", content="ERROR: invalid tool arguments")` или поднять `RuntimeError` с понятным текстом.
- Проверять `data.get("choices")`, `choices[0].get("message")`; если пусто — `RuntimeError`.
- Если `tool_calls` больше одного — логировать warning и брать первый (или явно описать поведение).
- Не логировать полный `messages` на INFO. Логировать `step`, `type`, имя инструмента, длину ответа, но не тексты.
**Тесты:** добавить в `test_llm_ollama.py` кейсы: невалидный JSON в `arguments`, пустые `choices`, ответ без `message`. Проверить, что `chat` не пропускает полный `messages` в лог (или что лог содержит только метаданные).

### T10. `temperature` / `max_tokens` не передаются в Ollama
**Файл:** `src/agent/llm_ollama.py`, `src/agent/config.py`
**Проблема:** `load_config` читает `temperature`/`max_tokens` (частично), но `OllamaLLM.chat` не кладёт их в `payload`.
**Исправить:** добавить `temperature` и `max_tokens` в `OllamaLLM.__init__` и в `payload`. Если поле не задано в конфиге — не передавать (использовать дефолт Ollama). Для 3B на tool calling часто лучше `temperature` ближе к 0.
**Тесты:** в `test_llm_ollama.py` проверить, что при заданных `temperature`/`max_tokens` они появляются в `payload`; при `None` — не появляются.

### T11. Ошибки инструментов не попадают в `executed_calls`
**Файл:** `src/agent/orchestrator.py`
**Проблема:** `executed_calls.add(call_key)` вызывается только в `try`-ветке после успешного вызова. Упавший вызов не запоминается, модель может долбить один и тот же падающий инструмент до `max_steps`.
**Исправить:** добавить счётчик ошибок на `call_key`. После N (например, 2) неудачных попыток одного вызова — возвращать `ERROR: <name> failed N times, giving up. Respond with a final answer.` и не вызывать инструмент.
**Тесты:** добавить тест: `FakeLLM` возвращает один и тот же `tool_call` на падающий инструмент 3 раза. Проверить, что `registry.call` вызван не более 2 раз, а на третьем шаге модели уходит сообщение про «giving up».

### T12. Тест `test_save_note_via_tool_context` проверяет не то; `notes_dir` утекает в историю
**Файл:** `tests/test_orchestrator.py`, `src/agent/orchestrator.py`
**Проблема:** `llm.calls[0][-1]` — это цель пользователя в первом запросе, там `notes_dir` и не мог появиться. А в историю оркестратор кладёт `tool_call: save_note({..., notes_dir: Path(...)})` — путь **утекает** в следующий промпт. Перекрытие контекстом работает, но модель путь видит.
**Исправить:**
1. В `orchestrator.py` при формировании `assistant`-сообщения класть аргументы **без** `tool_context`: `{**response.tool_arguments}` вместо `arguments`. Путь остаётся в вызове функции, но не в истории.
2. В тесте проверять, что в `llm.calls[1]` (второй запрос) в `assistant`-сообщении **нет** `notes_dir`.
**Тесты:** переписать `test_save_note_via_tool_context` — проверять отсутствие `notes_dir` в истории и наличие его в фактическом вызове инструмента.

---

## 🟡 Средний приоритет

### T2. `notes_dir: Path = ...` в `read_notes`
**Файл:** `src/agent/tools/read_notes.py`
**Проблема:** дефолт `Ellipsis` — нестандартный приём. Прямой вызов `read_notes("x")` без `notes_dir` упадёт с невнятной ошибкой.
**Исправить:** явный дефолт `notes_dir: Path | None = None` с подстановкой `Path("data/notes")` внутри функции. Обновить схему параметров инструмента, если нужно.
**Тесты:** `test_read_notes_default_notes_dir` — вызов без `notes_dir` не падает.

### T3. `max_results` в `read_notes` не вынесен в аргументы
**Файл:** `src/agent/tools/read_notes.py`
**Проблема:** жёстко зашитое `50` при пустом запросе.
**Исправить:** добавить `max_results: int = 50` в сигнатуру и в схему параметров (как у `search_notes`).
**Тесты:** обновить `test_empty_query_respects_max_results` на использование параметра.

### T4. Косметика в `search_notes`
**Файл:** `src/agent/tools/search_notes.py`
**Проблема:** суффикс `"…"` добавляется только при `has_prev`. Если совпадение в начале файла и snippet обрезан справа — суффикса нет. Также неиспользуемая `q = query.lower()`; при `kind == "stem"` `count(query[:-2])` завышает совпадения.
**Исправить:** условие `if trimmed_right or has_next_line` → `"…"` в конец. Удалить `q`. Пересмотреть подсчёт `matches` для stem (считать по `stem`, а не по `query[:-2]`).
**Тесты:** кейс с совпадением в первой строке; проверка `matches` для stem-совпадения.

### T6. Дублирование чтения заметок
**Файлы:** `src/agent/tools/read_notes.py`, `src/agent/tools/search_notes.py`
**Проблема:** обе функции почти одинаково читают файл, извлекают заголовок и тело.
**Исправить:** вынести в `_search.py` хелпер `load_note(path: Path) -> dict | None`, возвращающий `{"title": ..., "body": ...}` или `None` при ошибке. Также общий обход `*.md` в каталоге.
**Тесты:** существующие должны остаться зелёными.

### T13. `requirements.txt` пинит транзитивные пакеты
**Файл:** `requirements.txt`
**Проблема:** `pip freeze` записал `certifi`, `pluggy`, `iniconfig`, `packaging` и другие. Обновление `pytest` будет ломать установку.
**Исправить:** оставить только прямые зависимости: `requests`, `pytest`. Версии — минимальные (`>=`), не точные.
**Тесты:** `pip install -r requirements.txt` в чистом окружении проходит.

### T14. Нет `src/__init__.py`, нет `pyproject.toml` с `pythonpath`
**Проблема:** импорты держатся на `sys.path` и на том, что pytest запускают из корня. `from src.agent.tools.read_notes import ...` сработает не всегда.
**Исправить:** добавить `src/__init__.py`. Создать `pyproject.toml` с `[tool.pytest.ini_options] pythonpath = ["."]`. Убрать `sys.path.insert` из отладочных скриптов (они и так удаляются).
**Тесты:** `pytest` из любой подпапки проходит.

### T15. Дублирование списка инструментов в `app.py`
**Файл:** `src/agent/app.py`
**Проблема:** `registry.register(TOOL)` для каждого и `tools = [...]` — два места, где перечислены инструменты. Легко зарегистрировать в реестре, но забыть в `tools`, или наоборот.
**Исправить:** один список `ALL_TOOLS`, из него и регистрация в цикле, и передача в `OllamaLLM`, и построение `tool_context` из `config.paths.notes_dir`.
**Тесты:** `test_build_orchestrator_registers_all_tools` и `test_tool_context_has_notes_dir_for_all_tools` уже есть — они продолжат работать.

### T5. Дубль `?` в regex slug
**Файл:** `src/agent/tools/save_note.py`
**Проблема:** `re.sub(r'[<>:"/\\|?*?]', "", slug)` — `?` указан дважды.
**Исправить:** `re.sub(r'[<>:"/\\|?*]', "", slug)`.
**Тесты:** существующие проходят.

### T16. Неизвестный `response.type` крутит цикл
**Файл:** `src/agent/orchestrator.py`
**Проблема:** если тип не `final` и не `tool_call`, цикл крутится, в `messages` ничего не добавляется, пока не вылетит `MaxStepsExceeded`.
**Исправить:** при неизвестном типе — логировать warning и возвращать `OrchestratorResult(success=False, error=...)` или выбрасывать понятное исключение.
**Тесты:** тест с `FakeLLM`, возвращающим `LLMResponse(type="unknown")` (если протокол позволит) — или пропустить, пока протокол ограничен литералом.

---

## ⚪ Низкий приоритет / косметика

### T17. Windows-безопасность slug
**Файл:** `src/agent/tools/save_note.py`
**Проблема:** не режутся trailing `.`/` ` в имени; нет защиты от зарезервированных `CON`, `PRN`, `NUL`, `AUX`, `COM1..9`, `LPT1..9`.
**Исправить:** strip trailing dots/spaces; если slug (без расширения) совпадает с зарезервированным именем — добавить префикс `_`.

### T18. `search_notes` читает все `.md` при `max_results=1`
**Файл:** `src/agent/tools/search_notes.py`
**Проблема:** функция не может остановиться раньше, чем прочитает все файлы, даже если `max_results=1`. Для десятков заметок несущественно.
**Исправить:** ранний выход из цикла, когда набрано `max_results`. Но тогда сортировка по `path` теряет смысл (или нужно сначала сортировать список файлов и обходить в порядке). Решение: сортировать `md_files` до цикла, останавливаться при `len(results) >= max_results`.

### T19. Поиск только на одном уровне
**Файлы:** `read_notes.py`, `search_notes.py`
**Проблема:** вложенные папки в `notes_dir` не обходятся.
**Исправить:** опциональный параметр `recursive: bool = False`; по умолчанию — как сейчас. Когда появятся подпапки — включить.

### T20. `TASKS.md` устарел
**Файл:** `TASKS.md`
**Проблема:** там всё ещё написано, что зацикливание «оставлено как есть», хотя skip уже реализован (шаг 6.1). И упоминание `debug_*` файлов, если оно есть.
**Исправить:** актуализировать статусы и убрать устаревшие оговорки.

### T21. Мёртвый `path.read_bytes()` перед `tomllib.load`
**Файл:** `src/agent/config.py`
**Проблема:** если такой код есть — файл читается дважды.
**Исправить:** убрать лишнее чтение.

### T22. `SafetyConfig` нигде не используется
**Файлы:** `src/agent/config.py`, `src/agent/orchestrator.py`
**Проблема:** поля `allow_shell`, `max_tool_retries` (если есть) объявлены, но не влияют на поведение.
**Исправить:** либо реализовать использование (например, `max_tool_retries` в T11), либо удалить неиспользуемые поля, чтобы не вводить в заблуждение.

---

## 🧩 Известные компромиссы (не баги)

Эти решения приняты осознанно. Пересмотреть — при смене бэкенда (llama.cpp, OpenAI) или в шаге 7 (RAG).

### C1. Самодельный формат `tool_call:` / `tool_result:` вместо OpenAI `role: "tool"`
Для 3B-модели стандартные роли `assistant.tool_calls` + `role=tool` часто работают хуже, чем простые текстовые маркеры. Оставляем как есть. При переходе на другой бэкенд — пересмотреть.

### C2. Стемминг `query[:-2]` вместо `pymorphy3`
`pymorphy3` — зависимость и замедление на CPU. Для заметок эвристики хватает. В RAG эмбеддинги решат семантику. Пока — оставляем.

### C3. Один tool call за шаг
Мультитул и параллельные вызовы — после того, как конфиг и статусы станут однозначными. Для 3B текущий цикл нормален.

### C4. Список инструментов в `app.py` и `tools` — потенциальный дубль
Пока решается вручную; см. T15. Долгосрочно — единый `ALL_TOOLS`.

---

## 📌 После шага 7 (RAG/PDF)

- Разделить хранилище заметок/документов, retriever (эмбеддинги) и агент. Не тащить эмбеддинги внутрь `search_notes.py`.
- Убрать стемминг из `_search.py` — заменяется на семантический поиск.
- Ротация `logs/agent.log` — файл будет расти.
- Подтверждение опасных файловых операций (CLI) для `move_file`.
- Пересмотреть C1 (формат `tool_call`/`tool_result`) при переходе на llama.cpp/OpenAI.
- Проброс `temperature` ближе к 0 для tool calling на 3B — если качество маршрутизации просядет.

---

## ✅ Сделано

- [x] Шаг 1: каркас проекта.
- [x] Шаги 2–6: конфиг, логирование, `save_note`, `read_notes`, `search_notes`, оркестратор, подключение Ollama.
- [x] Шаг 6.1: защита от повторных вызовов (`executed_calls`).
- [x] Шаг 6.2: единая логика поиска со стеммингом.
- [x] Шаг 6.3: `query` опционален в `read_notes`.
- [x] Шаг 6.4: уточнение маршрутизации `read_notes` vs `search_notes`.
- [x] Шаг 5.5: удобная точка входа (`run_agent.py`) и фабрика оркестратора (`build_orchestrator`).
- [x] Шаг 5.6: русские триггеры в `SAVE_NOTE_TOOL`.
- [x] Контрольный прогон шага 6: 10/10.