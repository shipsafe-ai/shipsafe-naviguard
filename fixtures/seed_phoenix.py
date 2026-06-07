"""Seed Phoenix with Hormuz crisis traces using OTel SDK.

Uses OTel SDK directly for emitting traces (not Phoenix MCP — MCP is for querying).
Phoenix MCP is used at runtime by NaviGuard agents to query these traces.
"""

from __future__ import annotations

import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")


def seed_hormuz_traces() -> None:
    from opentelemetry import trace
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor
    from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
    from opentelemetry.sdk.resources import Resource
    from openinference.semconv.trace import SpanAttributes

    phoenix_endpoint = os.environ.get("PHOENIX_COLLECTOR_ENDPOINT", "")
    phoenix_api_key = os.environ.get("PHOENIX_API_KEY", "")

    if not phoenix_endpoint or not phoenix_api_key:
        print("ERROR: PHOENIX_COLLECTOR_ENDPOINT and PHOENIX_API_KEY required")
        return

    otlp_endpoint = phoenix_endpoint.rstrip("/") + "/v1/traces"

    resource = Resource.create(
        {
            "openinference.project.name": "naviguard",
            "service.name": "naviguard-routing-model",
        }
    )

    exporter = OTLPSpanExporter(
        endpoint=otlp_endpoint,
        headers={
            "api_key": phoenix_api_key,
            "authorization": f"Bearer {phoenix_api_key}",
        },
    )

    provider = TracerProvider(resource=resource)
    provider.add_span_processor(BatchSpanProcessor(exporter))
    tracer = provider.get_tracer("naviguard-seeder")

    fixtures_path = Path(__file__).parent / "hormuz_traces.json"
    data = json.loads(fixtures_path.read_text())
    traces = data["traces"]

    print(f"Seeding {len(traces)} Hormuz crisis traces into Phoenix project 'naviguard'...")

    for t in traces:
        ts = datetime.fromisoformat(t["timestamp"].replace("Z", "+00:00"))
        ts_ns = int(ts.timestamp() * 1e9)

        with tracer.start_as_current_span(
            name=f"naviguard.routing.decision.{t['category'].lower()}",
            start_time=ts_ns,
            attributes={
                SpanAttributes.OPENINFERENCE_SPAN_KIND: "LLM",
                SpanAttributes.INPUT_VALUE: t["input"],
                SpanAttributes.OUTPUT_VALUE: str(t["confidence_score"]),
                "naviguard.category": t["category"],
                "naviguard.decision": t["decision"],
                "naviguard.confidence_score": t["confidence_score"],
                "naviguard.latency_ms": t["latency_ms"],
                "naviguard.scenario": "hormuz_crisis_2026_06_08",
                "category": t["category"],
            },
        ) as span:
            span.set_attribute("trace_id_fixture", t["trace_id"])
            span.set_attribute("span_id_fixture", t["span_id"])
            time.sleep(0.01)

    provider.force_flush()
    print(f"Done. Seeded {len(traces)} traces.")
    print("View at: https://app.phoenix.arize.com/s/prateek-srivastava23")
    print("Project: naviguard")
    print(f"Regression window: {data['regression_window']['start']} - {data['regression_window']['end']}")
    print(f"BLOCK confidence drop: {data['regression_window']['confidence_drop_pct']}%")


if __name__ == "__main__":
    seed_hormuz_traces()
