"""Pytest fixtures and mocks for NaviGuard tests."""

from __future__ import annotations

import json
import os
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


os.environ.setdefault("GEMINI_MODEL", "gemini-2.5-flash")
os.environ.setdefault("PHOENIX_API_KEY", "px_test_key")
os.environ.setdefault("PHOENIX_COLLECTOR_ENDPOINT", "https://app.phoenix.arize.com/s/test")
os.environ.setdefault("PHOENIX_BASE_URL", "https://app.phoenix.arize.com/s/test")
os.environ.setdefault("PHOENIX_PROJECT_NAME", "naviguard-test")
os.environ.setdefault("GOOGLE_CLOUD_PROJECT", "test-project")
os.environ.setdefault("GOOGLE_GENAI_USE_VERTEXAI", "1")


SAMPLE_SPANS = [
    {
        "span_id": "span-001",
        "trace_id": "trace-abc-001",
        "timestamp": "2026-06-08T09:00:00Z",
        "confidence_score": 0.92,
        "category": "ROUTE",
        "input_summary": "Vessel routing request for Strait of Hormuz",
        "latency_ms": 234,
    },
    {
        "span_id": "span-002",
        "trace_id": "trace-abc-002",
        "timestamp": "2026-06-08T15:00:00Z",
        "confidence_score": 0.44,
        "category": "BLOCK",
        "input_summary": "Crisis avoidance routing request — Hormuz blocked",
        "latency_ms": 412,
    },
    {
        "span_id": "span-003",
        "trace_id": "trace-abc-003",
        "timestamp": "2026-06-08T15:30:00Z",
        "confidence_score": 0.51,
        "category": "BLOCK",
        "input_summary": "Alternative route request during Hormuz crisis",
        "latency_ms": 389,
    },
    {
        "span_id": "span-004",
        "trace_id": "trace-abc-004",
        "timestamp": "2026-06-08T16:00:00Z",
        "confidence_score": 0.88,
        "category": "ROUTE",
        "input_summary": "Standard Atlantic routing request",
        "latency_ms": 198,
    },
]

SAMPLE_MONITOR_REPORT = {
    "project": "naviguard",
    "window_minutes": 60,
    "span_count": 4,
    "spans": SAMPLE_SPANS,
    "summary": {
        "mean_confidence": 0.6875,
        "min_confidence": 0.44,
        "max_confidence": 0.92,
        "by_category": {
            "ROUTE": {"count": 2, "mean_confidence": 0.90},
            "BLOCK": {"count": 2, "mean_confidence": 0.475},
        },
    },
}

SAMPLE_REGRESSION_REPORT = {
    "status": "REGRESSION",
    "overall_confidence": 0.6875,
    "threshold": 0.70,
    "affected_categories": ["BLOCK"],
    "affected_trace_ids": ["trace-abc-002", "trace-abc-003"],
    "category_drift": {
        "BLOCK": {
            "current_mean": 0.475,
            "baseline_mean": 0.87,
            "delta": -0.395,
            "span_count": 2,
        }
    },
    "critical_spans": [
        {
            "span_id": "span-002",
            "trace_id": "trace-abc-002",
            "confidence_score": 0.44,
            "category": "BLOCK",
        }
    ],
    "regression_summary": "BLOCK category confidence dropped 41% at 15:00 during Hormuz crisis",
}

SAMPLE_ROOT_CAUSE_REPORT = {
    "root_cause": "Crisis avoidance pattern missing from training data — model never saw Hormuz blockage scenarios",
    "confidence": 0.89,
    "evidence": [
        {
            "trace_id": "trace-abc-002",
            "span_id": "span-002",
            "observation": "Confidence 0.44 on BLOCK decision — model hesitates on crisis routing",
        }
    ],
    "pattern": "NOVEL_DISTRIBUTION",
    "recommendation": "Add 50+ Hormuz crisis routing examples to training dataset with BLOCK decisions",
    "failure_examples": [
        {
            "input_summary": "Crisis avoidance routing request — Hormuz blocked",
            "expected_behavior": "BLOCK with confidence >0.85",
            "actual_confidence": 0.44,
        }
    ],
}

SAMPLE_DATASET_RESULT = {
    "dataset_id": "dataset-naviguard-001",
    "dataset_name": "naviguard-regression-2026-06-08-NOVEL_DISTRIBUTION",
    "example_count": 2,
    "approval_token": "approval-token-abc",
    "examples_preview": [
        {"input_summary": "Crisis avoidance routing request", "category": "BLOCK"}
    ],
}

SAMPLE_EXPERIMENT_RESULT = {
    "prompt_version_id": "prompt-v2-naviguard-001",
    "prompt_identifier": "naviguard-routing-prompt",
    "prompt_tag": "naviguard-proposed",
    "dataset_id": "dataset-naviguard-001",
    "change_summary": "Added 15 crisis avoidance examples; strengthened BLOCK decision boundary",
    "approval_token": "approval-token-xyz",
    "expected_improvement": "BLOCK confidence expected to improve from 0.475 to 0.82",
    "new_prompt_preview": "You are a maritime routing model. When encountering Hormuz crisis...",
}

SAMPLE_CRITIC_REPORT = {
    "verdict": "CORRECT",
    "confidence": 0.92,
    "hallucinated_trace_ids": [],
    "hallucinated_span_ids": [],
    "issues": [],
    "missed_regressions": [],
    "prompt_injection_detected": False,
    "critique": "NaviGuard correctly identified the BLOCK category regression with valid trace evidence.",
    "approved_for_dataset_creation": True,
    "approved_for_experiment": True,
}


@pytest.fixture
def sample_spans():
    return SAMPLE_SPANS


@pytest.fixture
def sample_monitor_report():
    return SAMPLE_MONITOR_REPORT


@pytest.fixture
def sample_regression_report():
    return SAMPLE_REGRESSION_REPORT


@pytest.fixture
def sample_root_cause_report():
    return SAMPLE_ROOT_CAUSE_REPORT


@pytest.fixture
def sample_dataset_result():
    return SAMPLE_DATASET_RESULT


@pytest.fixture
def sample_experiment_result():
    return SAMPLE_EXPERIMENT_RESULT


@pytest.fixture
def sample_critic_report():
    return SAMPLE_CRITIC_REPORT


@pytest.fixture
def mock_adk_agent():
    """Mock ADK LlmAgent to avoid real LLM calls in tests."""
    with patch("google.adk.agents.LlmAgent") as mock:
        yield mock


@pytest.fixture
def mock_phoenix_mcp():
    """Mock Phoenix MCP toolset."""
    with patch("agent.specialists.model_monitor.build_phoenix_mcp_toolset") as mock:
        mock.return_value = MagicMock()
        yield mock
