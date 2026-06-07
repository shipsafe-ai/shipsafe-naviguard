"""NaviGuard CLI — naviguard init | run | status | approve."""

from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path

import typer
import httpx
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

app = typer.Typer(
    name="naviguard",
    help="NaviGuard — AI quality monitoring with self-improvement loops (Arize Phoenix)",
    no_args_is_help=True,
)

API_BASE = os.environ.get("NAVIGUARD_API_URL", "http://localhost:8080")


@app.command()
def init():
    """Check environment, test Phoenix MCP connectivity."""
    typer.echo("NaviGuard init check...")

    required = ["PHOENIX_API_KEY", "PHOENIX_COLLECTOR_ENDPOINT", "GOOGLE_CLOUD_PROJECT"]
    missing = [k for k in required if not os.environ.get(k)]
    if missing:
        typer.echo(f"Missing env vars: {', '.join(missing)}", err=True)
        raise typer.Exit(1)

    typer.echo(f"PHOENIX_API_KEY: {'***' + os.environ['PHOENIX_API_KEY'][-4:]}")
    typer.echo(f"PHOENIX_BASE_URL: {os.environ.get('PHOENIX_BASE_URL', 'not set')}")
    typer.echo(f"GEMINI_MODEL: {os.environ.get('GEMINI_MODEL', 'gemini-2.5-flash (default)')}")
    typer.echo(f"GOOGLE_CLOUD_PROJECT: {os.environ.get('GOOGLE_CLOUD_PROJECT')}")

    try:
        response = httpx.get(f"{API_BASE}/health", timeout=5.0)
        data = response.json()
        typer.echo(f"API health: {data['status']}")
        typer.echo(f"Phoenix project: {data.get('phoenix_project', 'naviguard')}")
    except Exception as e:
        typer.echo(f"API not reachable at {API_BASE}: {e}", err=True)
        typer.echo("Start with: make run-api")

    typer.echo("Init complete.")


@app.command()
def run(
    window: int = typer.Option(60, "--window", "-w", help="Analysis window in minutes"),
    scenario: str = typer.Option(None, "--scenario", "-s", help="Demo scenario (e.g. 'hormuz')"),
    api_url: str = typer.Option(None, "--api", help="NaviGuard API URL"),
):
    """Run NaviGuard quality monitoring pipeline."""
    base = api_url or API_BASE

    typer.echo(f"Running NaviGuard pipeline (window={window}m, scenario={scenario or 'live'})...")

    try:
        payload = {"window_minutes": window}
        if scenario:
            payload["scenario"] = scenario
        response = httpx.post(f"{base}/run", json=payload, timeout=120.0)
        data = response.json()
    except httpx.TimeoutException:
        typer.echo("Request timed out (>120s). Run in background: make run-api", err=True)
        raise typer.Exit(1)
    except Exception as e:
        typer.echo(f"Failed: {e}", err=True)
        raise typer.Exit(1)

    typer.echo(f"\nRun ID: {data.get('run_id')}")
    typer.echo(f"Status: {data.get('status')}")
    typer.echo(f"Regression: {data.get('regression_status', 'UNKNOWN')}")
    typer.echo(f"Root cause: {data.get('root_cause', '')}")
    typer.echo(f"Critic verdict: {data.get('critic_verdict', '')}")

    if data.get("status") == "awaiting_approval":
        typer.echo("\nPending approvals require human sign-off:")
        for ap in data.get("pending_approvals", []):
            typer.echo(f"  Token: {ap.get('token')} | Type: {ap.get('artifact_type')}")
            typer.echo(f"  Approve with: naviguard approve {ap.get('token')}")


@app.command()
def status(run_id: str = typer.Argument(None, help="Run ID to check")):
    """Check status of a NaviGuard run or list recent runs."""
    try:
        if run_id:
            response = httpx.get(f"{API_BASE}/run/{run_id}", timeout=10.0)
            typer.echo(json.dumps(response.json(), indent=2))
        else:
            response = httpx.get(f"{API_BASE}/regressions", timeout=10.0)
            regressions = response.json()
            if not regressions:
                typer.echo("No regressions detected in recent traces.")
            else:
                typer.echo(f"Found {len(regressions)} regression spans:")
                for r in regressions[:10]:
                    typer.echo(
                        f"  {r['timestamp'][:19]} | {r['category']:6} | "
                        f"conf={r['confidence_score']:.2f} | trace={r['trace_id'][:16]}..."
                    )
    except Exception as e:
        typer.echo(f"Failed: {e}", err=True)
        raise typer.Exit(1)


@app.command()
def approve(
    token: str = typer.Argument(..., help="Approval token from pending approval"),
    notes: str = typer.Option("", "--notes", "-n", help="Operator notes"),
    api_url: str = typer.Option(None, "--api", help="NaviGuard API URL"),
):
    """Approve a pending dataset or experiment creation."""
    base = api_url or API_BASE
    try:
        response = httpx.post(
            f"{base}/approve/{token}",
            json={"notes": notes},
            timeout=10.0,
        )
        data = response.json()
        if data.get("approved"):
            typer.echo(f"Approved: {data.get('message')}")
        else:
            typer.echo(f"Failed to approve: {data}", err=True)
            raise typer.Exit(1)
    except httpx.HTTPStatusError as e:
        typer.echo(f"HTTP error: {e.response.status_code} — {e.response.text}", err=True)
        raise typer.Exit(1)
    except Exception as e:
        typer.echo(f"Failed: {e}", err=True)
        raise typer.Exit(1)


@app.command()
def datasets():
    """List Phoenix datasets created by NaviGuard."""
    try:
        response = httpx.get(f"{API_BASE}/datasets", timeout=30.0)
        items = response.json()
        if not items:
            typer.echo("No NaviGuard datasets found.")
            return
        for d in items:
            typer.echo(f"  {d['dataset_id']} | {d['dataset_name']} | {d['example_count']} examples")
    except Exception as e:
        typer.echo(f"Failed: {e}", err=True)
        raise typer.Exit(1)


@app.command()
def experiments():
    """List Phoenix prompt versions created by NaviGuard."""
    try:
        response = httpx.get(f"{API_BASE}/experiments", timeout=30.0)
        items = response.json()
        if not items:
            typer.echo("No NaviGuard experiments found.")
            return
        for e in items:
            typer.echo(
                f"  {e['prompt_version_id']} | tag={e['prompt_tag']} | {e['change_summary'][:60]}"
            )
    except Exception as e:
        typer.echo(f"Failed: {e}", err=True)
        raise typer.Exit(1)


if __name__ == "__main__":
    app()
