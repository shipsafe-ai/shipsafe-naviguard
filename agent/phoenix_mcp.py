"""Phoenix MCP client — wraps Phoenix MCP tools as ADK FunctionTools.

Uses the MCP protocol (stdio npx @arizeai/phoenix-mcp) with explicit session
management. ADK FunctionTool wraps each Phoenix MCP call. This fulfills full
Phoenix MCP integration with reliable session handling.

Phoenix MCP tools covered:
  list-projects, list-traces, get-trace, get-spans, get-span-annotations,
  list-sessions, get-session, list-annotation-configs,
  list-datasets, get-dataset, get-dataset-examples, add-dataset-examples,
  list-prompts, get-latest-prompt, list-prompt-versions, upsert-prompt,
  add-prompt-version-tag, list-experiments-for-dataset
"""

from __future__ import annotations

import asyncio
import json
import os
from contextlib import asynccontextmanager
from typing import Any

from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client


def _mcp_params() -> StdioServerParameters:
    # Use pre-installed package to avoid npx @latest version-mismatch at runtime
    return StdioServerParameters(
        command="node",
        args=[
            "/opt/phoenix-mcp/node_modules/@arizeai/phoenix-mcp/build/index.js",
            "--baseUrl",
            os.environ.get("PHOENIX_BASE_URL", "https://app.phoenix.arize.com/s/prateek-srivastava23"),
            "--apiKey",
            os.environ.get("PHOENIX_API_KEY", ""),
            "--project",
            os.environ.get("PHOENIX_PROJECT_NAME", "naviguard"),
        ],
    )


async def _call_phoenix_mcp(tool_name: str, arguments: dict[str, Any]) -> Any:
    """Open an MCP session, call one tool, return result. Each call is independent."""
    params = _mcp_params()
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            result = await session.call_tool(tool_name, arguments=arguments)
            if result.content:
                content = result.content[0]
                if hasattr(content, "text"):
                    try:
                        return json.loads(content.text)
                    except json.JSONDecodeError:
                        return content.text
            return {}


async def phoenix_list_projects() -> str:
    """Phoenix MCP: list-projects — list all Phoenix projects."""
    result = await _call_phoenix_mcp("list-projects", {})
    return json.dumps(result)


async def phoenix_verify_trace(trace_id: str, project_name: str = "naviguard") -> str:
    """Phoenix MCP: verify a trace_id exists by fetching spans for it (limit=1).

    Returns {"exists": true, "trace_id": "<id>"} if found, {"exists": false} otherwise.
    Used by Critic for prompt-injection defense — hallucinated IDs won't resolve.
    """
    args: dict[str, Any] = {"projectIdentifier": project_name, "traceId": trace_id, "limit": 1}
    result = await _call_phoenix_mcp("get-spans", args)
    found = bool(result) and result != {} and result != [] and "error" not in str(result).lower()[:50]
    if isinstance(result, list) and len(result) > 0:
        found = True
    elif isinstance(result, dict) and result.get("spans"):
        found = True
    return json.dumps({"exists": found, "trace_id": trace_id})


async def phoenix_list_traces(project_name: str = "naviguard", limit: int = 10) -> str:
    """Phoenix MCP: list-traces — get recent traces from naviguard project (max 10)."""
    result = await _call_phoenix_mcp("list-traces", {"projectIdentifier": project_name, "limit": min(limit, 10)})
    return json.dumps(result)


async def phoenix_get_trace(trace_id: str) -> str:
    """Phoenix MCP: get-trace — get a specific trace by ID."""
    result = await _call_phoenix_mcp("get-trace", {"trace_id": trace_id})
    # Return only key fields to limit context size
    if isinstance(result, dict):
        slim_keys = ("traceId", "trace_id", "id", "status", "startTime", "start_time")
        return json.dumps({k: result[k] for k in slim_keys if k in result})
    if isinstance(result, str) and len(result) > 500:
        return json.dumps({"found": True, "trace_id": trace_id, "summary": result[:200]})
    return json.dumps(result)


async def phoenix_get_spans(
    project_name: str = "naviguard",
    trace_id: str | None = None,
    limit: int = 20,
) -> str:
    """Phoenix MCP: get-spans — retrieve spans, optionally filtered by trace (max 20)."""
    args: dict[str, Any] = {"projectIdentifier": project_name, "limit": min(limit, 20)}
    if trace_id:
        args["traceId"] = trace_id
    result = await _call_phoenix_mcp("get-spans", args)
    # Trim span attributes to naviguard-relevant keys only
    if isinstance(result, list):
        slim = []
        for span in result:
            attrs = span.get("attributes", {}) or {}
            slim.append({
                "spanId": span.get("spanId") or span.get("context", {}).get("spanId", ""),
                "traceId": span.get("traceId") or span.get("context", {}).get("traceId", ""),
                "startTime": span.get("startTime") or span.get("start_time", ""),
                "confidence": attrs.get("naviguard.confidence_score") or attrs.get("output.value"),
                "category": attrs.get("naviguard.category") or attrs.get("category"),
                "spanKind": attrs.get("openinference.span.kind", ""),
            })
        return json.dumps(slim)
    elif isinstance(result, dict) and "spans" in result:
        spans = result["spans"]
        slim = []
        for span in spans[:20]:
            attrs = span.get("attributes", {}) or {}
            slim.append({
                "spanId": span.get("spanId", ""),
                "traceId": span.get("traceId", ""),
                "startTime": span.get("startTime", ""),
                "confidence": attrs.get("naviguard.confidence_score") or attrs.get("output.value"),
                "category": attrs.get("naviguard.category") or attrs.get("category"),
            })
        return json.dumps({"spans": slim})
    return json.dumps(result)


