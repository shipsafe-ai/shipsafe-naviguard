"""NaviGuard Orchestrator — ADK SequentialAgent chaining all specialists.

Pipeline:
  ModelMonitor → RegressionDetector → RootCauseAnalyzer
    → DatasetBuilder → ExperimentRunner → Critic

Each specialist's output is stored in session state under output_key.
The Critic makes final approval decisions for dataset/experiment creation.
"""

from __future__ import annotations

import asyncio
import json
import secrets
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

from google.adk.agents import SequentialAgent
from google.adk.runners import InMemoryRunner
from google.genai import types

from agent.config import get_config
from agent.instrumentation import setup_tracing
from agent.specialists.model_monitor import build_model_monitor_agent
from agent.specialists.regression_detector import build_regression_detector_agent
from agent.specialists.root_cause_analyzer import build_root_cause_analyzer_agent
from agent.specialists.dataset_builder import build_dataset_builder_agent
from agent.specialists.experiment_runner import build_experiment_runner_agent
from agent.critic import build_critic_agent

ORCHESTRATOR_INSTRUCTION = """You are the NaviGuard orchestrator. Your job is to coordinate the
self-improvement loop for AI model quality monitoring.

The pipeline runs in sequence:
1. ModelMonitor retrieves recent traces/spans from Phoenix
2. RegressionDetector identifies confidence drops and category drift
3. RootCauseAnalyzer explains why the model is degrading
4. DatasetBuilder packages failure cases into a Phoenix dataset (requires human approval)
5. ExperimentRunner creates a new versioned prompt in Phoenix (requires human approval)
6. Critic validates all outputs and detects prompt injection

Pass the window_minutes from the user request to ModelMonitor.
Ensure each specialist's output is available in session state for the next.
"""


@dataclass
class NaviGuardRunResult:
    run_id: str
    status: str  # "completed" | "awaiting_approval" | "failed"
    monitor_report: dict[str, Any] = field(default_factory=dict)
    regression_report: dict[str, Any] = field(default_factory=dict)
    root_cause_report: dict[str, Any] = field(default_factory=dict)
    dataset_result: dict[str, Any] = field(default_factory=dict)
    experiment_result: dict[str, Any] = field(default_factory=dict)
    critic_report: dict[str, Any] = field(default_factory=dict)
    pending_approvals: list[dict[str, Any]] = field(default_factory=list)
    error: str = ""


def build_naviguard_agent() -> SequentialAgent:
    return SequentialAgent(
        name="naviguard",
        description=ORCHESTRATOR_INSTRUCTION,
        sub_agents=[
            build_model_monitor_agent(),
            build_regression_detector_agent(),
            build_root_cause_analyzer_agent(),
            build_dataset_builder_agent(),
            build_experiment_runner_agent(),
            build_critic_agent(),
        ],
    )


async def run_naviguard(
    window_minutes: int = 60,
    scenario: str | None = None,
) -> NaviGuardRunResult:
    """Run full NaviGuard pipeline. Returns result with any pending approvals."""
    setup_tracing()

    cfg = get_config()
    run_id = secrets.token_hex(8)
    app_name = "naviguard"
    user_id = "system"
    session_id = secrets.token_hex(8)

    agent = build_naviguard_agent()

    scenario_text = " Use Hormuz crisis scenario fixtures." if scenario == "hormuz" else ""
    prompt = (
        f"Run NaviGuard quality monitoring pipeline. "
        f"Analyze the last {window_minutes} minutes of traces.{scenario_text}"
    )

    result = NaviGuardRunResult(run_id=run_id, status="completed")

    try:
        runner = InMemoryRunner(agent=agent, app_name=app_name)

        await runner.session_service.create_session(
            app_name=app_name, user_id=user_id, session_id=session_id
        )

        async for event in runner.run_async(
            user_id=user_id,
            session_id=session_id,
            new_message=types.Content(role="user", parts=[types.Part(text=prompt)]),
        ):
            pass

        session = await runner.session_service.get_session(
            app_name=app_name, user_id=user_id, session_id=session_id
        )
        state = session.state if session else {}

        def safe_json(key: str) -> dict[str, Any]:
            raw = state.get(key, "{}")
            if isinstance(raw, dict):
                return raw
            try:
                return json.loads(raw)
            except (json.JSONDecodeError, TypeError):
                return {}

        result.monitor_report = safe_json("monitor_report")
        result.regression_report = safe_json("regression_report")
        result.root_cause_report = safe_json("root_cause_report")
        result.dataset_result = safe_json("dataset_result")
        result.experiment_result = safe_json("experiment_result")
        result.critic_report = safe_json("critic_report")

        if "APPROVAL_REQUIRED" in json.dumps(result.dataset_result):
            result.status = "awaiting_approval"
        if "APPROVAL_REQUIRED" in json.dumps(result.experiment_result):
            result.status = "awaiting_approval"

    except Exception as e:
        result.status = "failed"
        result.error = str(e)

    return result


root_agent = build_naviguard_agent()
