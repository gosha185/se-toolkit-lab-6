#!/usr/bin/env python3
"""
Agent CLI - An agentic system with tools for navigating the project wiki.

Usage:
    uv run agent.py "Your question here"

Output:
    JSON with "answer", "source", and "tool_calls" fields to stdout.
    All debug output goes to stderr.
"""

import json
import os
import re
import sys
from typing import Any
from pathlib import Path

import httpx

# Project root directory
PROJECT_ROOT = Path(__file__).parent.resolve()


def load_config() -> dict[str, str | None]:
    """Load configuration from environment variables."""
    config = {
        "api_key": os.environ.get("LLM_API_KEY"),
        "api_base": os.environ.get("LLM_API_BASE"),
        "model": os.environ.get("LLM_MODEL"),
    }

    missing = [key for key, value in config.items() if not value]
    if missing:
        print(
            f"Error: Missing required environment variables: {', '.join(missing)}",
            file=sys.stderr,
        )
        print(
            "Please set LLM_API_KEY, LLM_API_BASE, and LLM_MODEL in .env.agent.secret",
            file=sys.stderr,
        )
        sys.exit(1)

    return config


def is_safe_path(path: str) -> tuple[bool, Path | None]:
    """
    Check if a path is safe to access (within project directory).

    Args:
        path: Relative path from project root

    Returns:
        Tuple of (is_safe, resolved_path). If not safe, resolved_path is None.
    """
    # Reject paths with .. components
    if ".." in path.split(os.sep) or ".." in path.split("/"):
        return False, None

    # Resolve the full path
    try:
        full_path = (PROJECT_ROOT / path).resolve()
    except (ValueError, OSError):
        return False, None

    # Check if the resolved path is within project root
    try:
        full_path.relative_to(PROJECT_ROOT)
        return True, full_path
    except ValueError:
        return False, None


def read_file(path: str) -> str:
    """
    Read a file from the project repository.

    Args:
        path: Relative path from project root

    Returns:
        File contents as a string, or an error message if the file doesn't exist.
    """
    safe, full_path = is_safe_path(path)
    if not safe or full_path is None:
        return f"Error: Access denied - path '{path}' is outside project directory"

    if not full_path.exists():
        return f"Error: File not found: {path}"

    if not full_path.is_file():
        return f"Error: Not a file: {path}"

    try:
        return full_path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as e:
        return f"Error: Cannot read file: {e}"


def list_files(path: str) -> str:
    """
    List files and directories at a given path.

    Args:
        path: Relative directory path from project root

    Returns:
        Newline-separated listing of entries, or an error message.
    """
    safe, full_path = is_safe_path(path)
    if not safe or full_path is None:
        return f"Error: Access denied - path '{path}' is outside project directory"

    if not full_path.exists():
        return f"Error: Directory not found: {path}"

    if not full_path.is_dir():
        return f"Error: Not a directory: {path}"

    try:
        entries = sorted(full_path.iterdir())
        return "\n".join(entry.name for entry in entries)
    except OSError as e:
        return f"Error: Cannot list directory: {e}"


def get_api_config() -> tuple[str, str | None]:
    """
    Get API configuration from environment variables.

    Returns:
        Tuple of (base_url, api_key). api_key may be None if not set.
    """
    base_url = os.environ.get("AGENT_API_BASE_URL", "http://localhost:42002")
    api_key = os.environ.get("LMS_API_KEY")
    return base_url, api_key


def query_api(method: str, path: str, body: str | None = None) -> str:
    """
    Call the backend API with authentication.

    Args:
        method: HTTP method (GET, POST, PUT, DELETE, etc.)
        path: API path (e.g., '/items/', '/analytics/completion-rate')
        body: Optional JSON request body for POST/PUT requests

    Returns:
        JSON string with status_code and body, or error message.
    """
    base_url, api_key = get_api_config()

    # Normalize path
    if not path.startswith("/"):
        path = f"/{path}"

    url = f"{base_url}{path}"

    headers = {
        "Content-Type": "application/json",
    }

    # Add API key for authentication
    if api_key:
        headers["X-API-Key"] = api_key

    print(f"Querying API: {method} {url}", file=sys.stderr)

    try:
        with httpx.Client(timeout=30.0) as client:
            if method.upper() == "GET":
                response = client.get(url, headers=headers)
            elif method.upper() == "POST":
                response = client.post(url, headers=headers, content=body or "{}")
            elif method.upper() == "PUT":
                response = client.put(url, headers=headers, content=body or "{}")
            elif method.upper() == "DELETE":
                response = client.delete(url, headers=headers)
            elif method.upper() == "PATCH":
                response = client.patch(url, headers=headers, content=body or "{}")
            else:
                return f"Error: Unsupported HTTP method '{method}'"

            # Build response object
            result = {
                "status_code": response.status_code,
                "body": response.text,
            }

            # Try to parse body as JSON for cleaner output
            try:
                result["body"] = response.json()
            except (json.JSONDecodeError, ValueError):
                pass

            return json.dumps(result, ensure_ascii=False)

    except httpx.TimeoutException:
        return json.dumps({"error": "API request timed out (30s limit)"})
    except httpx.ConnectError as e:
        return json.dumps({"error": f"Cannot connect to API at {base_url}: {e}"})
    except httpx.HTTPError as e:
        return json.dumps({"error": f"HTTP error: {e}"})