async def phoenix_get_span_annotations(span_id: str) -> str:
    """Phoenix MCP: get-span-annotations — retrieve annotations for a span."""
    result = await _call_phoenix_mcp("get-span-annotations", {"spanId": span_id})
    return json.dumps(result)


async def phoenix_list_sessions(project_name: str = "naviguard") -> str:
    """Phoenix MCP: list-sessions — list sessions in naviguard project."""
    result = await _call_phoenix_mcp("list-sessions", {"projectIdentifier": project_name})
    return json.dumps(result)


async def phoenix_get_session(session_id: str) -> str:
    """Phoenix MCP: get-session — get a specific session with full conversation."""
    result = await _call_phoenix_mcp("get-session", {"sessionId": session_id})
    return json.dumps(result)


async def phoenix_list_annotation_configs(project_name: str = "naviguard") -> str:
    """Phoenix MCP: list-annotation-configs — get annotation dimensions configured."""
    result = await _call_phoenix_mcp("list-annotation-configs", {"projectIdentifier": project_name})
    return json.dumps(result)


async def phoenix_list_datasets() -> str:
    """Phoenix MCP: list-datasets — list all Phoenix datasets."""
    result = await _call_phoenix_mcp("list-datasets", {})
    return json.dumps(result)


async def phoenix_get_dataset(dataset_id: str) -> str:
    """Phoenix MCP: get-dataset — get a dataset by ID."""
    result = await _call_phoenix_mcp("get-dataset", {"datasetId": dataset_id})
    return json.dumps(result)


async def phoenix_get_dataset_examples(dataset_id: str) -> str:
    """Phoenix MCP: get-dataset-examples — get examples from a dataset."""
    result = await _call_phoenix_mcp("get-dataset-examples", {"datasetId": dataset_id})
    return json.dumps(result)


async def phoenix_add_dataset_examples(dataset_name: str, examples: str) -> str:
    """Phoenix MCP: add-dataset-examples — add examples to a Phoenix dataset.

    Args:
        dataset_name: Name of the dataset (will be created if not exists)
        examples: JSON string of example list, each with 'input', 'output', 'metadata'
    """
    try:
        examples_list = json.loads(examples)
    except json.JSONDecodeError:
        return json.dumps({"error": "examples must be valid JSON array"})
    # Normalize examples: rename expected_output → output (Phoenix MCP schema)
    normalized = []
    for ex in examples_list:
        norm = dict(ex)
        if "expected_output" in norm and "output" not in norm:
            norm["output"] = norm.pop("expected_output")
        normalized.append(norm)
    result = await _call_phoenix_mcp(
        "add-dataset-examples",
        {"dataset_name": dataset_name, "examples": normalized},
    )
    return json.dumps(result)


async def phoenix_get_latest_prompt(identifier: str) -> str:
    """Phoenix MCP: get-latest-prompt — get the latest version of a prompt."""
    result = await _call_phoenix_mcp("get-latest-prompt", {"identifier": identifier})
    return json.dumps(result)


async def phoenix_list_prompt_versions(identifier: str) -> str:
    """Phoenix MCP: list-prompt-versions — get version history for a prompt."""
    result = await _call_phoenix_mcp("list-prompt-versions", {"identifier": identifier})
    return json.dumps(result)


async def phoenix_upsert_prompt(
    identifier: str,
    template: str,
    description: str = "",
) -> str:
    """Phoenix MCP: upsert-prompt — create or update a versioned prompt in Phoenix.

    Returns JSON with prompt version 'id' field for use with add-prompt-version-tag.
    Args:
        identifier: Prompt name (e.g. 'naviguard-routing-prompt')
        template: The new prompt template text (plain string)
        description: Description of what changed in this version
    """
    from agent.config import get_config
    cfg = get_config()
    result = await _call_phoenix_mcp(
        "upsert-prompt",
        {
            "name": identifier,
            "template": template,
            "description": description,
            "model_provider": "GOOGLE",
            "model_name": cfg.gemini_model,
        },
    )
    # Result is a string like "Successfully created prompt ...: {...json...}"
    # Extract the JSON object to get the version ID
    if isinstance(result, str):
        brace = result.find("{")
        if brace != -1:
            try:
                parsed = json.loads(result[brace:])
                return json.dumps({"id": parsed.get("id", ""), "prompt_data": parsed, "raw": result[:100]})
            except json.JSONDecodeError:
                pass
        return json.dumps({"raw": result, "id": ""})
    return json.dumps(result)


