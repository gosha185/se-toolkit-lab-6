"""Regression tests for agent.py (Task 3) - System Agent with query_api tool."""

import json
import os
import subprocess
import sys


def test_agent_uses_read_file_for_framework_question():
    """Test that agent uses read_file when asked about the backend framework.

    This test verifies:
    - Agent executes successfully
    - Output is valid JSON with required fields (answer, source, tool_calls)
    - At least one tool_call uses 'read_file'
    - The answer mentions FastAPI
    """
    # Ensure environment variables are set
    required_vars = ["LLM_API_KEY", "LLM_API_BASE", "LLM_MODEL"]
    missing = [var for var in required_vars if not os.environ.get(var)]

    if missing:
        print(
            f"Skipping test: Missing environment variables: {', '.join(missing)}",
            file=sys.stderr,
        )
        print(
            "Set LLM_API_KEY, LLM_API_BASE, LLM_MODEL to run this test.",
            file=sys.stderr,
        )
        return

    # Run agent with a question about the backend framework
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "uv",
            "run",
            "agent.py",
            "What framework does the backend use?",
        ],
        capture_output=True,
        text=True,
        timeout=180,
    )

    # Check exit code
    assert result.returncode == 0, f"Agent failed: {result.stderr}"

    # Parse JSON output
    try:
        output = json.loads(result.stdout)
    except json.JSONDecodeError as e:
        raise AssertionError(f"Invalid JSON output: {e}\nStdout: {result.stdout}")

    # Validate required fields
    assert "answer" in output, "Missing 'answer' field in output"
    assert isinstance(output["answer"], str), "'answer' must be a string"
    assert len(output["answer"]) > 0, "'answer' must be non-empty"

    assert "tool_calls" in output, "Missing 'tool_calls' field in output"
    assert isinstance(output["tool_calls"], list), "'tool_calls' must be an array"

    # Verify at least one tool_call uses read_file
    tool_calls = output["tool_calls"]
    assert len(tool_calls) > 0, "Expected at least one tool call"

    read_file_used = any(call.get("tool") == "read_file" for call in tool_calls)
    assert read_file_used, "Expected 'read_file' tool to be used"

    # Verify answer mentions FastAPI
    answer_lower = output["answer"].lower()
    assert "fastapi" in answer_lower, (
        f"Expected 'FastAPI' in answer, got: {output['answer']}"
    )


def test_agent_uses_query_api_for_items_count():
    """Test that agent uses query_api when asked about items in the database.

    This test verifies:
    - Agent executes successfully
    - Output is valid JSON with required fields (answer, source, tool_calls)
    - At least one tool_call uses 'query_api'
    - The answer contains a number
    """
    # Ensure environment variables are set
    required_vars = ["LLM_API_KEY", "LLM_API_BASE", "LLM_MODEL", "LMS_API_KEY"]
    missing = [var for var in required_vars if not os.environ.get(var)]

    if missing:
        print(
            f"Skipping test: Missing environment variables: {', '.join(missing)}",
            file=sys.stderr,
        )
        print(
            "Set LLM_API_KEY, LLM_API_BASE, LLM_MODEL, and LMS_API_KEY to run this test.",
            file=sys.stderr,
        )
        return

    # Run agent with a question about items count
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "uv",
            "run",
            "agent.py",
            "How many items are in the database?",
        ],
        capture_output=True,
        text=True,
        timeout=180,
    )

    # Check exit code
    assert result.returncode == 0, f"Agent failed: {result.stderr}"

    # Parse JSON output
    try:
        output = json.loads(result.stdout)
    except json.JSONDecodeError as e:
        raise AssertionError(f"Invalid JSON output: {e}\nStdout: {result.stdout}")

    # Validate required fields
    assert "answer" in output, "Missing 'answer' field in output"
    assert isinstance(output["answer"], str), "'answer' must be a string"
    assert len(output["answer"]) > 0, "'answer' must be non-empty"

    assert "tool_calls" in output, "Missing 'tool_calls' field in output"
    assert isinstance(output["tool_calls"], list), "'tool_calls' must be an array"

    # Verify at least one tool_call uses query_api
    tool_calls = output["tool_calls"]
    assert len(tool_calls) > 0, "Expected at least one tool call"

    query_api_used = any(call.get("tool") == "query_api" for call in tool_calls)
    assert query_api_used, "Expected 'query_api' tool to be used"

    # Verify answer contains a number
    import re

    numbers = re.findall(r"\d+", output["answer"])
    assert len(numbers) > 0, f"Expected a number in answer, got: {output['answer']}"