# Tool definitions for LLM function calling
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read the contents of a file from the project repository. Use this to read documentation files.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Relative path from project root (e.g., 'wiki/git-workflow.md')",
                    }
                },
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_files",
            "description": "List files and directories at a given path in the project repository.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Relative directory path from project root (e.g., 'wiki')",
                    }
                },
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "query_api",
            "description": "Call the backend API to get real-time data from the running system. Use this for questions about database state, API behavior, status codes, or runtime errors.",
            "parameters": {
                "type": "object",
                "properties": {
                    "method": {
                        "type": "string",
                        "description": "HTTP method (GET, POST, PUT, DELETE, etc.)",
                    },
                    "path": {
                        "type": "string",
                        "description": "API path (e.g., '/items/', '/analytics/completion-rate')",
                    },
                    "body": {
                        "type": "string",
                        "description": "Optional JSON request body for POST/PUT requests",
                    },
                },
                "required": ["method", "path"],
            },
        },
    },
]


def execute_tool(name: str, arguments: dict[str, Any]) -> str:
    """
    Execute a tool and return its result.

    Args:
        name: Tool name ('read_file', 'list_files', or 'query_api')
        arguments: Tool arguments as a dict

    Returns:
        Tool result as a string
    """
    if name == "read_file":
        path = arguments.get("path", "")
        return read_file(str(path))
    elif name == "list_files":
        path = arguments.get("path", "")
        return list_files(str(path))
    elif name == "query_api":
        method = arguments.get("method", "GET")
        path = arguments.get("path", "")
        body = arguments.get("body")
        return query_api(str(method), str(path), body)
    else:
        return f"Error: Unknown tool '{name}'"


