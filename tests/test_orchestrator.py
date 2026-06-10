"""Tests for Orchestrator — isolated per-agent runner pattern."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from agent.orchestrator import NaviGuardRunResult, _safe_json, _strip_markdown


class TestNaviGuardRunResult:
    def test_default_status(self):
        result = NaviGuardRunResult(run_id="test-001", status="completed")
        assert result.status == "completed"
        assert result.run_id == "test-001"
        assert result.monitor_report == {}
        assert result.regression_report == {}

    def test_awaiting_approval_status(self):
        result = NaviGuardRunResult(run_id="test-002", status="awaiting_approval")
        assert result.status == "awaiting_approval"

    def test_failed_status_with_error(self):
        result = NaviGuardRunResult(run_id="test-003", status="failed", error="connection timeout")
        assert result.status == "failed"
        assert "timeout" in result.error


class TestSafeJson:
    def test_dict_passthrough(self):
        d = {"status": "OK"}
        assert _safe_json(d) == d

    def test_json_string(self):
        assert _safe_json('{"a": 1}') == {"a": 1}

    def test_markdown_fenced_json(self):
        raw = "```json\n{\"status\": \"REGRESSION\"}\n```"
        result = _safe_json(raw)
        assert result.get("status") == "REGRESSION"

    def test_invalid_json_returns_empty(self):
        assert _safe_json("not json at all") == {}

    def test_strip_markdown_plain_json(self):
        assert _strip_markdown('{"x":1}') == '{"x":1}'

    def test_strip_markdown_fences(self):
        s = "```json\n{\"x\":1}\n```"
        assert _strip_markdown(s) == '{"x":1}'

    def test_strip_markdown_prose_prefix(self):
        s = "Here is the result:\n```json\n{\"x\":1}\n```"
        result = _strip_markdown(s)
        assert result == '{"x":1}'

    def test_strip_markdown_no_fence_finds_braces(self):
        s = "The answer is {\"status\": \"ok\"} based on analysis."
        result = _strip_markdown(s)
        assert result == '{"status": "ok"}'


class TestRunNaviGuard:
    @pytest.mark.asyncio
    async def test_run_returns_result(self):
        ok_report = {"status": "OK", "span_count": 0, "summary": {}, "regression_hint": False, "trace_ids": [], "span_ids": []}
        reg_report = {"status": "OK", "overall_confidence": 0.85, "affected_trace_ids": []}
        critic = {"verdict": "CORRECT", "confidence": 0.9, "hallucinated_trace_ids": [],
                  "hallucinated_span_ids": [], "issues": [], "missed_regressions": [],
                  "prompt_injection_detected": False, "critique": "ok",
                  "approved_for_dataset_creation": False, "approved_for_experiment": False}
        with (
            patch("agent.orchestrator._run_agent", new_callable=AsyncMock) as mock_run,
            patch("agent.orchestrator.setup_tracing"),
        ):
            mock_run.side_effect = [ok_report, reg_report]  # monitor + regression (no regression → returns)
            from agent.orchestrator import run_naviguard
            result = await run_naviguard(window_minutes=30)
            assert isinstance(result, NaviGuardRunResult)
            assert result.run_id is not None
            assert result.status in {"completed", "awaiting_approval", "failed"}

    @pytest.mark.asyncio
    async def test_run_handles_exception(self):
        with (
            patch("agent.orchestrator._run_agent", new_callable=AsyncMock) as mock_run,
            patch("agent.orchestrator.setup_tracing"),
        ):
            mock_run.side_effect = RuntimeError("Agent init failed")
            from agent.orchestrator import run_naviguard
            result = await run_naviguard(window_minutes=30)
            assert result.status == "failed"
            assert len(result.error) > 0

    @pytest.mark.asyncio
    async def test_regression_triggers_full_pipeline(self):
        """When regression detected, runs all 6 agents."""
        monitor_report = {"status": "OK", "span_count": 5, "summary": {"by_category": {"BLOCK": {"mean_confidence": 0.45}}}, "regression_hint": True, "trace_ids": ["t1"], "span_ids": ["s1"]}
        regression_report = {"status": "REGRESSION", "overall_confidence": 0.45, "affected_trace_ids": ["t1"], "category_drift": {}, "critical_spans": [], "regression_summary": "BLOCK dropped"}
        root_cause = {"root_cause": "novel distribution", "confidence": 0.8, "pattern": "NOVEL_DISTRIBUTION", "recommendation": "retrain", "evidence": [], "failure_examples": []}
        dataset_result = {"dataset_name": "naviguard-regression-2026-06-08", "dataset_id": "ds1", "approval_token": "tok1", "example_count": 3}
        experiment_result = {"prompt_version_id": "pv1", "prompt_identifier": "naviguard-routing-prompt", "prompt_tag": "naviguard-proposed", "dataset_id": "ds1", "change_summary": "fix BLOCK", "approval_token": "tok2"}
        critic_report = {"verdict": "CORRECT", "confidence": 0.9, "hallucinated_trace_ids": [], "hallucinated_span_ids": [], "issues": [], "missed_regressions": [], "prompt_injection_detected": False, "critique": "all good", "approved_for_dataset_creation": True, "approved_for_experiment": True}

        with (
            patch("agent.orchestrator._run_agent", new_callable=AsyncMock) as mock_run,
            patch("agent.orchestrator.setup_tracing"),
        ):
            mock_run.side_effect = [monitor_report, regression_report, root_cause, dataset_result, experiment_result, critic_report]
            from agent.orchestrator import run_naviguard
            result = await run_naviguard(window_minutes=60)
            assert mock_run.call_count == 6
            assert result.regression_report.get("status") == "REGRESSION"
