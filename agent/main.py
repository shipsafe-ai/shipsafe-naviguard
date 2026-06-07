"""NaviGuard entry point — one ADK turn with Phoenix tracing."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

import sys as _sys
_sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from agent.instrumentation import setup_tracing
from agent.orchestrator import run_naviguard


async def main_async(args: list[str]) -> None:
    setup_tracing()

    window_minutes = 60
    scenario = None

    for i, arg in enumerate(args):
        if arg == "--scenario" and i + 1 < len(args):
            scenario = args[i + 1]
        elif arg.isdigit():
            window_minutes = int(arg)

    result = await run_naviguard(window_minutes=window_minutes, scenario=scenario)

    import json
    print(json.dumps(
        {
            "run_id": result.run_id,
            "status": result.status,
            "regression_status": result.regression_report.get("status", "UNKNOWN"),
            "root_cause": result.root_cause_report.get("root_cause", ""),
            "critic_verdict": result.critic_report.get("verdict", ""),
            "pending_approvals": result.pending_approvals,
        },
        indent=2,
    ))


def main() -> None:
    asyncio.run(main_async(sys.argv[1:]))


if __name__ == "__main__":
    main()
