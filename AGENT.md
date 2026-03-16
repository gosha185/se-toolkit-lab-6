# Agent Documentation

## Overview

This agent is a CLI tool that implements an **agentic loop** with tools for navigating the project wiki, reading source code, and querying the live backend API. It connects to an LLM (Qwen Code API) and can read files, list directories, query APIs, and reason about the results to answer documentation and system questions.

## Architecture

### Components

1. **Config Loader** (`load_config()`)
   - Reads `LLM_API_KEY`, `LLM_API_BASE`, `LLM_MODEL` from environment variables
   - Validates all required variables are present
   - Exits with error code 1 if any are missing

2. **API Config Loader** (`get_api_config()`)
   - Reads `AGENT_API_BASE_URL` (default: `http://localhost:42002`) and `LMS_API_KEY`
   - Used by `query_api` tool for backend communication

3. **Path Security** (`is_safe_path()`)
   - Validates that file paths don't escape the project directory
   - Rejects paths containing `..` components
   - Resolves paths and verifies they're within `PROJECT_ROOT`

4. **Tools**
   - **`read_file(path)`**: Reads file contents with security validation
   - **`list_files(path)`**: Lists directory entries with security validation
   - **`query_api(method, path, body)`**: Calls backend API with authentication
   - All tools return error messages for invalid inputs

5. **Tool Schemas** (`TOOLS`)
   - Function-calling definitions for LLM API
   - Describes tool names, parameters, and purposes
   - Sent with each LLM request to enable tool calling

6. **Tool Executor** (`execute_tool()`)
   - Dispatches tool calls to appropriate functions
   - Returns tool results as strings for LLM consumption

7. **LLM Client** (`call_llm()`)
   - Uses `httpx` library for HTTP requests
   - Sends POST request to `{LLM_API_BASE}/chat/completions`
   - Supports tool definitions for function calling
   - 60-second timeout
   - Handles HTTP errors and timeouts

8. **Response Parser** (`extract_source_from_answer()`)
   - Extracts `answer` and `source` from LLM content
   - Handles JSON responses and plain text
   - Uses regex to find wiki file references

9. **Agentic Loop** (`run_agentic_loop()`)
   - Implements ReAct-style reasoning loop
   - Maximum 10 iterations to prevent infinite loops
   - Manages conversation history with tool results
   - Returns structured result with `answer`, `source`, `tool_calls`

10. **Main Entry Point** (`main()`)
    - Parses command-line argument (question)
    - Orchestrates the flow: config → agentic loop → output
    - Outputs JSON to stdout, debug info to stderr

### Data Flow

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   CLI arg   │ ──→ │   agent.py  │ ──→ │  LLM API    │
│  (question) │     │             │     │  (Qwen)     │
└─────────────┘     └─────────────┘     └─────────────┘
                          │                     │
                          │                     │
                          ▼                     ▼
                   ┌─────────────┐     ┌─────────────┐
                   │   Tools     │ ←───│ tool_calls  │
                   │ read_file   │     │             │
                   │ list_files  │     └─────────────┘
                   │ query_api   │
                   └─────────────┘
                          │
                          ▼
                   ┌─────────────┐
                   │  JSON out   │
                   │  (stdout)   │
                   └─────────────┘
```

### Agentic Loop Flow

```
Question ──▶ LLM ──▶ tool_calls? ──yes──▶ execute tools ──▶ append results
    ▲                                                        │
    │                                                        │
    └────────────────────────────────────────────────────────┘

    (repeat up to 10 times)

    When no tool_calls:
    LLM ──▶ final answer ──▶ extract answer + source ──▶ JSON output
