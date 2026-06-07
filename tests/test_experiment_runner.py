"""Tests for ExperimentRunner — RED first per TDD rules."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from agent.specialists.experiment_runner import (
    ApprovalRequired,
    ExperimentResult,
    build_experiment_runner_agent,
    check_approval_required,
    generate_approval_token,
    parse_experiment_result,
)


class TestApprovalRequired:
    def test_has_fields(self):
        exc = ApprovalRequired(
            token="tok-exp-001",
            prompt_identifier="naviguard-routing-prompt",
            change_summary="Added crisis examples",
        )
        assert exc.token == "tok-exp-001"
        assert exc.prompt_identifier == "naviguard-routing-prompt"
        assert "crisis" in exc.change_summary

    def test_is_exception(self):
        exc = ApprovalRequired(token="x", prompt_identifier="y", change_summary="z")
        assert isinstance(exc, Exception)


class TestCheckApprovalRequired:
    def test_detects_marker(self):
        raw = 'APPROVAL_REQUIRED:{"token": "tok-1", "prompt_identifier": "naviguard-routing-prompt", "change_summary": "Added examples"}'
        required, data = check_approval_required(raw)
        assert required is True
        assert data["token"] == "tok-1"
        assert data["prompt_identifier"] == "naviguard-routing-prompt"

    def test_no_marker(self):
        required, data = check_approval_required("Normal output")
        assert required is False

    def test_partial_marker_not_matched(self):
        required, data = check_approval_required("APPROVAL_ONLY some text")
        assert required is False


class TestExperimentResult:
    def test_from_dict(self, sample_experiment_result):
        result = ExperimentResult.from_dict(sample_experiment_result)
        assert result.prompt_version_id == "prompt-v2-naviguard-001"
        assert result.prompt_tag == "naviguard-proposed"
        assert result.dataset_id == "dataset-naviguard-001"

    def test_change_summary_non_empty(self, sample_experiment_result):
        result = ExperimentResult.from_dict(sample_experiment_result)
        assert len(result.change_summary) > 0

    def test_expected_improvement_field(self, sample_experiment_result):
        result = ExperimentResult.from_dict(sample_experiment_result)
        assert len(result.expected_improvement) > 0


class TestParseExperimentResult:
    def test_parse_valid_json(self, sample_experiment_result):
        raw = json.dumps(sample_experiment_result)
        result = parse_experiment_result(raw)
        assert isinstance(result, ExperimentResult)

    def test_parse_invalid_raises(self):
        with pytest.raises((json.JSONDecodeError, KeyError)):
            parse_experiment_result("not json")


class TestBuildExperimentRunnerAgent:
    def test_agent_name(self, mock_phoenix_mcp):
        with patch("agent.specialists.experiment_runner.LlmAgent") as mock_agent:
            mock_agent.return_value = MagicMock()
            build_experiment_runner_agent()
            call_kwargs = mock_agent.call_args.kwargs
            assert call_kwargs["name"] == "experiment_runner"
            assert call_kwargs["output_key"] == "experiment_result"

    def test_prompt_mentions_upsert_prompt(self):
        from agent.specialists.experiment_runner import SYSTEM_PROMPT
        assert "upsert-prompt" in SYSTEM_PROMPT

    def test_prompt_mentions_add_version_tag(self):
        from agent.specialists.experiment_runner import SYSTEM_PROMPT
        assert "add-prompt-version-tag" in SYSTEM_PROMPT
        assert "naviguard-proposed" in SYSTEM_PROMPT

    def test_prompt_has_approval_gate(self):
        from agent.specialists.experiment_runner import SYSTEM_PROMPT
        assert "APPROVAL_REQUIRED" in SYSTEM_PROMPT
        assert "STOP" in SYSTEM_PROMPT

    def test_prompt_references_list_datasets(self):
        from agent.specialists.experiment_runner import SYSTEM_PROMPT
        assert "list-datasets" in SYSTEM_PROMPT

    def test_loop_closing_documented(self):
        """ExperimentRunner closes the self-improvement loop — must be clear in prompt."""
        from agent.specialists.experiment_runner import SYSTEM_PROMPT
        assert "loop" in SYSTEM_PROMPT.lower() or "self-improvement" in SYSTEM_PROMPT.lower()
