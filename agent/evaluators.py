"""NaviGuard custom evaluator using Gemini via LiteLLM.

COMPLIANCE: Always LLM(provider="litellm", model="gemini/gemini-1.5-pro").
NEVER LLM(provider="openai", ...) — rules violation.
"""

from __future__ import annotations

from phoenix.evals import LLMEvaluator, llm_classify

NAVIGUARD_REGRESSION_EVALUATOR_TEMPLATE = """You are an expert evaluator judging whether NaviGuard correctly identified an AI quality regression.

CORRECT — the verdict:
- Correctly flags confidence drops below the configured threshold
- Detects category-specific drift even when overall accuracy is stable
- Provides evidence (specific trace IDs, confidence deltas) the operator can verify

INCORRECT — the verdict contains any of:
- Missing category-specific regressions visible in the trace data
- Hallucinated evidence (referenced trace IDs that don't exist)
- Confidence score that contradicts the evidence presented

[BEGIN DATA]
[Recent trace summary]: {input}
[NaviGuard verdict]: {output}
[END DATA]

Is the verdict correct or incorrect?
"""

NAVIGUARD_ROOT_CAUSE_EVALUATOR_TEMPLATE = """You are an expert evaluator judging whether NaviGuard's root cause analysis is valid.

CORRECT — the analysis:
- Identifies a specific, plausible root cause tied to evidence in traces
- Evidence references trace IDs that can be verified
- Recommendation is actionable and specific to the failure pattern

INCORRECT — the analysis contains any of:
- Vague root cause not tied to specific trace evidence
- Hallucinated trace/span IDs
- Generic recommendation that doesn't address the specific pattern

[BEGIN DATA]
[Regression report]: {input}
[Root cause analysis]: {output}
[END DATA]

Is the analysis correct or incorrect?
"""


def build_gemini_llm():
    """Build LiteLLM-backed Gemini judge. NEVER OpenAI."""
    from phoenix.evals import LiteLLMModel

    return LiteLLMModel(model="gemini/gemini-1.5-pro")


def build_regression_evaluator() -> LLMEvaluator:
    return LLMEvaluator(
        template=NAVIGUARD_REGRESSION_EVALUATOR_TEMPLATE,
        model=build_gemini_llm(),
        rails=["CORRECT", "INCORRECT"],
        provide_explanation=True,
    )


def build_root_cause_evaluator() -> LLMEvaluator:
    return LLMEvaluator(
        template=NAVIGUARD_ROOT_CAUSE_EVALUATOR_TEMPLATE,
        model=build_gemini_llm(),
        rails=["CORRECT", "INCORRECT"],
        provide_explanation=True,
    )


def run_regression_evaluation(traces_df, verdicts_df):
    """Run Gemini-based regression eval over a Phoenix dataset."""
    model = build_gemini_llm()
    return llm_classify(
        dataframe=traces_df,
        model=model,
        template=NAVIGUARD_REGRESSION_EVALUATOR_TEMPLATE,
        rails=["CORRECT", "INCORRECT"],
        provide_explanation=True,
    )
