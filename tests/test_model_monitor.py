"""Tests for ModelMonitor — RED first per TDD rules."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from agent.specialists.model_monitor import (
    MonitorReport,
    SpanSummary,
    build_model_monitor_agent,
    parse_monitor_report,
)


class TestMonitorReport:
    def test_from_dict_basic(self, sample_monitor_report):
        report = MonitorReport.from_dict(sample_monitor_report)
        assert report.project == "naviguard"
        assert report.window_minutes == 60
        assert report.span_count == 4
        assert len(report.spans) == 4

    def test_span_summary_fields(self, sample_monitor_report):
        report = MonitorReport.from_dict(sample_monitor_report)
        span = report.spans[0]
        assert isinstance(span, SpanSummary)
        assert span.span_id == "span-001"
        assert span.trace_id == "trace-abc-001"
        assert span.confidence_score == 0.92
        assert span.category == "ROUTE"

    def test_summary_statistics(self, sample_monitor_report):
        report = MonitorReport.from_dict(sample_monitor_report)
        assert report.summary["mean_confidence"] == pytest.approx(0.6875)
        assert report.summary["min_confidence"] == pytest.approx(0.44)
        assert report.summary["max_confidence"] == pytest.approx(0.92)

    def test_by_category_summary(self, sample_monitor_report):
        report = MonitorReport.from_dict(sample_monitor_report)
        assert "ROUTE" in report.summary["by_category"]
        assert "BLOCK" in report.summary["by_category"]
        assert report.summary["by_category"]["ROUTE"]["mean_confidence"] == pytest.approx(0.90)
        assert report.summary["by_category"]["BLOCK"]["mean_confidence"] == pytest.approx(0.475)


class TestParseMonitorReport:
    def test_parse_valid_json(self, sample_monitor_report):
        raw = json.dumps(sample_monitor_report)
        report = parse_monitor_report(raw)
        assert isinstance(report, MonitorReport)
        assert report.span_count == 4

    def test_parse_invalid_json_raises(self):
        with pytest.raises(json.JSONDecodeError):
            parse_monitor_report("not json")

    def test_parse_empty_spans(self):
        raw = json.dumps({
            "project": "naviguard",
            "window_minutes": 30,
            "span_count": 0,
            "spans": [],
            "summary": {},
        })
        report = parse_monitor_report(raw)
        assert report.span_count == 0
        assert report.spans == []


class TestBuildModelMonitorAgent:
    def test_agent_has_correct_name(self, mock_phoenix_mcp):
        with patch("agent.specialists.model_monitor.LlmAgent") as mock_agent:
            mock_agent.return_value = MagicMock(name="model_monitor")
            agent = build_model_monitor_agent()
            call_kwargs = mock_agent.call_args.kwargs
            assert call_kwargs["name"] == "model_monitor"
            assert call_kwargs["output_key"] == "monitor_report"

    def test_agent_uses_gemini_model(self, mock_phoenix_mcp):
        with patch("agent.specialists.model_monitor.LlmAgent") as mock_agent:
            mock_agent.return_value = MagicMock()
            build_model_monitor_agent()
            call_kwargs = mock_agent.call_args.kwargs
            assert "gemini" in call_kwargs["model"]

    def test_agent_has_phoenix_mcp_tools(self, mock_phoenix_mcp):
        with patch("agent.specialists.model_monitor.LlmAgent") as mock_agent:
            mock_agent.return_value = MagicMock()
            build_model_monitor_agent()
            call_kwargs = mock_agent.call_args.kwargs
            assert len(call_kwargs["tools"]) > 0

    def test_system_prompt_mentions_list_traces(self):
        from agent.specialists.model_monitor import SYSTEM_PROMPT
        assert "list-traces" in SYSTEM_PROMPT
        assert "get-spans" in SYSTEM_PROMPT
        assert "confidence" in SYSTEM_PROMPT.lower()

    def test_system_prompt_has_injection_defense(self):
        from agent.specialists.model_monitor import SYSTEM_PROMPT
        assert "DATA" in SYSTEM_PROMPT
        assert "never execute" in SYSTEM_PROMPT.lower() or "opaque" in SYSTEM_PROMPT.lower()
