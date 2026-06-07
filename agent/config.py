"""NaviGuard runtime configuration — all secrets from env/GCP Secret Manager."""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Config:
    gemini_model: str
    phoenix_api_key: str
    phoenix_collector_endpoint: str
    phoenix_base_url: str
    phoenix_project_name: str
    google_cloud_project: str
    google_cloud_location: str
    confidence_regression_threshold: float
    confidence_baseline_window_hours: int


def load_config() -> Config:
    return Config(
        gemini_model=os.environ.get("GEMINI_MODEL", "gemini-2.5-flash"),
        phoenix_api_key=os.environ.get("PHOENIX_API_KEY", ""),
        phoenix_collector_endpoint=os.environ.get("PHOENIX_COLLECTOR_ENDPOINT", ""),
        phoenix_base_url=os.environ.get(
            "PHOENIX_BASE_URL",
            "https://app.phoenix.arize.com/s/prateek-srivastava23",
        ),
        phoenix_project_name=os.environ.get("PHOENIX_PROJECT_NAME", "naviguard"),
        google_cloud_project=os.environ.get("GOOGLE_CLOUD_PROJECT", ""),
        google_cloud_location=os.environ.get("GOOGLE_CLOUD_LOCATION", "us-central1"),
        confidence_regression_threshold=float(
            os.environ.get("CONFIDENCE_REGRESSION_THRESHOLD", "0.70")
        ),
        confidence_baseline_window_hours=int(
            os.environ.get("CONFIDENCE_BASELINE_WINDOW_HOURS", "24")
        ),
    )


_config: Config | None = None


def get_config() -> Config:
    global _config
    if _config is None:
        _config = load_config()
    return _config
