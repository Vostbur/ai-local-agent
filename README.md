# AI Local Agent

Локальный AI-агент для повседневных задач. Работает полностью на вашем компьютере: ни документы, ни заметки, ни фотографии не покидают вашу машину.

## Что умеет сейчас

- **Сохранять заметки** в Markdown-файлы (`save_note`). Существующие заметки никогда не перезаписываются: при совпадении имени добавляется числовой суффикс.
- **Искать заметки по названию** (`read_notes`) — по заголовку и имени файла, с учётом русских словоформ.
- **Искать по содержимому** (`search_notes`) — с фрагментом контекста и числом совпадений.
- Работать с **локальной моделью** через [Ollama](https://ollama.com).
- **Не вызывать инструменты зря**: на посторонние вопросы вроде «какая погода» агент отвечает без `tool_call`.
- **Не зацикливаться** на повторных вызовах: одинаковый вызов инструмента с теми же аргументами пропускается (шаг 6.1). После `max_tool_failures` неудач подряд падающий вызов блокируется.
- **Не зависеть от текущей папки**: конфиг и данные берутся от корня проекта, а не от CWD (шаг 6.7).
- **Переживать `null`** в опциональных аргументах от модели (шаг 6.7, T24).
- Вести **логи** своих действий в `logs/agent.log` — без полных текстов заметок.

## Что появится позже

- Анализ PDF-документов и создание новых документов по их подобию.
- Сортировка фотографий по содержимому.
- Полноценный RAG (поиск по смыслу через эмбеддинги) по документам.

Текущий статус и план — в файле `TASKS.md`.

---

## Требования

- **Операционная система:** Windows 10/11, macOS или Linux.
- **Python 3.11 или новее.** Проверено на 3.11, 3.12, 3.13.
  Скачать: https://www.python.org/downloads/
  - На Windows при установке обязательно поставьте галочку **«Add Python to PATH»**.
- **Ollama.** Скачать: https://ollama.com/download
  - После установки Ollama запускается автоматически. Если нет — откройте терминал и выполните `ollama serve`.
- **Свободное место на диске:** около 3 ГБ (модель + зависимости).
- **Оперативная память:** 16 ГБ рекомендуется. На 8 ГБ будет тесно.
- **Git** (по желанию, но рекомендуется). Скачать: https://git-scm.com/downloads

---

## Установка с нуля (для новичка)

Все команды ниже выполняются в терминале. На Windows удобно использовать **PowerShell**, на macOS/Linux — **Terminal**.

### Шаг 1. Скачайте проект

Если вы уже скопировали папку проекта — переходите к шагу 2. Иначе:

    git clone <адрес-вашего-репозитория> ai-local-agent
    cd ai-local-agent

Если git не установлен, скачайте архив с проектом и распакуйте его, затем откройте терминал в распакованной папке.

### Шаг 2. Установите Ollama и загрузите модель

Установите Ollama с официального сайта.

Убедитесь, что Ollama работает:

    ollama --version

Если команда не найдена — перезапустите терминал.

Загрузите модель:

    ollama pull qwen2.5:3b

Займёт несколько минут и около 2 ГБ.

Проверьте:

    ollama run qwen2.5:3b "Привет"

Выйти из интерактивного режима — Ctrl+D (macOS/Linux) или `/bye` (Windows).

### Шаг 3. Создайте модель с увеличенным контекстом

Агенту нужен контекст больше стандартного. В корне проекта создайте файл `Modelfile`:

    FROM qwen2.5:3b
    PARAMETER num_ctx 8192

Соберите модель под новым именем:

    ollama create qwen2.5-3b-agent -f Modelfile

Проверьте:

    ollama list

В списке должна появиться `qwen2.5-3b-agent:latest` (тег `:latest` Ollama добавляет автоматически, в конфиге его можно не писать).

### Шаг 4. Создайте виртуальное окружение Python

    python -m venv .venv

Активируйте:

**Windows (PowerShell):**

    .venv\Scripts\Activate.ps1

Если PowerShell ругается на политику выполнения, один раз выполните:

    Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned

**Windows (cmd):**

    .venv\Scripts\activate.bat

**macOS / Linux:**

    source .venv/bin/activate

В начале строки появится `(.venv)`.

### Шаг 5. Установите зависимости

    pip install -r requirements.txt

### Шаг 6. Создайте локальный файл настроек

    # macOS / Linux
    cp config/settings.example.toml config/settings.toml

    # Windows (PowerShell)
    Copy-Item config\settings.example.toml config\settings.toml

Файл `config/settings.toml` не попадает в git — это ваши личные настройки.

### Шаг 7. Проверьте, что всё работает

    pytest -v

Все тесты должны быть зелёными. Благодаря `pyproject.toml` с `pythonpath = ["."]` тесты запускаются из любой папки проекта.

Запустите агент с одной задачей (реальная модель):

    python scripts/run_agent.py "Сохрани заметку 'Тест запуска' с текстом 'Привет'"

Первый запуск может занять несколько минут: модель загружается в память, а генерация на CPU медленная. В итоге в `data/notes/` появится файл с заметкой, а в консоли — строка вида `Готово: ...`.

**Важно:** скрипт можно запускать из любой папки — конфиг и данные ищутся от корня проекта, а не от текущей директории (шаг 6.7). Например, из `C:\`:

    python D:\projects\ai-local-agent\scripts\run_agent.py "Покажи все заметки"

---

## Как пользоваться агентом

### Запуск одной задачи

    python scripts/run_agent.py "Сохрани заметку 'Список покупок' с текстом 'Молоко, хлеб, яйца'"

Скрипт выполнит цель, напечатает финальный ответ и (если инструмент вернул путь) — путь к созданному файлу.

Если задача не удалась, будет напечатана причина:

    Не удалось выполнить задачу. Шагов: 1
    Причина: unknown response type: 'unknown'

### Интерактивный режим

    python scripts/run_agent.py

Скрипт запустится один раз и будет спрашивать цели одну за другой. Модель остаётся загруженной в память, поэтому следующие задачи выполняются быстрее, чем при повторном запуске скрипта.

    AI Local Agent (модель: qwen2.5-3b-agent)
    Введите цель или /quit для выхода.
    > сохрани заметку про встречу в понедельник
    [...] выполняется, подождите (на CPU это может занять несколько минут)
    Готово: Заметка сохранена.
    Шагов: 2
    > /quit
    Выход.

Для выхода: `/quit`, `/exit`, `exit`, `quit`, `Ctrl+C` или `Ctrl+D`.

### Типичные проблемы при запуске

- **Ollama не отвечает.** Запустите `ollama serve` в отдельном терминале и повторите.
- **Не найден файл настроек.** Скопируйте `config/settings.example.toml` в `config/settings.toml`.
- **Достигнут лимит шагов.** Модель не смогла дойти до финала за `max_steps` шагов. Сформулируйте цель точнее или увеличьте `max_steps` в `config/settings.toml`.

---

## Где хранятся данные

- **Заметки:** `data/notes/`
- **Логи:** `logs/agent.log`
- **Настройки:** `config/settings.toml`

Пути резолвятся от корня проекта, а не от текущей папки. Папки `data/` и `logs/` не попадают в git — ваши личные данные не окажутся в репозитории.

---

## Что происходит после запуска команды — пошаговый разбор

Этот раздел — учебный. Он показывает весь путь от нажатия Enter до появления файла с заметкой: какие функции вызываются, в каком порядке, какие данные передаются между ними. Если вы новичок в программировании, читайте его после того, как хотя бы один раз успешно запустили агента — так будет понятнее.

### Команда, которую мы разбираем

    python scripts/run_agent.py "Сохрани заметку 'Тест запуска' с текстом 'Привет'"

- `python` — интерпретатор Python.
- `scripts/run_agent.py` — точка входа, «кнопка включения» агента.
- `"Сохрани заметку 'Тест запуска' с текстом 'Привет'"` — **аргумент командной строки**, цель агента. Кавычки нужны, чтобы оболочка не разбила фразу на отдельные слова.

### Общая картина

Три фазы:

1. **Подготовка.** Python читает конфиг, настраивает логи, собирает оркестратор с инструментами и моделью.
2. **Работа агента.** Оркестратор в цикле общается с Ollama. Модель решает вызвать `save_note`, оркестратор вызывает функцию, возвращает результат модели, модель говорит «готово».
3. **Завершение.** Оркестратор возвращает результат, скрипт печатает его и выходит.

### Шаг 1. Python запускает `run_agent.py`

Python открывает файл, находит:

    if __name__ == "__main__":
        main()

и вызывает `main()`. Параллельно Python импортирует всё из шапки файла:

- `sys`, `argparse`, `logging` — стандартные библиотеки;
- `load_config` из `src/agent/config.py`;
- `setup_logging` из `src/agent/logging_setup.py`;
- `build_orchestrator` из `src/agent/app.py`;
- `MaxStepsExceeded` из `src/agent/orchestrator.py`.

Импорт — это «подключение»: Python читает файл и делает функции и классы доступными.

### Шаг 2. `main()` разбирает аргументы командной строки

    parser = argparse.ArgumentParser(description="AI Local Agent")
    parser.add_argument("goal", nargs="?", help="...")
    args = parser.parse_args()

- `add_argument("goal", nargs="?")` — позиционный аргумент `goal`, необязательный.
- `parse_args()` раскладывает слова после имени скрипта. В нашем случае `args.goal == "Сохрани заметку 'Тест запуска' с текстом 'Привет'"`.

Если аргумента нет, `args.goal is None` — скрипт перейдёт в интерактивный режим.

### Шаг 3. `load_config()` читает настройки

    try:
        config = load_config()
    except FileNotFoundError:
        ...
        sys.exit(1)

`load_config()` (из `src/agent/config.py`):

1. Определяет путь к файлу: `_PROJECT_ROOT / "config" / "settings.toml"`, где `_PROJECT_ROOT = Path(__file__).resolve().parents[2]`. Это **корень проекта**, а не CWD (шаг 6.7, T22).
2. Открывает файл и читает TOML через стандартный `tomllib`.
3. Превращает данные в датаклассы:
   - `LLMConfig(model, base_url, temperature, max_tokens, max_steps)` — без `provider` (шаг 6.7, T27);
   - `PathsConfig(data_dir, notes_dir, inbox_dir, photos_dir, logs_dir, memory, tools)` — относительные пути резолвятся от `_PROJECT_ROOT` через `_resolve_path` (шаг 6.7, T22);
   - `SafetyConfig(confirm_file_operations, max_tool_retries)` — без `allow_shell`/`allow_network` (шаг 6.7, T21);
   - `AppConfig(llm, paths, safety)`.
4. Возвращает `AppConfig`.

Если файла нет — `FileNotFoundError`, `main()` печатает путь, по которому искал, и выходит с кодом 1.

Ключевой момент: `config` — это не словарь. Это объект, в котором по атрибутам доступны значения: `config.llm.model`, `config.paths.notes_dir`. Такой подход называется **типизированной конфигурацией**: IDE подсказывает поля, опечатки ловятся сразу.

### Шаг 4. `setup_logging()` готовит логи

    logger = setup_logging(config.paths.logs_dir)

Функция из `src/agent/logging_setup.py`:

1. Создаёт папку `logs/`, если её нет.
2. Настраивает логгер `"agent"` — один на весь проект.
3. Добавляет два обработчика: файл `logs/agent.log` (UTF-8, append) и консоль.
4. Формат: `время | уровень | имя логгера | сообщение`.
5. Возвращает логгер.

`setup_logging` защищена от дубликатов: повторный вызов не добавит вторые обработчики.

### Шаг 5. `build_orchestrator()` собирает агента

    orchestrator = build_orchestrator(config, logger)

Функция из `src/agent/app.py`:

**5.1. Создаёт реестр.**

    registry = ToolRegistry()

**5.2. Регистрирует все инструменты из единого списка.**

    ALL_TOOLS = [SAVE_NOTE_TOOL, READ_NOTES_TOOL, SEARCH_NOTES_TOOL]
    for tool in ALL_TOOLS:
        registry.register(tool)

`ALL_TOOLS` — единственное место, где перечислены инструменты (шаг 6.6, T15). Если добавить новый, достаточно дописать в `ALL_TOOLS` — он попадёт и в реестр, и в `tools` для LLM.

**5.3. Создаёт клиент к Ollama.**

    llm = OllamaLLM(
        model=config.llm.model,
        base_url=config.llm.base_url,
        tools=ALL_TOOLS,
        temperature=config.llm.temperature,
        max_tokens=config.llm.max_tokens,
    )

`OllamaLLM` (из `src/agent/llm_ollama.py`) — обёртка над HTTP. В конструкторе ничего не отправляется, только запоминаются параметры. `temperature`/`max_tokens` передаются в payload, только если заданы (шаг 6.5, T10).

**5.4. Готовит `tool_context`.**

    tool_context = {
        name: {"notes_dir": config.paths.notes_dir}
        for name in TOOLS_WITH_NOTES_DIR
    }

`TOOLS_WITH_NOTES_DIR` — список инструментов, которым нужен `notes_dir` (`save_note`, `read_notes`, `search_notes`). Другие инструменты (например, `move_file` в шаге 8) в этот список не попадут, и лишнего аргумента им не передадут.

**5.5. Создаёт оркестратор.**

    return Orchestrator(
        llm=llm,
        registry=registry,
        logger=logger,
        max_steps=config.llm.max_steps,
        tool_context=tool_context,
        max_tool_failures=config.safety.max_tool_retries,
    )

`max_tool_failures` приходит из `SafetyConfig.max_tool_retries` (по умолчанию 2, шаг 6.7, T21).

`tool_context` — важная деталь. Модель не должна знать, куда сохранять файлы. Путь приходит из конфига. Даже если модель попытается подменить `notes_dir`, `{**args, **extra}` перекроет её аргумент.

### Шаг 6. `main()` вызывает `_run_one()`

    if args.goal:
        _run_one(orchestrator, args.goal, logger)
        return

`_run_one` печатает предупреждение:

    [...] выполняется, подождите (на CPU это может занять несколько минут)

Это не косметика: на CPU первая задача может занять 1–3 минуты.

Затем вызывает:

    result = orchestrator.run(goal)

### Шаг 7. `Orchestrator.run()` — начало цикла

**7.1. Инициализирует историю с системным промптом.**

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": goal},
    ]

`SYSTEM_PROMPT` содержит четыре правила: вызывать инструмент только при необходимости, после успеха — финал, не повторять одинаковые вызовы, `read_notes` для названий / `search_notes` для содержимого.

**7.2. Запускает цикл до `max_steps`.**

    executed_calls: set[str] = set()
    failed_calls: dict[str, int] = {}
    for step in range(1, self.max_steps + 1):

- `executed_calls` — множество успешно выполненных вызовов в этой задаче. Для защиты от повторных вызовов.
- `failed_calls` — счётчик ошибок по ключу вызова. Для защиты от долбёжки падающего инструмента (шаг 6.5, T11).

Оба живут только внутри `run`, между задачами не переносятся.

**7.3. Отправляет историю модели.**

    response = self.llm.chat(messages)

`OllamaLLM.chat`:

1. Преобразует `tools` в формат OpenAI.
2. Формирует POST на `http://localhost:11434/v1/chat/completions`.
3. Ждёт ответ (десятки секунд на CPU).
4. Разбирает JSON → `LLMResponse`.

Если ответ кривой (`JSONDecodeError`, пустые `choices`, нет `message`) — `RuntimeError` с понятным текстом (шаг 6.5, T9).

**7.4. Модель решает вызвать инструмент.**

Ollama возвращает `tool_calls`, где `arguments` — строка JSON. `OllamaLLM.chat` делает `json.loads(...)` и возвращает `LLMResponse(type="tool_call", tool_name="save_note", tool_arguments={"title": "...", "content": "..."})`.

**7.5. Оркестратор готовит аргументы.**

    extra = self.tool_context.get("save_note", {})
    arguments = {**response.tool_arguments, **extra}

`extra` идёт **после** — контекст перекрывает аргументы модели. Если бы модель передала `notes_dir="C:/Windows"`, контекст бы это перекрыл.

**7.6. Проверка на повторный вызов и на лимит падений.**

Оркестратор строит ключ вызова:

    call_key = f"{response.tool_name}:{sorted((k, str(v)) for k, v in arguments.items())}"

Три ветки:

- **`SKIPPED`** — если `call_key in executed_calls` (тот же вызов уже успешно выполнялся). Модели возвращается `tool_result: SKIPPED. ... Respond with a final answer now.`
- **`ERROR` (giving up)** — если `failed_calls[call_key] >= max_tool_failures`. Модели возвращается `ERROR: failed N times in a row, giving up. Do NOT call it again.`
- **обычный вызов** — `registry.call(...)`. При успехе `executed_calls.add(call_key)`. При исключении `failed_calls[call_key] += 1`.

**7.7. Формирует `tool_result` для модели.**

    if tool_status == "SKIPPED":
        content = f"tool_result: SKIPPED. {tool_name} {result}. Respond with a final answer now."
    else:
        content = f"tool_result: {tool_status}. {tool_name} returned: {result}. If this satisfies the user's goal, respond with a final answer now."

Три статуса `SUCCESS` / `ERROR` / `SKIPPED` — вместо прежнего булева `tool_succeeded` (шаг 6.5, T1). Модель видит явный статус и точную инструкцию.

### Шаг 8. `ToolRegistry.call()` вызывает функцию

`registry.call`:

1. `tool = self.get("save_note")` — находит `ToolDefinition`. Если нет — `KeyError`.
2. `func = tool.func` — достаёт функцию.
3. `return func(**arguments)` — вызывает с именованными аргументами.

Тонкая обёртка, но нужна: оркестратор не знает имён функций заранее (модель возвращает имя строкой).

### Шаг 9. `save_note()` создаёт файл

Функция из `src/agent/tools/save_note.py`:

1. **Проверка заголовка:** пустой `title` → `ValueError`.
2. **Создание папки:** `notes_dir.mkdir(parents=True, exist_ok=True)`.
3. **Slug:** нижний регистр, пробелы → `_`, удаление запрещённых символов и управляющих, сохранение Unicode, обрезка до 100, `rstrip(" .")`, экранирование Windows-зарезервированных имён (`CON`, `NUL`, `COM1..9`, `LPT1..9`) префиксом `_` (шаг 6.6, T17). Пустой slug → `"note"`.
4. **Поиск свободного имени:** `slug.md`, `slug_1.md`, `slug_2.md`, … — **никогда не перезаписывает**.
5. **Запись:** `# {title}\n\n{content}\n`, UTF-8.
6. **Возврат:** `Path` к созданному файлу.

### Шаг 10. Оркестратор возвращает результат модели

Вернувшись в `Orchestrator.run`:

1. Пишет краткий результат в лог через `_summarize_for_log(result)`. Для `Path` — путь, для списка — `list[N]`, для длинной строки — обрезка. Полные тексты заметок в лог **не** попадают (шаг 6.7, T25).
2. Добавляет в `messages` два сообщения: `assistant(tool_call: save_note({...}))` и `user(tool_result: SUCCESS. ...)`.
3. **Переходит на следующую итерацию.** Вызывает `llm.chat(messages)` с расширенной историей.

### Шаг 11. Второй запрос — финал

Модель видит:

- системный промпт;
- цель пользователя;
- свой `tool_call`;
- `tool_result: SUCCESS. save_note returned: data/notes/тест_запуска.md. If this satisfies...`.

Модель решает: «задача выполнена». Ollama возвращает JSON без `tool_calls`, только с текстом. `OllamaLLM.chat` возвращает `LLMResponse(type="final", content="Заметка сохранена.")`.

Оркестратор:

    return OrchestratorResult(
        success=True,
        final_answer="Заметка сохранена.",
        steps_used=2,
        tool_results=["data/notes/тест_запуска.md"],
    )

`steps_used=2` — два обращения к модели: `tool_call` + `final`.

### Шаг 12. `_run_one` печатает результат

    if result.success:
        print(f"Готово: {result.final_answer}")
        print(f"Шагов: {result.steps_used}")
        if result.tool_results:
            print(f"Результаты инструментов: {result.tool_results}")
    else:
        print(f"Не удалось выполнить задачу. Шагов: {result.steps_used}")
        if result.error:
            print(f"Причина: {result.error}")

В консоли:

    [...] выполняется, подождите (на CPU это может занять несколько минут)
    Готово: Заметка сохранена.
    Шагов: 2
    Результаты инструментов: ['data/notes/тест_запуска.md']

### Шаг 13. Что осталось на диске

- **`data/notes/тест_запуска.md`** — новая заметка. Содержимое:

      # Тест запуска

      Привет

  При повторном запуске с тем же заголовком появится `тест_запуска_1.md`.

- **`logs/agent.log`** — строки вида:

      2026-10-28 12:34:56,789 | INFO | agent | step=1 type=tool_call
      2026-10-28 12:34:58,012 | INFO | agent | tool save_note -> data/notes/тест_запуска.md
      2026-10-28 12:35:10,345 | INFO | agent | step=2 type=final
      2026-10-28 12:35:10,346 | INFO | agent | final: Заметка сохранена.

- **`config/settings.toml`, `data/`, `logs/`** — не попадают в git.

### Полная цепочка вызовов (краткая схема)

    python scripts/run_agent.py "<цель>"
    └── run_agent.main()
        ├── argparse.parse_args() → args.goal
        ├── config.load_config() → AppConfig   (пути от _PROJECT_ROOT)
        ├── logging_setup.setup_logging() → logger
        ├── app.build_orchestrator(config, logger)
        │   ├── ToolRegistry()
        │   ├── for tool in ALL_TOOLS: registry.register(tool)
        │   ├── OllamaLLM(model, base_url, tools=ALL_TOOLS, temperature, max_tokens)
        │   └── Orchestrator(..., max_tool_failures=config.safety.max_tool_retries)
        ├── run_agent._run_one(orchestrator, goal, logger)
        │   └── orchestrator.run(goal)
        │       ├── messages = [system, user(goal)]
        │       ├── executed_calls = set(); failed_calls = {}
        │       ├── for step in 1..max_steps:
        │       │   ├── llm.chat(messages) → tool_call | final | unknown
        │       │   ├── if final: return OrchestratorResult(success=True, ...)
        │       │   ├── if tool_call:
        │       │   │   ├── call_key = tool + sorted(args)
        │       │   │   ├── if call_key in executed_calls: SKIPPED
        │       │   │   ├── elif failed_calls[call_key] >= max_tool_failures: ERROR (giving up)
        │       │   │   └── else: registry.call(tool, **args) → SUCCESS | ERROR
        │       │   └── messages += [assistant(tool_call), user(tool_result)]
        │       ├── if unknown: return OrchestratorResult(success=False, error=...)
        │       └── raise MaxStepsExceeded
        └── print("Готово: ...")

### Где что искать в коде

| Что происходит | Файл | Функция / класс |
| :--- | :--- | :--- |
| Точка входа | `scripts/run_agent.py` | `main`, `_run_one` |
| Чтение конфига | `src/agent/config.py` | `load_config`, `_PROJECT_ROOT`, `_resolve_path` |
| Логирование | `src/agent/logging_setup.py` | `setup_logging` |
| Сборка агента | `src/agent/app.py` | `build_orchestrator`, `ALL_TOOLS` |
| Цикл «цель → инструмент → результат» | `src/agent/orchestrator.py` | `Orchestrator.run`, `SYSTEM_PROMPT`, `_summarize_for_log` |
| Клиент к Ollama | `src/agent/llm_ollama.py` | `OllamaLLM.chat` |
| Реестр инструментов | `src/agent/registry.py` | `ToolRegistry.call`, `ToolDefinition` |
| Сохранение заметки | `src/agent/tools/save_note.py` | `save_note`, `_make_slug`, `SAVE_NOTE_TOOL` |
| Поиск по названию | `src/agent/tools/read_notes.py` | `read_notes`, `READ_NOTES_TOOL` |
| Поиск по содержимому | `src/agent/tools/search_notes.py` | `search_notes`, `SEARCH_NOTES_TOOL` |
| Стемминг и чтение заметок | `src/agent/tools/_search.py` | `find_match`, `find_match_with_kind`, `iter_md_files`, `load_note` |

### Что важно понять из этого разбора

1. **Агент — это цикл, а не один запрос.** Модель вызывается минимум дважды: чтобы выбрать инструмент и чтобы подтвердить финал.
2. **Модель не пишет код и не трогает файлы напрямую.** Она возвращает «запрос на вызов», остальное делает Python.
3. **Контекст инструментов — это защита.** Модель не знает, куда сохранять файлы.
4. **Три линии защиты от зацикливания:** системный промпт, детектор `executed_calls` (для успешных повторов), счётчик `failed_calls` (для падающих).
5. **Логи — главный инструмент отладки.** Полные тексты заметок в лог не пишутся, но тип ответа, имя инструмента и статус — видны.
6. **Медленно — это нормально.** На CPU 3B-модель генерирует 5–15 токенов в секунду.

---

## Работа с заметками: сохранение, поиск, чтение

Агент работает с заметками в `data/notes/` через три инструмента:

| Инструмент | Что делает | Когда используется |
| :--- | :--- | :--- |
| `save_note` | Сохраняет новую заметку в Markdown. Никогда не перезаписывает: при совпадении имени добавляет `_1`, `_2`. | «Сохрани заметку…», «Запиши…», «Создай заметку…» |
| `read_notes` | Ищет по названию (заголовку и имени файла). | «Покажи заметки про…», «Есть ли заметка под названием…», «Покажи все заметки» |
| `search_notes` | Ищет по содержимому. Возвращает фрагмент с контекстом и число совпадений. | «Найди, что я писал про…», «В какой заметке я упоминал…» |

`max_results` в обоих инструментах опционален. Если модель передаёт `null` (типично для 3B) — подставляется дефолт (50 / 5). Если `<= 0` — возвращается пустой список.

### Примеры запуска

**Сохранение новой заметки**

    python scripts/run_agent.py "Сохрани заметку 'Список покупок' с текстом 'Молоко, хлеб, яйца'"

Создаст `data/notes/список_покупок.md`:

    # Список покупок

    Молоко, хлеб, яйца

**Сохранение второй заметки с тем же названием**

    python scripts/run_agent.py "Сохрани заметку 'Список покупок' с текстом 'Ещё один список'"

Создаст `список_покупок_1.md`. Первый файл не изменится.

**Поиск по названию**

    python scripts/run_agent.py "Покажи заметки про покупки"

`read_notes(query="покупки")` найдёт `список_покупок.md` — стем «покуп» покрывает разницу в окончании.

**Поиск по содержимому**

    python scripts/run_agent.py "В какой заметке я упоминал документы?"

`search_notes(query="документы")` вернёт «Идеи проекта» с фрагментом «…Сделать локального агента для документов».

**Показать все заметки**

    python scripts/run_agent.py "Покажи все заметки"

**Проверка, что агент не вызывает инструменты зря**

    python scripts/run_agent.py "Какая сегодня погода?"

Агент ответит, что прогноз погоды вне его возможностей, и не вызовет ни один инструмент.

### Интерактивный режим

    python scripts/run_agent.py

    AI Local Agent (модель: qwen2.5-3b-agent)
    Введите цель или /quit для выхода.
    > Покажи все заметки
    [...] выполняется, подождите
    Готово: Вот все мои заметки: ...
    > /quit
    Выход.

Второй запрос выполняется быстрее первого: модель уже загружена.

### Как понять, что агент выбрал правильный инструмент

Каждый запуск пишет в `logs/agent.log`:

    step=1 type=tool_call
    tool read_notes -> list[2]
    step=2 type=final

- `type=tool_call` и `tool_name` — какой инструмент выбрала модель.
- `tool <name> -> ...` — краткий результат (для списков — `list[N]`, для `Path` — путь; полные тексты не пишутся, шаг 6.7, T25).
- `step=2 type=final` — модель завершила задачу.

Если после `tool_call` идёт **второй** `tool_call` с тем же именем и аргументами — сработала защита от повторов: второй вызов пропускается, модели возвращается `SKIPPED`. В норме этого не происходит.

### Известные ограничения текущей версии

- **Галлюцинации на неполных запросах.** На запрос `"Запиши заметку в файл"` без содержания модель может придумать заголовок. Промпт `save_note` теперь просит уточнения, а не выдумывания (шаг 6.7, T26), но на 3B галлюцинация полностью не устранена. Если содержание важно — указывайте его явно в кавычках.
- **Маршрутизация read_notes vs search_notes на 3B нестабильна.** Модель иногда путает инструменты на неоднозначных формулировках. Уточните запрос: «по названию» или «по содержимому».
- **Стемминг — эвристика.** Поиск «покупки» → «покупок» работает. Но стем «документ» — подстрока, поэтому «документы» найдёт и «документация», и «недокументированный». В `search_notes` счётчик `matches` использует `\b`-границу и «недокументированный» не считает, но `find_match` по-прежнему подстрочный (T28 — закроется в RAG).
- **Один инструмент за шаг.** Для двух действий — два запроса.
- **Ответы на английском.** Иногда 3B-модель отвечает по-английски. Это ограничение модели; переход на `qwen2.5:7b` уменьшает частоту, но замедляет CPU.

---

## Структура проекта

    ai-local-agent/
    ├── README.md
    ├── ARCHITECTURE.md
    ├── TASKS.md
    ├── TODO.md
    ├── Modelfile
    ├── pyproject.toml             ← конфиг pytest (pythonpath) и упаковки
    ├── requirements.txt
    ├── config/
    │   ├── settings.example.toml
    │   └── settings.toml           ← ваши локальные настройки (не в git)
    ├── src/
    │   ├── __init__.py             ← делает src пакетом
    │   └── agent/
    │       ├── config.py           ← загрузка настроек, _PROJECT_ROOT
    │       ├── logging_setup.py    ← настройка логов
    │       ├── registry.py         ← реестр инструментов
    │       ├── llm.py              ← протокол LLM и FakeLLM для тестов
    │       ├── llm_ollama.py       ← подключение к Ollama
    │       ├── orchestrator.py     ← цикл, статусы, _summarize_for_log
    │       ├── app.py              ← build_orchestrator, ALL_TOOLS
    │       └── tools/
    │           ├── stub.py         ← тестовый инструмент echo
    │           ├── save_note.py    ← сохранение заметок
    │           ├── read_notes.py   ← поиск по названию
    │           ├── search_notes.py ← поиск по содержимому
    │           └── _search.py      ← find_match, iter_md_files, load_note
    ├── tests/
    ├── data/                       ← ваши данные (не в git)
    │   ├── inbox/
    │   ├── notes/
    │   └── photos/
    ├── logs/                       ← логи (не в git)
    └── scripts/
        ├── run_agent.py            ← основная точка входа
        ├── smoke_step2.py          ← исторические smoke-скрипты
        ├── smoke_step3.py
        ├── smoke_step4.py
        └── smoke_step5.py

---

## Проблемы и решения

**`ollama: command not found`**

Ollama не установлен или терминал не видит его. Переустановите Ollama и откройте новый терминал.

**`ConnectionError` при запуске агента**

Ollama не запущен. Выполните `ollama serve` в отдельном терминале.

**Модель отвечает очень медленно**

Это нормально для CPU. 3B-модель генерирует 5–15 токенов в секунду. Один запрос — 30–120 секунд. Если совсем невыносимо — попробуйте `qwen2.5:1.5b` (быстрее, качество ниже).

**`does not support tools` или модель не вызывает инструменты**

Убедитесь, что используете `qwen2.5-3b-agent` (созданную через `Modelfile`), а не `qwen2.5:3b`. Если не помогает — проверьте версию Ollama: `ollama --version`. Обновите, если старше полугода.

**`ModuleNotFoundError` при запуске pytest**

Виртуальное окружение не активировано. Активируйте (см. шаг 4) и повторите. Если активировано, но ошибка остаётся — проверьте, что в корне есть `pyproject.toml` с `[tool.pytest.ini_options] pythonpath = ["."]`.

**`FileNotFoundError: config/settings.toml`**

Вы не создали локальный файл настроек. Вернитесь к шагу 6. В сообщении об ошибке будет указан точный путь, по которому искали.

**`SyntaxError: source code string cannot contain null bytes` в тестах**

Файл повреждён (часто — сохранён в UTF-16). Проверьте кодировку в VS Code (в статус-баре должно быть **UTF-8**), при необходимости «Save with Encoding → UTF-8». Проверить, что в файле нет нулевых байтов:

    Get-ChildItem -Recurse -Filter *.py src, tests | ForEach-Object {
        $bytes = [System.IO.File]::ReadAllBytes($_.FullName)
        $nulls = ($bytes | Where-Object { $_ -eq 0 }).Count
        if ($nulls -gt 0) { Write-Host "$($_.FullName): $nulls nulls" }
    }

**Тесты падают, но агент работает**

Возможно, окружение повреждено. Пересоздайте `.venv`: удалите папку, выполните `python -m venv .venv`, активируйте, установите зависимости.

**Хочу посмотреть, что делал агент**

Откройте `logs/agent.log`. Там видны типы ответов, имена инструментов, краткие результаты. Полные тексты заметок в лог не пишутся (шаг 6.7, T25).

**Хочу изменить `max_steps` или `max_tool_retries`**

Отредактируйте `config/settings.toml`:

    [llm]
    max_steps = 15

    [safety]
    max_tool_retries = 3

После правки — перезапустите агент.

---

## Лицензия и приватность

Проект работает локально. Никакие данные не отправляются в интернет. Модель, документы и логи остаются на вашем компьютере.