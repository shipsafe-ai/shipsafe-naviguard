"""Phoenix tracing via phoenix.otel.register with auto_instrument=True.

auto_instrument=True detects all installed OpenInference packages automatically.
Do NOT use set_global_tracer_provider=False — that's only for Agent Engine.
NaviGuard runs on Cloud Run.
"""

from __future__ import annotations

import os
from typing import Any, Optional

_provider: Optional[Any] = None


def setup_tracing() -> Optional[Any]:
    """Returns tracer provider when Phoenix auth configured, else None."""
    global _provider
    if _provider is not None:
        return _provider
    if not (os.environ.get("PHOENIX_API_KEY") or "").strip():
        return None

    from phoenix.otel import register

    _provider = register(
        project_name=os.environ.get("PHOENIX_PROJECT_NAME", "naviguard"),
        batch=False,
        auto_instrument=True,
        verbose=False,
    )
    return _provider


def reset_tracing() -> None:
    """Test helper — resets singleton so tests can reinitialize."""
    global _provider
    _provider = None
