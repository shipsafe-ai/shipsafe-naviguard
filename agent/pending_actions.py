"""Shared in-memory store for pending NaviGuard approval actions.

Orchestrator writes here after each agent outputs APPROVAL_REQUIRED.
API /approve endpoint reads here to execute the actual Phoenix MCP calls.
Shared within one process (FastAPI + orchestrator run in same process).
"""

from __future__ import annotations

from typing import Any

# token → {"type": "dataset"|"experiment", "spec": {...}}
_store: dict[str, dict[str, Any]] = {}


def register(token: str, action_type: str, spec: dict[str, Any]) -> None:
    """Store a pending action keyed by token."""
    _store[token] = {"type": action_type, "spec": spec}


def get(token: str) -> dict[str, Any] | None:
    """Read a pending action without consuming it."""
    return _store.get(token)


def consume(token: str) -> dict[str, Any] | None:
    """Read and remove a pending action (post-approval execution)."""
    return _store.pop(token, None)


def list_pending() -> list[dict[str, Any]]:
    """List all pending actions."""
    return [{"token": k, **v} for k, v in _store.items()]


def clear() -> None:
    """Clear all pending actions (for testing)."""
    _store.clear()