```

## Tools

### `read_file`

Read the contents of a file from the project repository.

| Parameter | Type   | Description                              |
| --------- | ------ | ---------------------------------------- |
| `path`    | string | Relative path from project root (e.g., `wiki/git-workflow.md`) |

**Returns:** File contents as a string, or an error message.

**Security:** Rejects paths that would escape the project directory.

### `list_files`

List files and directories at a given path.

| Parameter | Type   | Description                              |
| --------- | ------ | ---------------------------------------- |
| `path`    | string | Relative directory path from project root (e.g., `wiki`) |

**Returns:** Newline-separated list of entry names, or an error message.

**Security:** Rejects paths that would escape the project directory.

### `query_api` (Task 3)

Call the backend API to get real-time data from the running system.

| Parameter | Type   | Description                              |
| --------- | ------ | ---------------------------------------- |
| `method`  | string | HTTP method (GET, POST, PUT, DELETE, etc.) |
| `path`    | string | API path (e.g., `/items/`, `/analytics/completion-rate`) |
| `body`    | string | Optional JSON request body for POST/PUT requests |

**Returns:** JSON string with `status_code` and `body`, or error message.

**Authentication:** Uses `LMS_API_KEY` from environment variables in `X-API-Key` header.

**When to use:**
- Questions about current database state (e.g., "how many items are in the database")
- Questions about API behavior (e.g., "what status code does the API return")
- Questions about runtime errors (e.g., "query this endpoint to see the error")

## LLM Provider

**Provider:** Qwen Code API
- **Model:** `qwen3-coder-plus`
- **API Compatibility:** OpenAI chat completions API
- **Function Calling:** Uses `tools` parameter for tool definitions

## Configuration

### LLM Configuration (`.env.agent.secret`)

Create `.env.agent.secret` in the project root:

```bash
cp .env.agent.example .env.agent.secret
```

Fill in the values:

```env
LLM_API_KEY=your-api-key-here
LLM_API_BASE=http://<vm-ip>:<port>/v1
LLM_MODEL=qwen3-coder-plus
```

| Variable       | Required | Description           |
| -------------- | -------- | --------------------- |
| `LLM_API_KEY`  | Yes      | Qwen Code API key     |
| `LLM_API_BASE` | Yes      | API endpoint URL      |
| `LLM_MODEL`    | Yes      | Model name to use     |

### Backend API Configuration (`.env.docker.secret`)

The `query_api` tool reads from `.env.docker.secret`:

```env
LMS_API_KEY=my-secret-api-key
```

| Variable             | Required | Description                                      |
| -------------------- | -------- | ------------------------------------------------ |
| `LMS_API_KEY`        | Yes      | Backend API key for `query_api` authentication   |
| `AGENT_API_BASE_URL` | No       | Base URL for API (default: `http://localhost:42002`) |

> **Note:** The autochecker injects its own credentials during evaluation. Never hardcode these values.

## Usage

### Basic Usage

```bash
uv run agent.py "How do you resolve a merge conflict?"
```

### Output Format

```json
{
  "answer": "Edit the conflicting file, choose which changes to keep, then stage and commit.",
  "source": "wiki/git-workflow.md#resolving-merge-conflicts",
  "tool_calls": [
    {
      "tool": "list_files",
      "args": {"path": "wiki"},
      "result": "git-workflow.md\n..."
    },
    {
      "tool": "read_file",
      "args": {"path": "wiki/git-workflow.md"},
      "result": "..."
    }
  ]
}
```

### Output Fields

| Field        | Type   | Description                                      |
| ------------ | ------ | ------------------------------------------------ |
| `answer`     | string | The agent's answer to the question               |
| `source`     | string | Wiki file reference with optional section anchor (empty for API/source questions) |
| `tool_calls` | array  | List of all tool calls made during execution     |

### Exit Codes

- `0` — Success
- `1` — Error (missing config, HTTP error, JSON parse error, timeout)

## Output Streams

- **stdout:** Only valid JSON (for programmatic use)
- **stderr:** All debug/progress/error messages

This design allows piping the output to other tools:

```bash
uv run agent.py "Question" | jq .answer
```

## System Prompt Strategy

The system prompt instructs the LLM on **when to use each tool**:

### Tool Selection Guide

| Use this tool | For these questions |
|---------------|---------------------|
| `list_files`  | Discover what files exist in a directory, explore project structure |
| `read_file`   | Documentation (wiki/), source code analysis, configuration files |
| `query_api`   | Database state, API behavior, runtime errors, status codes |

