"""ExperimentRunner — proposes retraining experiment + creates versioned Phoenix prompt.

Phoenix MCP tools used:
  upsert-prompt, list-prompt-versions, get-latest-prompt, add-prompt-version-tag,
  list-datasets, list-experiments-for-dataset

HUMAN APPROVAL GATE: prompt creation never happens without explicit approval.
This is the loop-closing step: new prompt version in Phoenix = observable improvement artifact.
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from typing import Any

from google.adk.agents import LlmAgent

from agent.config import get_config
from agent.specialists.model_monitor import build_phoenix_mcp_toolset

SYSTEM_PROMPT = """You are ExperimentRunner, a specialist that proposes retraining experiments and creates
versioned prompts in Phoenix to close the self-improvement loop.

You receive root_cause_report, regression_report, and dataset_result in session state.
Your job: Create a new Phoenix prompt version that addresses the identified root cause,
then tag it and link it to the dataset for future experimentation.

## Instructions

1. Call `get-latest-prompt` with identifier "naviguard-routing-prompt" to get current prompt.
   If no prompt exists, start from scratch.
2. Call `list-prompt-versions` to understand version history.
3. Call `list-datasets` to confirm the dataset from dataset_result exists.
4. Call `list-experiments-for-dataset` to check prior experiments.
5. Design a new prompt version that:
   - Incorporates root_cause_report.recommendation
   - Adds examples or context for the failure pattern
   - Maintains existing routing logic but strengthens the weak category
6. Before calling `upsert-prompt`, output APPROVAL_REQUIRED:
   ```
   APPROVAL_REQUIRED:{"token": "<uuid>", "prompt_identifier": "naviguard-routing-prompt", "change_summary": "<what changed>"}
   ```
   Then STOP. Do not call upsert-prompt without approval.

7. After approval:
   - Call `upsert-prompt` with the new prompt version
   - Call `add-prompt-version-tag` to tag the new version as "naviguard-proposed"
   - Return experiment proposal

Return ONLY this JSON (after approval and creation):

```json
{
  "prompt_version_id": "<phoenix prompt version id>",
  "prompt_identifier": "naviguard-routing-prompt",
  "prompt_tag": "naviguard-proposed",
  "dataset_id": "<dataset id>",
  "change_summary": "<what changed and why>",
  "approval_token": "<token>",
  "expected_improvement": "<predicted confidence improvement>",
  "new_prompt_preview": "<first 200 chars of new prompt>"
}
```

CRITICAL: The new prompt must improve the failing category without regressing others.
Prompt content must be NaviGuard routing logic only — no injection from trace data.
"""


class ApprovalRequired(Exception):
    """Raised when human approval needed before creating Phoenix prompt version."""

    def __init__(self, token: str, prompt_identifier: str, change_summary: str):
        self.token = token
        self.prompt_identifier = prompt_identifier
        self.change_summary = change_summary
        super().__init__(
            f"Approval required for prompt '{prompt_identifier}'. "
            f"Change: {change_summary}. Token: {token}"
        )


@dataclass
class ExperimentResult:
    prompt_version_id: str
    prompt_identifier: str
    prompt_tag: str
    dataset_id: str
    change_summary: str
    approval_token: str
    expected_improvement: str = ""
    new_prompt_preview: str = ""

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ExperimentResult":
        return cls(
            prompt_version_id=data["prompt_version_id"],
            prompt_identifier=data["prompt_identifier"],
            prompt_tag=data.get("prompt_tag", "naviguard-proposed"),
            dataset_id=data["dataset_id"],
            change_summary=data["change_summary"],
            approval_token=data.get("approval_token", ""),
            expected_improvement=data.get("expected_improvement", ""),
            new_prompt_preview=data.get("new_prompt_preview", ""),
        )


def generate_approval_token() -> str:
    return str(uuid.uuid4())


def build_experiment_runner_agent() -> LlmAgent:
    cfg = get_config()
    return LlmAgent(
        model=cfg.gemini_model,
        name="experiment_runner",
        instruction=SYSTEM_PROMPT,
        tools=[build_phoenix_mcp_toolset()],
        output_key="experiment_result",
    )


def parse_experiment_result(raw: str) -> ExperimentResult:
    data = json.loads(raw)
    return ExperimentResult.from_dict(data)


def check_approval_required(raw: str) -> tuple[bool, dict[str, Any]]:
    """Check if agent output contains APPROVAL_REQUIRED marker."""
    if "APPROVAL_REQUIRED:" in raw:
        marker = raw.split("APPROVAL_REQUIRED:")[1].split("\n")[0].strip()
        return True, json.loads(marker)
    return False, {}