async def phoenix_add_prompt_version_tag(
    prompt_version_id: str,
    tag: str,
) -> str:
    """Phoenix MCP: add-prompt-version-tag — tag a prompt version (e.g. 'naviguard-proposed')."""
    result = await _call_phoenix_mcp(
        "add-prompt-version-tag",
        {"prompt_version_id": prompt_version_id, "name": tag},
    )
    return json.dumps(result)


async def phoenix_list_experiments_for_dataset(dataset_id: str) -> str:
    """Phoenix MCP: list-experiments-for-dataset — get experiments linked to a dataset."""
    result = await _call_phoenix_mcp(
        "list-experiments-for-dataset",
        {"datasetId": dataset_id},
    )
    return json.dumps(result)


def get_all_phoenix_tools() -> list:
    """Return all Phoenix MCP functions as ADK FunctionTools."""
    from google.adk.tools import FunctionTool

    return [
        FunctionTool(func=phoenix_list_projects),
        FunctionTool(func=phoenix_list_traces),
        FunctionTool(func=phoenix_get_trace),
        FunctionTool(func=phoenix_get_spans),
        FunctionTool(func=phoenix_get_span_annotations),
        FunctionTool(func=phoenix_list_sessions),
        FunctionTool(func=phoenix_get_session),
        FunctionTool(func=phoenix_list_annotation_configs),
        FunctionTool(func=phoenix_list_datasets),
        FunctionTool(func=phoenix_get_dataset),
        FunctionTool(func=phoenix_get_dataset_examples),
        FunctionTool(func=phoenix_add_dataset_examples),
        FunctionTool(func=phoenix_get_latest_prompt),
        FunctionTool(func=phoenix_list_prompt_versions),
        FunctionTool(func=phoenix_upsert_prompt),
        FunctionTool(func=phoenix_add_prompt_version_tag),
        FunctionTool(func=phoenix_list_experiments_for_dataset),
    ]


def get_monitor_tools() -> list:
    """Tools for ModelMonitor: list-projects, list-traces, get-trace, get-spans, list-sessions, get-session."""
    from google.adk.tools import FunctionTool
    return [
        FunctionTool(func=phoenix_list_projects),
        FunctionTool(func=phoenix_list_traces),
        FunctionTool(func=phoenix_get_trace),
        FunctionTool(func=phoenix_get_spans),
        FunctionTool(func=phoenix_list_sessions),
        FunctionTool(func=phoenix_get_session),
    ]


def get_detector_tools() -> list:
    """Tools for RegressionDetector: get-spans, get-span-annotations, list-annotation-configs."""
    from google.adk.tools import FunctionTool
    return [
        FunctionTool(func=phoenix_get_spans),
        FunctionTool(func=phoenix_get_span_annotations),
        FunctionTool(func=phoenix_list_annotation_configs),
    ]


def get_analyzer_tools() -> list:
    """Tools for RootCauseAnalyzer: get-spans, get-session, get-span-annotations."""
    from google.adk.tools import FunctionTool
    return [
        FunctionTool(func=phoenix_get_spans),
        FunctionTool(func=phoenix_get_session),
        FunctionTool(func=phoenix_get_span_annotations),
    ]


def get_dataset_tools() -> list:
    """Tools for DatasetBuilder: list-datasets, get-dataset, get-dataset-examples, add-dataset-examples."""
    from google.adk.tools import FunctionTool
    return [
        FunctionTool(func=phoenix_list_datasets),
        FunctionTool(func=phoenix_get_dataset),
        FunctionTool(func=phoenix_get_dataset_examples),
        FunctionTool(func=phoenix_add_dataset_examples),
    ]


def get_experiment_tools() -> list:
    """Tools for ExperimentRunner: upsert-prompt, list-prompt-versions, add-prompt-version-tag, list-datasets, list-experiments-for-dataset."""
    from google.adk.tools import FunctionTool
    return [
        FunctionTool(func=phoenix_get_latest_prompt),
        FunctionTool(func=phoenix_list_prompt_versions),
        FunctionTool(func=phoenix_upsert_prompt),
        FunctionTool(func=phoenix_add_prompt_version_tag),
        FunctionTool(func=phoenix_list_datasets),
        FunctionTool(func=phoenix_list_experiments_for_dataset),
    ]


def get_critic_tools() -> list:
    """Tools for Critic: get-spans, get-trace (verify evidence exists)."""
    from google.adk.tools import FunctionTool
    return [
        FunctionTool(func=phoenix_get_spans),
        FunctionTool(func=phoenix_get_trace),
    ]