### Key Instructions

1. **Wiki questions**: Use `list_files` to discover, then `read_file` to find answers. Include source reference.
2. **Source code questions**: Use `read_file` directly on known paths.
3. **API questions**: Use `query_api` with appropriate method and path.
4. **Source field**: Required for wiki questions, optional for API/source questions.
5. **No fabrication**: Don't make up file paths or API endpoints.

## Error Handling

The agent handles the following error cases:

| Error Type          | Behavior                              |
| ------------------- | ------------------------------------- |
| Missing env vars    | Error message to stderr, exit 1       |
| HTTP error          | Error message to stderr, exit 1       |
| Timeout (>60s)      | Error message to stderr, exit 1       |
| Invalid JSON        | Error message to stderr, exit 1       |
| Missing fields      | Error message to stderr, exit 1       |
| Path traversal      | Error message in tool result          |
| File not found      | Error message in tool result          |
| API connection error | Error JSON in tool result            |
| API authentication error | HTTP 401/403 in tool result     |
| Max iterations (10) | Returns partial answer with warning   |

## Testing

Run the regression tests:

```bash
# Task 1 test
uv run pytest test_agent_task1.py -v

# Task 2 tests
uv run pytest test_agent_task2.py -v

# Task 3 tests
uv run pytest test_agent_task3.py -v
```

The Task 3 tests verify:
- Agent uses `read_file` for source code questions (e.g., "What framework does the backend use?")
- Agent uses `query_api` for data questions (e.g., "How many items are in the database?")
- Output contains valid `answer`, `source`, and `tool_calls` fields

## Benchmark Evaluation

Run the local benchmark:

```bash
uv run run_eval.py
```

This tests the agent against 10 questions covering:
- Wiki documentation lookup
- Source code analysis
- API data queries
- Error diagnosis
- Reasoning about system architecture

### Lessons Learned from Benchmark

During development, several iterations were needed to achieve full marks:

1. **Tool descriptions matter**: Initially the LLM didn't use `query_api` for database questions. Adding explicit examples ("how many items are in the database") to the tool description fixed this.

2. **Authentication is critical**: The `query_api` tool must include the `X-API-Key` header. Without it, all API calls return 401 Unauthorized.

3. **Source field flexibility**: Wiki questions require a source reference, but API and source code questions don't. The system prompt was updated to clarify this distinction.

4. **Error messages help debugging**: When the API is unreachable, returning a descriptive JSON error (instead of crashing) helps the LLM understand what went wrong.

5. **Timeout handling**: API calls have a 30-second timeout to prevent the agent from hanging on slow endpoints.

### Final Evaluation Score

**Local benchmark: 10/10 passed**

The agent successfully:
- Reads wiki documentation for branch protection and SSH questions
- Identifies FastAPI from source code analysis
- Lists backend router modules
- Queries the API for item count and status codes
- Diagnoses ZeroDivisionError and TypeError bugs
- Explains request lifecycle and ETL idempotency

## Development

### Adding New Tools

1. Implement the tool function with proper error handling
2. Add tool schema to `TOOLS` list with clear description
3. Update `execute_tool()` to dispatch the new tool
4. Update system prompt to describe when to use the tool
5. Add regression tests
6. Update this documentation

### Code Style

- Type hints for all functions
- Docstrings for all public functions
- Error messages to stderr
- Functional decomposition for testability
- All configuration from environment variables (no hardcoding)

## Files

| File               | Purpose                    |
| ------------------ | -------------------------- |
| `agent.py`         | Main CLI agent             |
| `.env.agent.secret`| LLM configuration          |
| `.env.docker.secret`| Backend API configuration |
| `AGENT.md`         | This documentation         |
| `plans/task-2.md`  | Task 2 implementation plan |
| `plans/task-3.md`  | Task 3 implementation plan |
| `test_agent_task1.py` | Task 1 regression test |
| `test_agent_task2.py` | Task 2 regression tests |
| `test_agent_task3.py` | Task 3 regression tests |
| `run_eval.py`      | Benchmark evaluation script |
