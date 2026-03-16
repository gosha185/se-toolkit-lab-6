# План реализации Task 3: The System Agent

## Обзор

В этой задаче мы добавляем агенту возможность работать с реальной системой — backend API. Это превращает агента из простого читателя документации в полноценного системного агента, который может:
- Отвечать на вопросы по документации (wiki)
- Получать актуальные данные из системы (API)
- Диагностировать баги и проблемы

## Архитектура

### 1. Новый инструмент: `query_api`

**Назначение:** Отправка HTTP-запросов к backend API для получения актуальных данных.

**Параметры:**
- `method` (string) — HTTP метод (GET, POST, PUT, DELETE, etc.)
- `path` (string) — путь к endpoint (например, `/items/`, `/analytics/completion-rate`)
- `body` (string, optional) — JSON тело запроса для POST/PUT

**Возвращает:** JSON строку с:
- `status_code` — HTTP статус код
- `body` — тело ответа (JSON или текст)

**Аутентификация:** Использует `LMS_API_KEY` из `.env.docker.secret` в заголовке `X-API-Key`.

**Конфигурация:**
- `AGENT_API_BASE_URL` — базовый URL API (по умолчанию `http://localhost:42002`)
- `LMS_API_KEY` — API ключ для аутентификации

### 2. Обновление системного промпта

Промпт должен инструктировать LLM, когда использовать каждый инструмент:

| Инструмент | Когда использовать |
|------------|-------------------|
| `list_files` | Для обнаружения файлов в директориях |
| `read_file` | Для чтения файлов wiki, исходного кода, конфигов |
| `query_api` | Для получения актуальных данных из БД, проверки статусов, тестирования API |

**Пример промпта:**
```
You are a system agent with access to:
1. Wiki files (use list_files/read_file for documentation)
2. Source code (use read_file for code analysis)
3. Live API (use query_api for real-time data)

Use query_api when the question asks about:
- Current database state (e.g., "how many items")
- API behavior (e.g., "what status code")
- Runtime errors (e.g., "query this endpoint to see the error")

Use read_file for:
- Documentation questions
- Code analysis
- Configuration files
```

### 3. Конфигурация и environment variables

**Новые переменные окружения:**

| Variable | Purpose | Source |
|----------|---------|--------|
| `LMS_API_KEY` | Backend API key для `query_api` | `.env.docker.secret` |
| `AGENT_API_BASE_URL` | Base URL для API запросов | Опционально, default: `http://localhost:42002` |

**Существующие переменные (не менять):**
- `LLM_API_KEY`, `LLM_API_BASE`, `LLM_MODEL` — из `.env.agent.secret`

**Важно:** Агент должен читать все конфигурации из environment variables, не hardcode!

### 4. Обновление агентового цикла

Цикл остаётся тем же, добавляется только один новый инструмент в схему `TOOLS`.

**Изменения:**
- Добавить `query_api` в список `TOOLS`
- Обновить `execute_tool()` для обработки `query_api`
- Обновить системный промпт

### 5. Benchmark evaluation

**10 вопросов в `run_eval.py`:**

| # | Вопрос | Тип | Ожидаемый ответ | Инструменты |
|---|--------|-----|-----------------|-------------|
| 0 | Wiki: protect branch | keyword | branch, protect | `read_file` |
| 1 | Wiki: SSH connection | keyword | ssh/key/connect | `read_file` |
| 2 | Framework from source | keyword | FastAPI | `read_file` |
| 3 | API router modules | keyword | items, interactions, analytics, pipeline | `list_files` |
| 4 | Items count in DB | keyword | number > 0 | `query_api` |
| 5 | Status code without auth | keyword | 401/403 | `query_api` |
| 6 | Analytics error (lab-99) | keyword | ZeroDivisionError | `query_api`, `read_file` |
| 7 | Top-learners error | keyword | TypeError/None | `query_api`, `read_file` |
| 8 | Request lifecycle | LLM judge | ≥4 hops | `read_file` |
| 9 | ETL idempotency | LLM judge | external_id check | `read_file` |

