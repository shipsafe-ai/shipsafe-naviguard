"""NaviGuard FastAPI — all Phoenix data queries go via Phoenix MCP toolset."""

from __future__ import annotations

import asyncio
import json
import os
import subprocess
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

from agent.config import get_config
from agent.instrumentation import setup_tracing
from agent.orchestrator import run_naviguard, run_naviguard_stream, NaviGuardRunResult
from api.approval_store import approval_store
from api.models import (
    ApproveRequest,
    ApproveResponse,
    DatasetItem,
    ExperimentItem,
    HealthResponse,
    MetricsResponse,
    PendingApprovalItem,
    RegressionItem,
    RunRequest,
    RunResponse,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_tracing()
    yield


app = FastAPI(
    title="NaviGuard",
    description="AI quality monitoring with self-improvement loops — Arize Phoenix track",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

_active_runs: dict[str, NaviGuardRunResult] = {}


@app.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    cfg = get_config()
    return HealthResponse(
        status="ok",
        phoenix_project=cfg.phoenix_project_name,
        phoenix_base_url=cfg.phoenix_base_url,
        gemini_model=cfg.gemini_model,
    )


@app.post("/run/stream")
async def run_stream(request: RunRequest) -> StreamingResponse:
    """SSE stream — steps fire as they complete. Bypasses Cloud Run 300s request timeout."""
    async def generate():
        async for event in run_naviguard_stream(
            window_minutes=request.window_minutes,
            scenario=request.scenario,
        ):
            yield f"data: {json.dumps(event)}\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


@app.post("/run", response_model=RunResponse)
async def run(request: RunRequest) -> RunResponse:
    result = await run_naviguard(
        window_minutes=request.window_minutes,
        scenario=request.scenario,
    )
    _active_runs[result.run_id] = result

    return RunResponse(
        run_id=result.run_id,
        status=result.status,
        regression_status=result.regression_report.get("status", "UNKNOWN"),
        root_cause=result.root_cause_report.get("root_cause", ""),
        critic_verdict=result.critic_report.get("verdict", ""),
        pending_approvals=result.pending_approvals,
        monitor_report=result.monitor_report,
        regression_report=result.regression_report,
        root_cause_report=result.root_cause_report,
        dataset_result=result.dataset_result,
        experiment_result=result.experiment_result,
        critic_report=result.critic_report,
        error=result.error,
    )


@app.post("/approve/{token}", response_model=ApproveResponse)
async def approve(token: str, request: ApproveRequest) -> ApproveResponse:
    from agent.pending_actions import consume as _consume_action
    action = _consume_action(token)
    if not action:
        raise HTTPException(status_code=404, detail=f"No pending approval for token: {token}")

    action_type = action["type"]
    spec = action["spec"]
    result_detail: dict = {}

    try:
        if action_type == "dataset":
            result_detail = await _execute_dataset_creation(spec)
        elif action_type == "experiment":
            result_detail = await _execute_experiment_creation(spec)
        else:
            result_detail = {"warning": f"Unknown action type: {action_type}"}
    except Exception as exc:
        result_detail = {"error": str(exc)}

    return ApproveResponse(
        token=token,
        approved=True,
        message=f"Approved and executed: {action_type}. Notes: {request.notes or 'none'}",
        result=result_detail,
    )


async def _execute_dataset_creation(spec: dict) -> dict:
    """Call Phoenix MCP add-dataset-examples with the approved spec."""
    from agent.phoenix_mcp import phoenix_add_dataset_examples
    dataset_name = spec.get("dataset_name", "naviguard-regression")
    examples = spec.get("examples", [])
    if not examples:
        return {"warning": "No examples in spec — nothing added to Phoenix"}
    result_json = await phoenix_add_dataset_examples(
        dataset_name=dataset_name,
        examples=json.dumps(examples),
    )
    cfg = get_config()
    phoenix_url = f"{cfg.phoenix_base_url}/datasets"
    return {
        "dataset_name": dataset_name,
        "example_count": len(examples),
        "phoenix_result": result_json,
        "phoenix_url": phoenix_url,
    }


async def _execute_experiment_creation(spec: dict) -> dict:
    """Call Phoenix MCP upsert-prompt + add-prompt-version-tag with the approved spec."""
    from agent.phoenix_mcp import phoenix_upsert_prompt, phoenix_add_prompt_version_tag
    identifier = spec.get("prompt_identifier", "naviguard-routing-prompt")
    template = spec.get("prompt_template", "")
    change_summary = spec.get("change_summary", "NaviGuard proposed improvement")
    tag = spec.get("prompt_tag", "naviguard-proposed")

    if not template:
        return {"warning": "No prompt template in spec — nothing created in Phoenix"}

    upsert_result_json = await phoenix_upsert_prompt(
        identifier=identifier,
        template=template,
        description=change_summary,
    )
    upsert_result = json.loads(upsert_result_json) if isinstance(upsert_result_json, str) else upsert_result_json
    prompt_version_id = upsert_result.get("id", "")

    tag_result = {}
    if prompt_version_id:
        tag_result_json = await phoenix_add_prompt_version_tag(
            prompt_version_id=prompt_version_id,
            tag=tag,
        )
        tag_result = json.loads(tag_result_json) if isinstance(tag_result_json, str) else tag_result_json

    cfg = get_config()
    phoenix_url = f"{cfg.phoenix_base_url}/prompts/{identifier}"
    return {
        "prompt_identifier": identifier,
        "prompt_version_id": prompt_version_id,
        "prompt_tag": tag,
        "change_summary": change_summary,
        "phoenix_url": phoenix_url,
        "upsert_result": upsert_result,
        "tag_result": tag_result,
    }


@app.get("/approvals/pending", response_model=list[PendingApprovalItem])
async def list_pending_approvals() -> list[PendingApprovalItem]:
    return [
        PendingApprovalItem(
            token=a.token,
            artifact_type=a.artifact_type,
            details=a.details,
        )
        for a in approval_store.list_pending()
    ]


@app.get("/regressions", response_model=list[RegressionItem])
async def get_regressions() -> list[RegressionItem]:
    """Below-threshold spans via the working Phoenix MCP stdio client."""
    from agent.phoenix_mcp import phoenix_get_spans

    spans = _parse_spans(await phoenix_get_spans(project_name="naviguard", limit=20))
    regressions = []
    for span in spans:
        conf = _coerce_conf(span.get("confidence"))
        if conf is not None and conf < 0.70:
            regressions.append(
                RegressionItem(
                    trace_id=span.get("traceId", ""),
                    span_id=span.get("spanId", ""),
                    timestamp=span.get("startTime", ""),
                    confidence_score=conf,
                    category=span.get("category") or "UNKNOWN",
                    annotation=None,
                )
            )
    return regressions


@app.get("/datasets", response_model=list[DatasetItem])
async def get_datasets() -> list[DatasetItem]:
    """naviguard datasets via the working Phoenix MCP stdio client."""
    from agent.phoenix_mcp import phoenix_list_datasets

    datasets = _parse_list(await phoenix_list_datasets(), "datasets")
    out = []
    for d in datasets:
        if not isinstance(d, dict):
            continue
        name = (d.get("name") or d.get("dataset_name") or "")
        if "naviguard" not in name.lower():
            continue
        out.append(
            DatasetItem(
                dataset_id=d.get("id", d.get("dataset_id", "")),
                dataset_name=name,
                example_count=d.get("exampleCount", d.get("example_count", 0)) or 0,
                created_at=d.get("createdAt", d.get("created_at", "")) or "",
            )
        )
    return out


@app.get("/experiments", response_model=list[ExperimentItem])
async def get_experiments() -> list[ExperimentItem]:
    """naviguard prompt versions via the working Phoenix MCP stdio client."""
    from agent.phoenix_mcp import phoenix_list_prompt_versions

    versions = _parse_list(await phoenix_list_prompt_versions("naviguard-routing-prompt"), "versions")
    out = []
    for v in versions:
        if not isinstance(v, dict):
            continue
        tags = v.get("tags", [])
        out.append(
            ExperimentItem(
                prompt_version_id=v.get("id", ""),
                prompt_identifier=v.get("identifier", "naviguard-routing-prompt"),
                prompt_tag=",".join(tags) if isinstance(tags, list) else str(tags or ""),
                dataset_id=v.get("datasetId", ""),
                change_summary=v.get("description", v.get("change_summary", "")),
                created_at=v.get("createdAt", ""),
            )
        )
    return out


@app.get("/metrics", response_model=MetricsResponse)
async def get_metrics() -> MetricsResponse:
    """Confidence timeline from Phoenix spans via MCP."""
    from agent.phoenix_mcp import phoenix_get_spans

    cfg = get_config()
    spans = _parse_spans(await phoenix_get_spans(project_name="naviguard", limit=20))

    timeline = []
    by_category: dict[str, list[float]] = {}
    regression_windows = []

    for span in spans:
        conf = _coerce_conf(span.get("confidence"))
        if conf is None:
            continue
        ts = span.get("startTime", "")
        cat = span.get("category") or "UNKNOWN"
        timeline.append({"timestamp": ts, "confidence_score": conf, "category": cat})
        by_category.setdefault(cat, []).append(conf)
        if conf < cfg.confidence_regression_threshold:
            regression_windows.append({"timestamp": ts, "confidence_score": conf, "category": cat})

    category_summary = {
        cat: {"mean": sum(scores) / len(scores), "count": len(scores)}
        for cat, scores in by_category.items()
    }

    return MetricsResponse(
        project="naviguard",
        confidence_timeline=sorted(timeline, key=lambda x: x["timestamp"]),
        by_category=category_summary,
        regression_windows=regression_windows,
    )


async def _query_phoenix_mcp(tool_name: str, params: dict[str, Any]) -> dict[str, Any]:
    """Run a Phoenix MCP tool via pre-installed node binary (avoids npx version-mismatch)."""
    cfg = get_config()
    try:
        cmd = [
            "node",
            "/opt/phoenix-mcp/node_modules/@arizeai/phoenix-mcp/build/index.js",
            "--baseUrl", cfg.phoenix_base_url,
            "--apiKey", cfg.phoenix_api_key,
            "--tool", tool_name,
            "--params", json.dumps(params),
        ]
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, _stderr = await asyncio.wait_for(proc.communicate(), timeout=30.0)
        if proc.returncode == 0:
            return json.loads(stdout.decode())
        return {}
    except Exception:
        return {}


def _extract_confidence(span: dict[str, Any]) -> float | None:
    for key in ["output.value", "outputValue", "attributes.output.value"]:
        val = span.get(key)
        if val is not None:
            try:
                f = float(val)
                if 0.0 <= f <= 1.0:
                    return f
            except (ValueError, TypeError):
                pass
    attrs = span.get("attributes", {})
    if isinstance(attrs, dict):
        for key in ["output.value", "confidence_score", "confidence"]:
            val = attrs.get(key)
            if val is not None:
                try:
                    f = float(val)
                    if 0.0 <= f <= 1.0:
                        return f
                except (ValueError, TypeError):
                    pass
    return None


def _extract_category(span: dict[str, Any]) -> str:
    for key in ["category", "attributes.category", "metadata.category"]:
        val = span.get(key)
        if val:
            return str(val)
    attrs = span.get("attributes", {})
    if isinstance(attrs, dict):
        return str(attrs.get("category", "UNKNOWN"))
    return "UNKNOWN"


def _parse_spans(raw: str) -> list[dict[str, Any]]:
    """Parse phoenix_get_spans JSON (a list, or {'spans': [...]}) into a span list."""
    try:
        data = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return []
    if isinstance(data, list):
        return [s for s in data if isinstance(s, dict)]
    if isinstance(data, dict):
        return [s for s in data.get("spans", []) if isinstance(s, dict)]
    return []


def _parse_list(raw: str, key: str) -> list[Any]:
    """Parse an MCP list result (a bare list, or {key: [...]})."""
    try:
        data = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return []
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        return data.get(key, []) or []
    return []


def _coerce_conf(val: Any) -> float | None:
    """Coerce a confidence value (float or str) to a 0..1 float, else None."""
    if val is None or val == "":
        return None
    try:
        f = float(val)
        return f if 0.0 <= f <= 1.0 else None
    except (ValueError, TypeError):
        return None
