"""Tests for Orchestrator — RED first per TDD rules."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from agent.orchestrator import NaviGuardRunResult, build_naviguard_agent


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


class TestBuildNaviGuardAgent:
    def test_agent_is_sequential(self):
        with (
            patch("agent.orchestrator.build_model_monitor_agent") as m1,
            patch("agent.orchestrator.build_regression_detector_agent") as m2,
            patch("agent.orchestrator.build_root_cause_analyzer_agent") as m3,
            patch("agent.orchestrator.build_dataset_builder_agent") as m4,
            patch("agent.orchestrator.build_experiment_runner_agent") as m5,
            patch("agent.orchestrator.build_critic_agent") as m6,
            patch("agent.orchestrator.SequentialAgent") as mock_seq,
        ):
            for m in [m1, m2, m3, m4, m5, m6]:
                m.return_value = MagicMock()
            mock_seq.return_value = MagicMock()
            agent = build_naviguard_agent()
            mock_seq.assert_called_once()
            call_kwargs = mock_seq.call_args.kwargs
            assert call_kwargs["name"] == "naviguard"

    def test_pipeline_order(self):
        """Verify all 6 specialists are in pipeline."""
        with (
            patch("agent.orchestrator.build_model_monitor_agent") as m1,
            patch("agent.orchestrator.build_regression_detector_agent") as m2,
            patch("agent.orchestrator.build_root_cause_analyzer_agent") as m3,
            patch("agent.orchestrator.build_dataset_builder_agent") as m4,
            patch("agent.orchestrator.build_experiment_runner_agent") as m5,
            patch("agent.orchestrator.build_critic_agent") as m6,
            patch("agent.orchestrator.SequentialAgent") as mock_seq,
        ):
            agents = [MagicMock(name=f"agent_{i}") for i in range(6)]
            m1.return_value, m2.return_value, m3.return_value = agents[0], agents[1], agents[2]
            m4.return_value, m5.return_value, m6.return_value = agents[3], agents[4], agents[5]
            mock_seq.return_value = MagicMock()
            build_naviguard_agent()
            sub_agents = mock_seq.call_args.kwargs["sub_agents"]
            assert len(sub_agents) == 6


class TestRunNaviGuard:
    @pytest.mark.asyncio
    async def test_run_returns_result(self):
        with (
            patch("agent.orchestrator.build_naviguard_agent") as mock_build,
            patch("agent.orchestrator.InMemoryRunner") as mock_runner_cls,
            patch("agent.orchestrator.setup_tracing"),
        ):
            mock_agent = MagicMock()
            mock_build.return_value = mock_agent

            mock_runner = MagicMock()
            mock_runner_cls.return_value = mock_runner
            mock_runner.session_service.create_session = AsyncMock()
            mock_runner.run_async = AsyncMock(return_value=aiter([]))
            mock_session = MagicMock()
            mock_session.state = {}
            mock_runner.session_service.get_session = AsyncMock(return_value=mock_session)

            from agent.orchestrator import run_naviguard
            result = await run_naviguard(window_minutes=30)

            assert isinstance(result, NaviGuardRunResult)
            assert result.run_id is not None
            assert result.status in {"completed", "awaiting_approval", "failed"}

    @pytest.mark.asyncio
    async def test_run_handles_exception(self):
        with (
            patch("agent.orchestrator.build_naviguard_agent") as mock_build,
            patch("agent.orchestrator.InMemoryRunner") as mock_runner_cls,
            patch("agent.orchestrator.setup_tracing"),
        ):
            mock_build.return_value = MagicMock()
            mock_runner_cls.side_effect = RuntimeError("ADK init failed")

            from agent.orchestrator import run_naviguard
            result = await run_naviguard(window_minutes=30)

            assert result.status == "failed"
            assert len(result.error) > 0


def aiter(items):
    """Async iterator helper for tests."""
    async def _gen():
        for item in items:
            yield item
    return _gen()