def call_llm(
    messages: list[dict[str, Any]],
    config: dict[str, Any],
    tools: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """
    Call the LLM API and return the parsed response.

    Args:
        messages: List of message dicts for the conversation
        config: Configuration dict with api_key, api_base, model
        tools: Optional list of tool definitions for function calling

    Returns:
        Parsed response dict with 'message' and optionally 'tool_calls'

    Raises:
        SystemExit: On HTTP errors or timeout
    """
    url = f"{config['api_base']}/chat/completions"

    headers = {
        "Authorization": f"Bearer {config['api_key']}",
        "Content-Type": "application/json",
    }

    payload = {
        "model": config["model"],
        "messages": messages,
        "temperature": 0.7,
    }

    if tools:
        payload["tools"] = tools

    print(f"Calling LLM at {url}...", file=sys.stderr)

    try:
        with httpx.Client(timeout=60.0) as client:
            response = client.post(url, headers=headers, json=payload)
            response.raise_for_status()
    except httpx.TimeoutException:
        print("Error: LLM request timed out (60s limit)", file=sys.stderr)
        sys.exit(1)
    except httpx.HTTPError as e:
        print(f"Error: HTTP request failed: {e}", file=sys.stderr)
        httpx_response = getattr(e, "response", None)
        if httpx_response is not None:
            print(f"Response: {httpx_response.text}", file=sys.stderr)
        sys.exit(1)

    data = response.json()

    try:
        message = data["choices"][0]["message"]
    except (KeyError, IndexError) as e:
        print(f"Error: Unexpected API response format: {e}", file=sys.stderr)
        print(f"Full response: {data}", file=sys.stderr)
        sys.exit(1)

    return message


def extract_source_from_answer(content: str) -> tuple[str, str]:
    """
    Extract the answer and source from LLM content.

    Looks for patterns like:
    - {"answer": "...", "source": "..."}
    - Plain text answer with source reference

    Args:
        content: Raw text content from LLM

    Returns:
        Tuple of (answer, source). Source defaults to empty string if not found.
    """
    text = content.strip()

    # Handle markdown code blocks
    if text.startswith("```json"):
        text = text.removeprefix("```json").removesuffix("```").strip()
    elif text.startswith("```"):
        text = text.removeprefix("```").removesuffix("```").strip()

    # Try to parse as JSON
    try:
        parsed = json.loads(text)
        answer = parsed.get("answer", text)
        source = parsed.get("source", "")
        return str(answer), str(source)
    except json.JSONDecodeError:
        pass

    # Try to extract source from text (look for wiki/...md#... patterns)
    source_match = re.search(r"(wiki/[\w\-/]+\.md(?:#[\w\-]+)?)", text)
    source = source_match.group(1) if source_match else ""

    # Return the full text as answer
    return text, source


def run_agentic_loop(question: str, config: dict[str, Any]) -> dict[str, Any]:
    """
    Run the agentic loop to answer a question using tools.

    Args:
        question: The user's question
        config: Configuration dict

    Returns:
        Dict with 'answer', 'source', and 'tool_calls' fields
    """
    # System prompt instructing the LLM how to use tools
    system_prompt = (
        "You are a system agent with access to three types of tools:\n\n"
        "1. WIKI TOOLS (list_files, read_file): Use these to read documentation from the wiki/ directory.\n"
        "2. SOURCE CODE (read_file): Use this to read Python source files, configuration files, etc.\n"
        "3. LIVE API (query_api): Use this to query the running backend API for real-time data.\n\n"
        "WHEN TO USE query_api:\n"
        "- Questions about current database state (e.g., 'how many items are in the database')\n"
        "- Questions about API behavior (e.g., 'what status code does the API return')\n"
        "- Questions about runtime errors (e.g., 'query this endpoint to see the error')\n\n"
        "WHEN TO USE read_file:\n"
        "- Documentation questions (wiki/ files)\n"
        "- Code analysis (backend/, agent.py, etc.)\n"
        "- Configuration files (docker-compose.yml, Dockerfile, etc.)\n\n"
        "WHEN TO USE list_files:\n"
        "- Discovering what files exist in a directory\n"
        "- Exploring the project structure\n\n"
        "IMPORTANT: For wiki/documentation questions, include the source reference (file path with optional section anchor like 'wiki/file.md#section'). "
        "For API or source code questions, the source field is optional.\n\n"
        "When you have found the answer, respond with a JSON object containing:\n"
        '  - "answer": your final answer as a string\n'
        '  - "source": the wiki file path with optional section anchor (e.g., "wiki/git-workflow.md#resolving-merge-conflicts"), or empty string for API/source questions\n'
        "Do not make up file paths or API endpoints. Only reference files and endpoints you have actually read or queried."
    )

    # Initialize conversation
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": question},
    ]

    # Track all tool calls
    all_tool_calls: list[dict[str, Any]] = []

    # Agentic loop
    max_iterations = 10
    iteration = 0

    while iteration < max_iterations:
        iteration += 1
        print(f"\n[Iteration {iteration}]", file=sys.stderr)

        # Call LLM with tool definitions
        response = call_llm(messages, config, tools=TOOLS)

        # Check for tool calls
        tool_calls = response.get("tool_calls")

        if not tool_calls:
            # No tool calls - this is the final answer
            print("[No tool calls - final answer]", file=sys.stderr)
            content = response.get("content", "")
            answer, source = extract_source_from_answer(content)
            break

        # Execute tool calls
        print(f"[Executing {len(tool_calls)} tool call(s)]", file=sys.stderr)

        for tool_call in tool_calls:
            function = tool_call.get("function", {})
            tool_name = function.get("name", "unknown")
            tool_args_str = function.get("arguments", "{}")

            # Parse arguments (may be a JSON string)
            try:
                tool_args: dict[str, Any] = (
                    json.loads(tool_args_str)
                    if isinstance(tool_args_str, str)
                    else tool_args_str
                )
            except json.JSONDecodeError:
                tool_args = {}

            # Record the tool call
            tool_call_record: dict[str, Any] = {
                "tool": tool_name,
                "args": tool_args,
            }

            # Execute the tool
            result = execute_tool(tool_name, tool_args)
            tool_call_record["result"] = result
            all_tool_calls.append(tool_call_record)

            print(
                f"  - {tool_name}({tool_args}) -> {len(result)} chars", file=sys.stderr
            )

            # Add tool result to conversation history
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tool_call.get("id", ""),
                    "content": result,
                    "name": tool_name,
                }
            )

    else:
        # Max iterations reached
        print(f"\n[Max iterations ({max_iterations}) reached]", file=sys.stderr)
        answer = "I reached the maximum number of tool calls (10) without finding a complete answer."
        source = ""

    return {
        "answer": answer,
        "source": source,
        "tool_calls": all_tool_calls,
    }


def main() -> None:
    """Main entry point."""
    if len(sys.argv) < 2:
        print('Usage: uv run agent.py "<question>"', file=sys.stderr)
        sys.exit(1)

    question = sys.argv[1]

    # Load configuration
    config = load_config()
    print(f"Using model: {config['model']}", file=sys.stderr)

    # Run agentic loop
    result = run_agentic_loop(question, config)

    # Output only valid JSON to stdout
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
