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

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

from agent.config import get_config
from agent.instrumentation import setup_tracing
from agent.orchestrator import run_naviguard, NaviGuardRunResult
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
    success = approval_store.grant_approval(token)
    if not success:
        raise HTTPException(status_code=404, detail=f"No pending approval for token: {token}")
    return ApproveResponse(
        token=token,
        approved=True,
        message=f"Approval granted. Notes: {request.notes or 'none'}",
    )


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
    """Query Phoenix via MCP for regression-annotated spans."""
    result = await _query_phoenix_mcp("get-spans", {"project": "naviguard", "limit": 100})
    spans = result.get("spans", [])
    regressions = []
    for span in spans:
        conf = _extract_confidence(span)
        if conf is not None and conf < 0.70:
            regressions.append(
                RegressionItem(
                    trace_id=span.get("traceId", span.get("trace_id", "")),
                    span_id=span.get("spanId", span.get("span_id", "")),
                    timestamp=span.get("startTime", span.get("timestamp", "")),
                    confidence_score=conf,
                    category=_extract_category(span),
                    annotation=span.get("annotation"),
                )
            )
    return regressions


@app.get("/datasets", response_model=list[DatasetItem])
async def get_datasets() -> list[DatasetItem]:
    """Query Phoenix via MCP for naviguard datasets."""
    result = await _query_phoenix_mcp("list-datasets", {})
    datasets = result.get("datasets", [])
    return [
        DatasetItem(
            dataset_id=d.get("id", d.get("dataset_id", "")),
            dataset_name=d.get("name", d.get("dataset_name", "")),
            example_count=d.get("exampleCount", d.get("example_count", 0)),
            created_at=d.get("createdAt", d.get("created_at", "")),
        )
        for d in datasets
        if "naviguard" in d.get("name", d.get("dataset_name", "")).lower()
    ]


@app.get("/experiments", response_model=list[ExperimentItem])
async def get_experiments() -> list[ExperimentItem]:
    """Query Phoenix via MCP for naviguard experiments."""
    result = await _query_phoenix_mcp("list-prompt-versions", {"identifier": "naviguard-routing-prompt"})
    versions = result.get("versions", [])
    return [
        ExperimentItem(
            prompt_version_id=v.get("id", ""),
            prompt_identifier=v.get("identifier", "naviguard-routing-prompt"),
            prompt_tag=",".join(v.get("tags", [])),
            dataset_id=v.get("datasetId", ""),
            change_summary=v.get("description", v.get("change_summary", "")),
            created_at=v.get("createdAt", ""),
        )
        for v in versions
    ]


@app.get("/metrics", response_model=MetricsResponse)
async def get_metrics() -> MetricsResponse:
    """Confidence timeline from Phoenix spans via MCP."""
    cfg = get_config()
    result = await _query_phoenix_mcp("get-spans", {"project": "naviguard", "limit": 200})
    spans = result.get("spans", [])

    timeline = []
    by_category: dict[str, list[float]] = {}
    regression_windows = []

    for span in spans:
        conf = _extract_confidence(span)
        if conf is None:
            continue
        ts = span.get("startTime", span.get("timestamp", ""))
        cat = _extract_category(span)
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
    """Run a Phoenix MCP tool call via npx subprocess and return parsed result."""
    cfg = get_config()
    try:
        cmd = [
            "npx", "-y", "@arizeai/phoenix-mcp@latest",
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
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=30.0)
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
