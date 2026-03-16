"""Regression tests for agent.py (Task 2) - Documentation Agent with tools."""

import json
import os
import subprocess
import sys


def test_agent_uses_read_file_for_merge_conflict():
    """Test that agent uses read_file tool when asked about merge conflicts.

    This test verifies:
    - Agent executes successfully
    - Output is valid JSON with required fields (answer, source, tool_calls)
    - At least one tool_call uses 'read_file'
    - The source field references wiki/git-workflow.md
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

    # Run agent with a question about merge conflicts
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "uv",
            "run",
            "agent.py",
            "How do you resolve a merge conflict?",
        ],
        capture_output=True,
        text=True,
        timeout=180,  # Give extra time for multiple LLM calls
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

    assert "source" in output, "Missing 'source' field in output"
    assert isinstance(output["source"], str), "'source' must be a string"

    assert "tool_calls" in output, "Missing 'tool_calls' field in output"
    assert isinstance(output["tool_calls"], list), "'tool_calls' must be an array"

    # Verify at least one tool_call uses read_file
    tool_calls = output["tool_calls"]
    assert len(tool_calls) > 0, "Expected at least one tool call"

    read_file_used = any(call.get("tool") == "read_file" for call in tool_calls)
    assert read_file_used, "Expected 'read_file' tool to be used"

    # Verify source references git-workflow.md
    source = output["source"]
    assert "git-workflow.md" in source, (
        f"Expected 'git-workflow.md' in source, got: {source}"
    )


def test_agent_uses_list_files_for_wiki_exploration():
    """Test that agent uses list_files tool when asked about wiki contents.

    This test verifies:
    - Agent executes successfully
    - Output is valid JSON with required fields (answer, source, tool_calls)
    - At least one tool_call uses 'list_files'
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

    # Run agent with a question about wiki files
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "uv",
            "run",
            "agent.py",
            "What files are in the wiki?",
        ],
        capture_output=True,
        text=True,
        timeout=180,  # Give extra time for multiple LLM calls
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

    assert "source" in output, "Missing 'source' field in output"
    assert isinstance(output["source"], str), "'source' must be a string"

    assert "tool_calls" in output, "Missing 'tool_calls' field in output"
    assert isinstance(output["tool_calls"], list), "'tool_calls' must be an array"

    # Verify at least one tool_call uses list_files
    tool_calls = output["tool_calls"]
    assert len(tool_calls) > 0, "Expected at least one tool call"

    list_files_used = any(call.get("tool") == "list_files" for call in tool_calls)
    assert list_files_used, "Expected 'list_files' tool to be used"
