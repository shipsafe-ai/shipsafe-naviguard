"""Tests for RootCauseAnalyzer — RED first per TDD rules."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from agent.specialists.root_cause_analyzer import (
    RootCauseReport,
    build_root_cause_analyzer_agent,
    parse_root_cause_report,
)


class TestRootCauseReport:
    def test_from_dict_basic(self, sample_root_cause_report):
        report = RootCauseReport.from_dict(sample_root_cause_report)
        assert len(report.root_cause) > 0
        assert report.confidence == pytest.approx(0.89)
        assert report.pattern == "NOVEL_DISTRIBUTION"

    def test_evidence_contains_trace_ids(self, sample_root_cause_report):
        report = RootCauseReport.from_dict(sample_root_cause_report)
        assert len(report.evidence) > 0
        assert "trace_id" in report.evidence[0]
        assert "span_id" in report.evidence[0]
        assert "observation" in report.evidence[0]

    def test_recommendation_is_actionable(self, sample_root_cause_report):
        report = RootCauseReport.from_dict(sample_root_cause_report)
        assert len(report.recommendation) > 20

    def test_failure_examples_present(self, sample_root_cause_report):
        report = RootCauseReport.from_dict(sample_root_cause_report)
        assert len(report.failure_examples) > 0
        example = report.failure_examples[0]
        assert "input_summary" in example
        assert "actual_confidence" in example

    def test_pattern_enum_values(self):
        valid_patterns = {
            "NOVEL_DISTRIBUTION",
            "PROMPT_DRIFT",
            "EDGE_CASE_CLUSTER",
            "FEEDBACK_LOOP",
            "UNKNOWN",
        }
        for pattern in valid_patterns:
            report = RootCauseReport.from_dict({
                "root_cause": "test",
                "confidence": 0.5,
                "pattern": pattern,
            })
            assert report.pattern == pattern

    def test_defaults_on_minimal_dict(self):
        report = RootCauseReport.from_dict({"root_cause": "test", "confidence": 0.5})
        assert report.pattern == "UNKNOWN"
        assert report.evidence == []
        assert report.failure_examples == []


class TestParseRootCauseReport:
    def test_parse_valid_json(self, sample_root_cause_report):
        raw = json.dumps(sample_root_cause_report)
        report = parse_root_cause_report(raw)
        assert isinstance(report, RootCauseReport)
        assert report.confidence > 0

    def test_parse_invalid_json_raises(self):
        with pytest.raises((json.JSONDecodeError, KeyError)):
            parse_root_cause_report("not json")


class TestBuildRootCauseAnalyzerAgent:
    def test_agent_name(self, mock_phoenix_mcp):
        with patch("agent.specialists.root_cause_analyzer.LlmAgent") as mock_agent:
            mock_agent.return_value = MagicMock()
            build_root_cause_analyzer_agent()
            call_kwargs = mock_agent.call_args.kwargs
            assert call_kwargs["name"] == "root_cause_analyzer"
            assert call_kwargs["output_key"] == "root_cause_report"

    def test_system_prompt_has_mcp_tools(self):
        from agent.specialists.root_cause_analyzer import SYSTEM_PROMPT
        assert "get-spans" in SYSTEM_PROMPT
        assert "get-session" in SYSTEM_PROMPT
        assert "get-span-annotations" in SYSTEM_PROMPT

    def test_system_prompt_injection_defense(self):
        from agent.specialists.root_cause_analyzer import SYSTEM_PROMPT
        assert "DATA" in SYSTEM_PROMPT
        assert "opaque" in SYSTEM_PROMPT.lower() or "never" in SYSTEM_PROMPT.lower()

    def test_system_prompt_verifiable_evidence(self):
        from agent.specialists.root_cause_analyzer import SYSTEM_PROMPT
        assert "verifiable" in SYSTEM_PROMPT.lower() or "retrieved via MCP" in SYSTEM_PROMPT