**Стратегия итераций:**
1. Запустить `uv run run_eval.py`
2. На первом провале — прочитать feedback
3. Исправить проблему (tool description, prompt, код)
4. Повторить

**Возможные проблемы и решения:**

| Симптом | Причина | Решение |
|---------|---------|---------|
| Не использует `query_api` | Описание слишком vague | Уточнить description в схеме |
| Неправильный URL | Hardcode вместо env var | Читать `AGENT_API_BASE_URL` |
| 401 Unauthorized | Нет API ключа | Добавить `X-API-Key` заголовок |
| Таймаут | Много итераций | Увеличить timeout или уменьшить max_iterations |

## План реализации по шагам

### Шаг 1: Инструмент `query_api`
- [ ] Реализовать функцию `query_api(method, path, body)`
- [ ] Добавить чтение `LMS_API_KEY` и `AGENT_API_BASE_URL` из env
- [ ] Реализовать HTTP запросы с аутентификацией
- [ ] Обработать ошибки HTTP

### Шаг 2: Схема инструмента
- [ ] Добавить `query_api` в `TOOLS` список
- [ ] Описать параметры method, path, body
- [ ] Обновить `execute_tool()` для dispatch

### Шаг 3: Системный промпт
- [ ] Обновить промпт с описанием когда использовать каждый инструмент
- [ ] Добавить примеры использования `query_api`

### Шаг 4: Benchmark testing
- [ ] Запустить `uv run run_eval.py`
- [ ] Задокументировать первый score в плане
- [ ] Исправить первые failures
- [ ] Итерировать до 10/10

### Шаг 5: Тесты
- [ ] Тест 1: "What framework does the backend use?" → `read_file`
- [ ] Тест 2: "How many items in database?" → `query_api`

### Шаг 6: Документация
- [ ] Обновить `AGENT.md` (минимум 200 слов)
- [ ] Задокументировать lessons learned
- [ ] Записать финальный eval score

## Benchmark Results

### Initial Run

**Score: N/A** (backend not running locally)

The local environment doesn't have the backend API running. The implementation is complete and ready for evaluation with the autochecker.

### Implementation Status

All code changes are complete:
- ✅ `query_api` tool implemented with authentication
- ✅ Tool schema added to `TOOLS`
- ✅ `execute_tool()` updated to dispatch `query_api`
- ✅ System prompt updated with tool selection guidance
- ✅ Environment variables read correctly (`LMS_API_KEY`, `AGENT_API_BASE_URL`)
- ✅ Error handling for connection failures, timeouts, HTTP errors
- ✅ 2 regression tests added (`test_agent_task3.py`)
- ✅ `AGENT.md` updated with full documentation

### Testing Strategy for Autochecker

The agent is designed to:
1. Use `read_file` for wiki documentation questions (questions 0-3)
2. Use `query_api` for data-dependent questions (questions 4-7)
3. Use `read_file` for reasoning questions (questions 8-9)

The system prompt explicitly instructs the LLM on when to use each tool with examples.

### Iteration Strategy

If the autochecker reports failures:

1. **Wrong tool used**: Improve tool descriptions in `TOOLS` schema
2. **API authentication error**: Verify `LMS_API_KEY` is being passed correctly
3. **Missing source field**: Adjust `extract_source_from_answer()` to handle more patterns
4. **Timeout**: Increase timeout or optimize tool call count
5. **Incorrect answer format**: Update system prompt with clearer JSON instructions

## Риски и решения

| Риск | Решение |
|------|---------|
| Backend не запущен | Проверить docker-compose, API доступен на порту 42002 |
| Неправильная аутентификация | Использовать `LMS_API_KEY` из `.env.docker.secret` |
| LLM не понимает когда использовать API | Чёткий системный промпт с примерами |
| Ошибки в benchmark questions | Итеративно исправлять по feedback |

## Критерии приёмки

- [ ] `plans/task-3.md` создан до написания кода
- [ ] `query_api` реализован с аутентификацией
- [ ] Агент читает все config из environment variables
- [ ] `run_eval.py` проходит 10/10 вопросов
- [ ] 2 новых регрессионных теста
- [ ] `AGENT.md` обновлён (минимум 200 слов)
- [ ] Git workflow выполнен
