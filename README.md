# NaviGuard

**Your AI made 500 decisions today. Were any of them regressions?**

Every AI system in production makes thousands of silent decisions a day —
each one carrying a confidence score that nobody is watching. When a model
quietly degrades on one category of inputs while overall accuracy looks fine,
you don't get an alert. You get an incident, weeks later, after the damage.

NaviGuard is an autonomous AI-quality agent that closes the loop from
**detection** to **fix**. It continuously reads your model's traces, detects
confidence regressions, finds the root cause, builds a labeled dataset from
the exact failures, and proposes a new versioned prompt to correct them — then
stops and waits for a human to approve. It is an agent that uses its own
observability data to improve over time.

NaviGuard is **demonstrated on maritime crisis routing but works for any AI
system producing confidence scores** — fraud detection, medical triage,
recommendation ranking, content moderation, support routing, or any model
emitting a scored decision per request.

---

## The self-improvement loop

This is the whole product in one diagram. Every step is traceable in Arize
Phoenix, and nothing touches your systems of record without human sign-off.

```
   Phoenix traces (your model's real decisions)
        │
        ▼
   1. ModelMonitor        ── read traces + spans, compute confidence stats
        │
        ▼
   2. RegressionDetector  ── compare vs baseline, flag category drift
        │
        ▼
   3a. RootCauseAnalyzer  ─┐
   3b. DatasetBuilder      ├─ run in parallel
   3c. ExperimentRunner   ─┘
        │
        ▼
   4. Critic              ── adversarial review + prompt-injection defense
        │
        ▼
   HUMAN APPROVAL GATE    ── operator approves or rejects
        │
        ▼
   Phoenix dataset created  +  new prompt version tagged `naviguard-proposed`
```

Detect a regression → diagnose it → build a labeled dataset from the failing
cases → propose a corrected, versioned prompt. Observation feeds improvement,
and the improvement is itself a Phoenix artifact you can experiment against.

---

## How it works

NaviGuard reasons over your telemetry instead of pattern-matching on it.
Raw Phoenix trace data is formatted into structured context, Gemini produces a
typed decision (verdict + confidence + evidence + reasoning), and the result is
streamed to the operator for approval.

**Five specialists plus an adversarial Critic**, orchestrated as a fast,
partly-parallel pipeline:

| Specialist | Role |
|---|---|
| **ModelMonitor** | Queries Phoenix traces, spans, and sessions; computes confidence statistics per category |
| **RegressionDetector** | Compares current confidence vs the configured baseline (default 0.70), flags category-specific drift |
| **RootCauseAnalyzer** | Explains *why* the model degraded — pattern classification tied to trace evidence |
| **DatasetBuilder** | Produces a labeled-dataset spec from the failing cases |
| **ExperimentRunner** | Proposes a corrected, versioned prompt to fix the regression |
| **Critic** | Adversarially challenges every conclusion and verifies cited trace IDs actually exist in Phoenix (hallucinated IDs are treated as a prompt-injection signal) |

The Critic runs in **every** path and is never skipped. Decisions never
auto-execute — writing a dataset or a prompt version to Phoenix happens *only*
after a human approves.

### Fast, streaming pipeline

