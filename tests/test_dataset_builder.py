"""Tests for DatasetBuilder — RED first per TDD rules."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from agent.specialists.dataset_builder import (
    ApprovalRequired,
    DatasetResult,
    build_dataset_builder_agent,
    check_approval_required,
    generate_approval_token,
    parse_dataset_result,
)


class TestApprovalRequired:
    def test_exception_has_token(self):
        exc = ApprovalRequired(token="tok-123", dataset_name="test-dataset", example_count=5)
        assert exc.token == "tok-123"
        assert exc.dataset_name == "test-dataset"
        assert exc.example_count == 5

    def test_exception_message_contains_token(self):
        exc = ApprovalRequired(token="tok-456", dataset_name="naviguard-ds", example_count=10)
        assert "tok-456" in str(exc)

    def test_is_exception(self):
        exc = ApprovalRequired(token="x", dataset_name="y", example_count=1)
        assert isinstance(exc, Exception)


class TestGenerateApprovalToken:
    def test_returns_string(self):
        token = generate_approval_token()
        assert isinstance(token, str)
        assert len(token) > 0

    def test_unique_tokens(self):
        tokens = {generate_approval_token() for _ in range(10)}
        assert len(tokens) == 10


class TestCheckApprovalRequired:
    def test_detects_approval_marker(self):
        raw = 'Some output\nAPPROVAL_REQUIRED:{"token": "abc", "dataset_name": "ds", "example_count": 5}\nMore text'
        required, data = check_approval_required(raw)
        assert required is True
        assert data["token"] == "abc"
        assert data["dataset_name"] == "ds"
        assert data["example_count"] == 5

    def test_no_marker_returns_false(self):
        raw = "Normal agent output without approval requirement"
        required, data = check_approval_required(raw)
        assert required is False
        assert data == {}

    def test_empty_string(self):
        required, data = check_approval_required("")
        assert required is False


class TestDatasetResult:
    def test_from_dict(self, sample_dataset_result):
        result = DatasetResult.from_dict(sample_dataset_result)
        assert result.dataset_id == "dataset-naviguard-001"
        assert result.example_count == 2
        assert result.approval_token == "approval-token-abc"

    def test_examples_preview(self, sample_dataset_result):
        result = DatasetResult.from_dict(sample_dataset_result)
        assert len(result.examples_preview) > 0

    def test_dataset_name_format(self, sample_dataset_result):
        result = DatasetResult.from_dict(sample_dataset_result)
        assert "naviguard" in result.dataset_name.lower()


class TestParseDatasetResult:
    def test_parse_valid_json(self, sample_dataset_result):
        raw = json.dumps(sample_dataset_result)
        result = parse_dataset_result(raw)
        assert isinstance(result, DatasetResult)

    def test_parse_invalid_raises(self):
        with pytest.raises((json.JSONDecodeError, KeyError)):
            parse_dataset_result("not json")


class TestBuildDatasetBuilderAgent:
    def test_agent_name(self, mock_phoenix_mcp):
        with patch("agent.specialists.dataset_builder.LlmAgent") as mock_agent:
            mock_agent.return_value = MagicMock()
            build_dataset_builder_agent()
            call_kwargs = mock_agent.call_args.kwargs
            assert call_kwargs["name"] == "dataset_builder"
            assert call_kwargs["output_key"] == "dataset_result"

    def test_prompt_mentions_list_datasets(self):
        from agent.specialists.dataset_builder import SYSTEM_PROMPT
        # Phoenix calls happen post-approval; prompt describes dataset spec building
        assert "dataset" in SYSTEM_PROMPT.lower()
        assert "examples" in SYSTEM_PROMPT.lower()

    def test_prompt_mentions_approval_gate(self):
        from agent.specialists.dataset_builder import SYSTEM_PROMPT
        assert "APPROVAL_REQUIRED" in SYSTEM_PROMPT

    def test_prompt_no_fabrication(self):
        from agent.specialists.dataset_builder import SYSTEM_PROMPT
        assert "Never fabricate" in SYSTEM_PROMPT or "ONLY" in SYSTEM_PROMPT
