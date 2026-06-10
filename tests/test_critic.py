"""Tests for Critic — RED first per TDD rules."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from agent.critic import (
    CriticReport,
    build_critic_agent,
    parse_critic_report,
)


class TestCriticReport:
    def test_correct_verdict(self, sample_critic_report):
        report = CriticReport.from_dict(sample_critic_report)
        assert report.verdict == "CORRECT"
        assert report.is_correct is True

    def test_incorrect_verdict(self):
        data = {
            "verdict": "INCORRECT",
            "confidence": 0.95,
            "hallucinated_trace_ids": ["fake-trace-999"],
            "issues": [{"severity": "HIGH", "description": "Hallucinated trace ID"}],
            "prompt_injection_detected": True,
            "approved_for_dataset_creation": False,
            "approved_for_experiment": False,
        }
        report = CriticReport.from_dict(data)
        assert report.is_correct is False
        assert report.prompt_injection_detected is True
        assert not report.approved_for_dataset_creation
        assert not report.approved_for_experiment

    def test_hallucinated_trace_ids_field(self, sample_critic_report):
        report = CriticReport.from_dict(sample_critic_report)
        assert isinstance(report.hallucinated_trace_ids, list)
        assert len(report.hallucinated_trace_ids) == 0

    def test_approval_gates_true_on_correct(self, sample_critic_report):
        report = CriticReport.from_dict(sample_critic_report)
        assert report.approved_for_dataset_creation is True
        assert report.approved_for_experiment is True

    def test_approval_gates_false_when_injection(self):
        data = {
            "verdict": "INCORRECT",
            "confidence": 0.9,
            "prompt_injection_detected": True,
            "approved_for_dataset_creation": False,
            "approved_for_experiment": False,
        }
        report = CriticReport.from_dict(data)
        assert report.approved_for_dataset_creation is False

    def test_missed_regressions_field(self):
        data = {
            "verdict": "INCORRECT",
            "confidence": 0.7,
            "missed_regressions": [
                {"category": "HOLD", "evidence": "HOLD category also dropped but missed"}
            ],
            "approved_for_dataset_creation": False,
            "approved_for_experiment": False,
        }
        report = CriticReport.from_dict(data)
        assert len(report.missed_regressions) == 1


class TestParseCriticReport:
    def test_parse_valid_json(self, sample_critic_report):
        raw = json.dumps(sample_critic_report)
        report = parse_critic_report(raw)
        assert isinstance(report, CriticReport)

    def test_parse_invalid_raises(self):
        with pytest.raises((json.JSONDecodeError, KeyError)):
            parse_critic_report("not json")


class TestBuildCriticAgent:
    def test_agent_name(self, mock_phoenix_mcp):
        with patch("agent.critic.LlmAgent") as mock_agent:
            mock_agent.return_value = MagicMock()
            build_critic_agent()
            call_kwargs = mock_agent.call_args.kwargs
            assert call_kwargs["name"] == "critic"
            assert call_kwargs["output_key"] == "critic_report"

    def test_system_prompt_uses_evaluator_template(self):
        from agent.critic import SYSTEM_PROMPT, EVALUATOR_PROMPT
        assert "CORRECT" in EVALUATOR_PROMPT
        assert "INCORRECT" in EVALUATOR_PROMPT
        assert "BEGIN DATA" in EVALUATOR_PROMPT
        assert "END DATA" in EVALUATOR_PROMPT

    def test_system_prompt_verifies_trace_ids(self):
        from agent.critic import SYSTEM_PROMPT
        assert "phoenix_verify_trace" in SYSTEM_PROMPT or "get-trace" in SYSTEM_PROMPT or "verify" in SYSTEM_PROMPT
        assert "hallucinated" in SYSTEM_PROMPT.lower() or "hallucinate" in SYSTEM_PROMPT.lower()

    def test_evaluator_prompt_correct_rubric(self):
        from agent.critic import EVALUATOR_PROMPT
        assert "category-specific drift" in EVALUATOR_PROMPT
        assert "confidence deltas" in EVALUATOR_PROMPT

    def test_evaluator_prompt_incorrect_rubric(self):
        from agent.critic import EVALUATOR_PROMPT
        assert "Hallucinated evidence" in EVALUATOR_PROMPT
        assert "trace IDs" in EVALUATOR_PROMPT

    def test_prompt_references_mcp_verification(self):
        from agent.critic import SYSTEM_PROMPT
        # Critic uses phoenix_verify_trace to confirm trace IDs exist in Phoenix
        assert "phoenix_verify_trace" in SYSTEM_PROMPT or "verify_trace" in SYSTEM_PROMPT
