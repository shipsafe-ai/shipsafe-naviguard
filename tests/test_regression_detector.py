"""Tests for RegressionDetector — RED first per TDD rules."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from agent.specialists.regression_detector import (
    CategoryDrift,
    RegressionReport,
    build_regression_detector_agent,
    parse_regression_report,
)


class TestRegressionReport:
    def test_from_dict_regression_status(self, sample_regression_report):
        report = RegressionReport.from_dict(sample_regression_report)
        assert report.status == "REGRESSION"
        assert report.is_regression is True

    def test_from_dict_ok_status(self):
        data = {
            "status": "OK",
            "overall_confidence": 0.88,
            "threshold": 0.70,
        }
        report = RegressionReport.from_dict(data)
        assert report.status == "OK"
        assert report.is_regression is False

    def test_affected_categories(self, sample_regression_report):
        report = RegressionReport.from_dict(sample_regression_report)
        assert "BLOCK" in report.affected_categories

    def test_affected_trace_ids_populated(self, sample_regression_report):
        report = RegressionReport.from_dict(sample_regression_report)
        assert "trace-abc-002" in report.affected_trace_ids
        assert "trace-abc-003" in report.affected_trace_ids

    def test_category_drift_parsed(self, sample_regression_report):
        report = RegressionReport.from_dict(sample_regression_report)
        assert "BLOCK" in report.category_drift
        drift = report.category_drift["BLOCK"]
        assert isinstance(drift, CategoryDrift)
        assert drift.current_mean == pytest.approx(0.475)
        assert drift.baseline_mean == pytest.approx(0.87)
        assert drift.delta == pytest.approx(-0.395)

    def test_critical_spans_present(self, sample_regression_report):
        report = RegressionReport.from_dict(sample_regression_report)
        assert len(report.critical_spans) == 1
        assert report.critical_spans[0]["confidence_score"] == pytest.approx(0.44)

    def test_regression_summary_text(self, sample_regression_report):
        report = RegressionReport.from_dict(sample_regression_report)
        assert len(report.regression_summary) > 0
        assert "BLOCK" in report.regression_summary


class TestParseRegressionReport:
    def test_parse_valid_json(self, sample_regression_report):
        raw = json.dumps(sample_regression_report)
        report = parse_regression_report(raw)
        assert isinstance(report, RegressionReport)
        assert report.is_regression

    def test_parse_invalid_json_raises(self):
        with pytest.raises((json.JSONDecodeError, KeyError)):
            parse_regression_report("not json")


class TestBuildRegressionDetectorAgent:
    def test_agent_name(self, mock_phoenix_mcp):
        with patch("agent.specialists.regression_detector.LlmAgent") as mock_agent:
            mock_agent.return_value = MagicMock()
            build_regression_detector_agent()
            call_kwargs = mock_agent.call_args.kwargs
            assert call_kwargs["name"] == "regression_detector"
            assert call_kwargs["output_key"] == "regression_report"

    def test_system_prompt_references_mcp_tools(self):
        from agent.specialists.regression_detector import SYSTEM_PROMPT
        assert "threshold" in SYSTEM_PROMPT.lower() or "0.70" in SYSTEM_PROMPT or "annotation" in SYSTEM_PROMPT.lower()

    def test_system_prompt_trace_id_safety(self):
        from agent.specialists.regression_detector import SYSTEM_PROMPT
        assert "affected_trace_ids" in SYSTEM_PROMPT
        assert "Never fabricate" in SYSTEM_PROMPT or "ONLY" in SYSTEM_PROMPT

    def test_threshold_mentioned_in_prompt(self):
        from agent.specialists.regression_detector import SYSTEM_PROMPT
        assert "0.70" in SYSTEM_PROMPT or "threshold" in SYSTEM_PROMPT.lower()

    def test_detects_category_drift_logic(self, sample_regression_report):
        """BLOCK category drops 41% while ROUTE stays stable — must be detected."""
        report = RegressionReport.from_dict(sample_regression_report)
        assert report.is_regression
        assert "BLOCK" in report.affected_categories
        assert "ROUTE" not in report.affected_categories
