"""Pydantic models for NaviGuard API."""

from __future__ import annotations

from typing import Any, Optional
from pydantic import BaseModel


class RunRequest(BaseModel):
    window_minutes: int = 60
    scenario: Optional[str] = None


class RunResponse(BaseModel):
    run_id: str
    status: str
    regression_status: str = "UNKNOWN"
    root_cause: str = ""
    critic_verdict: str = ""
    pending_approvals: list[dict[str, Any]] = []
    monitor_report: dict[str, Any] = {}
    regression_report: dict[str, Any] = {}
    root_cause_report: dict[str, Any] = {}
    dataset_result: dict[str, Any] = {}
    experiment_result: dict[str, Any] = {}
    critic_report: dict[str, Any] = {}
    error: str = ""


class ApproveRequest(BaseModel):
    notes: Optional[str] = None


class ApproveResponse(BaseModel):
    token: str
    approved: bool
    message: str


class PendingApprovalItem(BaseModel):
    token: str
    artifact_type: str
    details: dict[str, Any]


class HealthResponse(BaseModel):
    status: str
    phoenix_project: str
    phoenix_base_url: str
    gemini_model: str


class MetricsResponse(BaseModel):
    project: str
    confidence_timeline: list[dict[str, Any]]
    by_category: dict[str, Any]
    regression_windows: list[dict[str, Any]]


class RegressionItem(BaseModel):
    trace_id: str
    span_id: str
    timestamp: str
    confidence_score: float
    category: str
    annotation: Optional[str] = None


class DatasetItem(BaseModel):
    dataset_id: str
    dataset_name: str
    example_count: int
    created_at: str = ""


class ExperimentItem(BaseModel):
    prompt_version_id: str
    prompt_identifier: str
    prompt_tag: str
    dataset_id: str
    change_summary: str
    created_at: str = ""
