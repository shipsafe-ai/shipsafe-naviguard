"""Tests for FastAPI endpoints — RED first per TDD rules."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from api.main import app
from api.approval_store import ApprovalStore


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def fresh_approval_store():
    store = ApprovalStore()
    return store


class TestHealthEndpoint:
    def test_health_returns_ok(self, client):
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert "phoenix_project" in data
        assert data["phoenix_project"] == "naviguard-test"

    def test_health_includes_model(self, client):
        response = client.get("/health")
        data = response.json()
        assert "gemini_model" in data
        assert "gemini" in data["gemini_model"]


class TestApprovalStore:
    def test_request_approval(self, fresh_approval_store):
        approval = fresh_approval_store.request_approval(
            token="tok-1", artifact_type="dataset", details={"name": "test"}
        )
        assert approval.token == "tok-1"
        assert not approval.approved

    def test_grant_approval(self, fresh_approval_store):
        fresh_approval_store.request_approval(
            token="tok-2", artifact_type="experiment", details={}
        )
        success = fresh_approval_store.grant_approval("tok-2")
        assert success is True
        assert fresh_approval_store.get("tok-2").approved is True

    def test_grant_nonexistent_token(self, fresh_approval_store):
        success = fresh_approval_store.grant_approval("nonexistent-token")
        assert success is False

    @pytest.mark.asyncio
    async def test_wait_for_approval_timeout(self, fresh_approval_store):
        fresh_approval_store.request_approval(
            token="tok-timeout", artifact_type="dataset", details={}
        )
        result = await fresh_approval_store.wait_for_approval("tok-timeout", timeout=0.01)
        assert result is False

    @pytest.mark.asyncio
    async def test_wait_for_approval_granted(self, fresh_approval_store):
        import asyncio
        fresh_approval_store.request_approval(
            token="tok-grant", artifact_type="dataset", details={}
        )

        async def grant_after_delay():
            await asyncio.sleep(0.05)
            fresh_approval_store.grant_approval("tok-grant")

        asyncio.create_task(grant_after_delay())
        result = await fresh_approval_store.wait_for_approval("tok-grant", timeout=1.0)
        assert result is True

    def test_list_pending_only_unapproved(self, fresh_approval_store):
        fresh_approval_store.request_approval("tok-a", "dataset", {})
        fresh_approval_store.request_approval("tok-b", "experiment", {})
        fresh_approval_store.grant_approval("tok-a")
        pending = fresh_approval_store.list_pending()
        assert len(pending) == 1
        assert pending[0].token == "tok-b"


class TestRunEndpoint:
    def test_run_returns_run_id(self, client):
        with patch("api.main.run_naviguard") as mock_run:
            from agent.orchestrator import NaviGuardRunResult
            mock_run.return_value = NaviGuardRunResult(
                run_id="test-run-001",
                status="completed",
                regression_report={"status": "REGRESSION"},
                root_cause_report={"root_cause": "Novel distribution"},
                critic_report={"verdict": "CORRECT"},
            )
            response = client.post("/run", json={"window_minutes": 60})
            assert response.status_code == 200
            data = response.json()
            assert data["run_id"] == "test-run-001"
            assert data["status"] == "completed"

    def test_run_with_scenario(self, client):
        with patch("api.main.run_naviguard") as mock_run:
            from agent.orchestrator import NaviGuardRunResult
            mock_run.return_value = NaviGuardRunResult(run_id="run-002", status="completed")
            response = client.post("/run", json={"window_minutes": 60, "scenario": "hormuz"})
            assert response.status_code == 200
            mock_run.assert_called_once_with(window_minutes=60, scenario="hormuz")


class TestApproveEndpoint:
    def test_approve_valid_token(self, client):
        from agent.pending_actions import register, clear
        clear()
        register("tok-api-1", "dataset", {"dataset_name": "test", "examples": []})
        response = client.post("/approve/tok-api-1", json={})
        assert response.status_code == 200
        data = response.json()
        assert data["approved"] is True
        assert data["token"] == "tok-api-1"

    def test_approve_invalid_token(self, client):
        response = client.post("/approve/nonexistent-token-xyz", json={})
        assert response.status_code == 404

    def test_approve_with_notes(self, client):
        from agent.pending_actions import register, clear
        clear()
        register("tok-api-2", "experiment", {"prompt_identifier": "naviguard-routing-prompt", "prompt_template": "test", "change_summary": "test", "prompt_tag": "naviguard-proposed"})
        response = client.post("/approve/tok-api-2", json={"notes": "Reviewed by operator"})
        assert response.status_code == 200
        data = response.json()
        assert "Reviewed by operator" in data["message"]