The orchestrator issues **direct Gemini calls** (`genai.Client` on Vertex AI)
with `thinking_budget=0`, and runs the three analysis specialists concurrently
via `asyncio.gather`. A full run completes in **~21 seconds** (down from ~350s,
which previously hit Cloud Run's request timeout).

Runs stream over Server-Sent Events at **`POST /run/stream`**: the dashboard
shows live `✓ / ● / ○` status per step and renders Gemini's reasoning as it
arrives — the regression summary, root cause, recommended fix, and the Critic's
critique.

---

## Arize Phoenix integration

Phoenix is NaviGuard's memory and its workbench. The agent talks to Phoenix
exclusively through the **official Phoenix MCP server**
(`@arizeai/phoenix-mcp`, pre-installed in the container and invoked over the
MCP stdio protocol — not `npx @latest`, which is unreliable at runtime).

Phoenix MCP tools NaviGuard uses:

- **Read** — `list-traces`, `get-spans`, `list-datasets`, `list-prompt-versions`
- **Write (post-approval only)** — `add-dataset-examples`, `upsert-prompt`,
  `add-prompt-version-tag`

The loop's outputs are real Phoenix artifacts: a labeled dataset built from the
failing spans, and a new prompt version tagged `naviguard-proposed`, both
visible and replayable in your Phoenix space.

Every LLM call — including the evaluator/judge — runs on **Gemini via Vertex
AI**. The Phoenix evaluator is wired through `LiteLLMModel(model="vertex_ai/…")`,
never an OpenAI judge.

---

## Prompt-injection defense

Trace data — span attributes, categories, free-text fields — is attacker-
reachable and is treated as **data, never instructions**:

- User-controlled content is passed to Gemini as opaque structured input.
- The Critic explicitly checks whether any field value is instruction-like and
  whether the analysis can be manipulated.
- The Critic verifies that every cited trace ID resolves to a real span in
  Phoenix; a hallucinated ID is flagged as an injection signal and blocks
  dataset/prompt creation.
- No verdict auto-executes. The human approval gate is mandatory before any
  write to Phoenix.

---

## Quickstart

NaviGuard deploys with one command:

```bash
npx shipsafe-naviguard init     # health check + connection details
npx shipsafe-naviguard demo     # run the Hormuz crisis scenario end-to-end
npx shipsafe-naviguard health   # check the deployed agent
```

**Live deployment:**

- Agent (API): `https://naviguard-o34wppiwiq-uc.a.run.app`
- Dashboard: `https://naviguard-dashboard-336382452417.us-central1.run.app`

### Run the demo

Click **Run Hormuz Demo** in the dashboard (or `npx shipsafe-naviguard demo`).
The pipeline runs against a deterministic fixture and, in ~21 seconds, produces:

- `crisis_avoidance` confidence **0.31** vs a **0.70** baseline → **REGRESSION**
- Root-cause pattern: **NOVEL_DISTRIBUTION**
- **Critic verdict: CORRECT**
- Status: **awaiting_approval** — dataset and prompt version are created in
  Phoenix only after you `POST /approve`.

### Connect your own data

```bash
npx shipsafe-naviguard connect --uri <your-phoenix-space>
```

Point NaviGuard at any Phoenix project whose spans carry a confidence score and
category, and the same loop runs on your model.

---

## API

| Endpoint | Description |
|---|---|
| `GET /health` | Service + Phoenix + Gemini model status |
| `POST /run/stream` | Run the pipeline, streaming step events over SSE |
| `POST /run` | Run the pipeline, return the full result as JSON |
| `POST /approve/{token}` | Approve a pending dataset or prompt-version write |
| `GET /approvals/pending` | List artifacts awaiting human approval |
| `GET /regressions` | Spans below the confidence threshold |
| `GET /metrics` | Confidence timeline + per-category summary |
| `GET /datasets` | NaviGuard datasets in Phoenix |
| `GET /experiments` | Proposed prompt versions |

---

## Architecture

- **Agent brain** — Python on Google ADK, deployed to **Google Cloud Run**.
  Specialists are defined as ADK `LlmAgent`s; the production hot path uses
  direct Vertex AI Gemini calls for speed.
- **Dashboard** — Next.js + Tailwind, dark "mission control" theme, deployed
  to Cloud Run. Live SSE step view and self-improvement-loop visualization.
- **CLI** — Node, published as `shipsafe-naviguard` on npm (`init` / `demo` /
  `health`).
- **Gemini** — model read from config (`GEMINI_MODEL`, default
  `gemini-2.5-flash`), never hardcoded in logic. All calls on Vertex AI.
- **Secrets** — every credential (Phoenix API key, collector endpoint) lives in
  **GCP Secret Manager**. Nothing in code, nothing in `.env` at deploy time.
- **Tests** — pytest, TDD-first, covering specialists, the orchestrator, the
  Critic, and the API.

---

## Demo scenario — Hormuz Crisis

A deterministic, pre-scripted maritime crisis used to showcase the full loop
without any live API calls. At 15:00, the routing model's `crisis_avoidance`
confidence collapses to ~0.31 while standard-route decisions stay healthy
(~0.80). NaviGuard catches the category-specific drift, diagnoses a novel input
distribution, builds the dataset, proposes the corrected prompt, and the Critic
confirms — all on one screen with a full audit trail.

The shipping context is the demo. The product is universal.

---

## License

MIT — see [LICENSE](LICENSE).

---

*Part of the **ShipSafe** ecosystem — six AI agents for production operations
intelligence, built for the Google Cloud Rapid Agent Hackathon. NaviGuard is
the Arize Phoenix track submission.*
