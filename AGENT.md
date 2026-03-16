# Agent Documentation

## Overview

This agent is a CLI tool that implements an **agentic loop** with tools for navigating the project wiki. It connects to an LLM (Qwen Code API) and can read files, list directories, and reason about the results to answer documentation questions.

## Architecture

### Components

1. **Config Loader** (`load_config()`)
   - Reads `LLM_API_KEY`, `LLM_API_BASE`, `LLM_MODEL` from environment variables
   - Validates all required variables are present
   - Exits with error code 1 if any are missing

2. **Path Security** (`is_safe_path()`)
   - Validates that file paths don't escape the project directory
   - Rejects paths containing `..` components
   - Resolves paths and verifies they're within `PROJECT_ROOT`

3. **Tools**
   - **`read_file(path)`**: Reads file contents with security validation
   - **`list_files(path)`**: Lists directory entries with security validation
   - Both tools return error messages for invalid paths

4. **Tool Schemas** (`TOOLS`)
   - Function-calling definitions for LLM API
   - Describes tool names, parameters, and purposes
   - Sent with each LLM request to enable tool calling

5. **Tool Executor** (`execute_tool()`)
   - Dispatches tool calls to appropriate functions
   - Returns tool results as strings for LLM consumption

6. **LLM Client** (`call_llm()`)
   - Uses `httpx` library for HTTP requests
   - Sends POST request to `{LLM_API_BASE}/chat/completions`
   - Supports tool definitions for function calling
   - 60-second timeout
   - Handles HTTP errors and timeouts

7. **Response Parser** (`extract_source_from_answer()`)
   - Extracts `answer` and `source` from LLM content
   - Handles JSON responses and plain text
   - Uses regex to find wiki file references

8. **Agentic Loop** (`run_agentic_loop()`)
   - Implements ReAct-style reasoning loop
   - Maximum 10 iterations to prevent infinite loops
   - Manages conversation history with tool results
   - Returns structured result with `answer`, `source`, `tool_calls`

9. **Main Entry Point** (`main()`)
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

## LLM Provider

**Provider:** Qwen Code API
- **Model:** `qwen3-coder-plus`
- **API Compatibility:** OpenAI chat completions API
- **Function Calling:** Uses `tools` parameter for tool definitions

## Configuration

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
| `source`     | string | Wiki file reference with optional section anchor |
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

The system prompt instructs the LLM to:

1. Use `list_files` to discover files in directories
2. Use `read_file` to read file contents
3. Always include source references (file path + section anchor)
4. Respond with JSON containing `answer` and `source` fields
5. Not make up file paths — only reference files actually read

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
| Max iterations (10) | Returns partial answer with warning   |

## Testing

Run the regression tests:

```bash
# Task 1 test
uv run pytest test_agent_task1.py -v

# Task 2 tests
uv run pytest test_agent_task2.py -v
```

The Task 2 tests verify:
- Agent uses `read_file` for questions about specific topics
- Agent uses `list_files` for questions about directory contents
- Output contains valid `answer`, `source`, and `tool_calls` fields
- Source references the correct wiki files

## Development

### Adding New Tools

1. Implement the tool function with security validation
2. Add tool schema to `TOOLS` list
3. Update `execute_tool()` to handle the new tool
4. Update system prompt to describe the new tool
5. Update this documentation

### Code Style

- Type hints for all functions
- Docstrings for all public functions
- Error messages to stderr
- Functional decomposition for testability

## Files

| File               | Purpose                    |
| ------------------ | -------------------------- |
| `agent.py`         | Main CLI agent             |
| `.env.agent.secret`| Local configuration        |
| `AGENT.md`         | This documentation         |
| `plans/task-2.md`  | Implementation plan        |
| `test_agent_task2.py` | Regression tests for Task 2 |
