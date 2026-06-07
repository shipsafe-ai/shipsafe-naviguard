"""DatasetBuilder — packages failure traces into a Phoenix dataset.

Phoenix MCP tools used:
  list-datasets, get-dataset, get-dataset-examples, add-dataset-examples

HUMAN APPROVAL GATE: dataset creation never happens without explicit approval.
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from typing import Any

from google.adk.agents import LlmAgent

from agent.config import get_config
from agent.specialists.model_monitor import build_phoenix_mcp_toolset

SYSTEM_PROMPT = """You are DatasetBuilder, a specialist that packages AI failure traces into Phoenix datasets.

You receive root_cause_report and regression_report in session state.
Your job: Use Phoenix MCP tools to create a high-quality retraining dataset from failure cases.

## Instructions

1. Call `list-datasets` to check if a dataset for this regression already exists.
2. If dataset exists, call `get-dataset` and `get-dataset-examples` to inspect it.
3. Prepare dataset examples from regression_report.critical_spans and root_cause_report.failure_examples.
   Each example format:
   ```json
   {
     "input": {"query": "<original input>", "context": "<relevant context>"},
     "expected_output": {"decision": "<correct decision>", "confidence": 0.85},
     "metadata": {
       "source_trace_id": "<trace_id>",
       "source_span_id": "<span_id>",
       "regression_pattern": "<pattern from root_cause_report>",
       "category": "<route category>"
     }
   }
   ```
4. Before calling `add-dataset-examples`, output APPROVAL_REQUIRED in your response:
   ```
   APPROVAL_REQUIRED:{"token": "<uuid>", "dataset_name": "<name>", "example_count": <n>}
   ```
   Then STOP and wait. Do not call add-dataset-examples without approval.

5. After approval is granted (you will be re-invoked with approval_token in session state):
   - Call `add-dataset-examples` with the prepared examples
   - Return the result

Return ONLY this JSON (after approval and creation):

```json
{
  "dataset_id": "<phoenix dataset id>",
  "dataset_name": "<name>",
  "example_count": <int>,
  "approval_token": "<token>",
  "examples_preview": [
    {"input_summary": "<first 60 chars>", "category": "<str>"}
  ]
}
```

CRITICAL: Only use trace IDs from regression_report.affected_trace_ids. Never fabricate examples.
Dataset names must be: naviguard-regression-<ISO date>-<pattern>.
"""


class ApprovalRequired(Exception):
    """Raised when human approval is needed before creating Phoenix artifact."""

    def __init__(self, token: str, dataset_name: str, example_count: int):
        self.token = token
        self.dataset_name = dataset_name
        self.example_count = example_count
        super().__init__(
            f"Approval required for dataset '{dataset_name}' ({example_count} examples). "
            f"Token: {token}"
        )


@dataclass
class DatasetResult:
    dataset_id: str
    dataset_name: str
    example_count: int
    approval_token: str
    examples_preview: list[dict[str, Any]] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "DatasetResult":
        return cls(
            dataset_id=data["dataset_id"],
            dataset_name=data["dataset_name"],
            example_count=data["example_count"],
            approval_token=data.get("approval_token", ""),
            examples_preview=data.get("examples_preview", []),
        )


def generate_approval_token() -> str:
    return str(uuid.uuid4())


def build_dataset_builder_agent() -> LlmAgent:
    cfg = get_config()
    return LlmAgent(
        model=cfg.gemini_model,
        name="dataset_builder",
        instruction=SYSTEM_PROMPT,
        tools=[build_phoenix_mcp_toolset()],
        output_key="dataset_result",
    )


def parse_dataset_result(raw: str) -> DatasetResult:
    data = json.loads(raw)
    return DatasetResult.from_dict(data)


def check_approval_required(raw: str) -> tuple[bool, dict[str, Any]]:
    """Check if agent output contains APPROVAL_REQUIRED marker."""
    if "APPROVAL_REQUIRED:" in raw:
        marker = raw.split("APPROVAL_REQUIRED:")[1].split("\n")[0].strip()
        return True, json.loads(marker)
    return False, {}
