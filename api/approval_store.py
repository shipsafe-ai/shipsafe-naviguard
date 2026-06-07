"""In-memory approval store for human-gated dataset/experiment creation."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any


@dataclass
class PendingApproval:
    token: str
    artifact_type: str  # "dataset" | "experiment"
    details: dict[str, Any]
    event: asyncio.Event = field(default_factory=asyncio.Event)
    approved: bool = False


class ApprovalStore:
    def __init__(self) -> None:
        self._pending: dict[str, PendingApproval] = {}

    def request_approval(
        self,
        token: str,
        artifact_type: str,
        details: dict[str, Any],
    ) -> PendingApproval:
        approval = PendingApproval(token=token, artifact_type=artifact_type, details=details)
        self._pending[token] = approval
        return approval

    def grant_approval(self, token: str) -> bool:
        if token not in self._pending:
            return False
        self._pending[token].approved = True
        self._pending[token].event.set()
        return True

    async def wait_for_approval(self, token: str, timeout: float = 300.0) -> bool:
        if token not in self._pending:
            return False
        try:
            await asyncio.wait_for(self._pending[token].event.wait(), timeout=timeout)
            return self._pending[token].approved
        except asyncio.TimeoutError:
            return False

    def list_pending(self) -> list[PendingApproval]:
        return [a for a in self._pending.values() if not a.approved]

    def get(self, token: str) -> PendingApproval | None:
        return self._pending.get(token)

    def remove(self, token: str) -> None:
        self._pending.pop(token, None)


approval_store = ApprovalStore()
