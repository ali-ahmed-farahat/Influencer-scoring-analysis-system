"""Typed containers and model adapters for Step 4."""

import json
import os
from dataclasses import dataclass, field
from typing import Any
from google import genai
from google.genai import types
from pydantic import BaseModel, Field

from logging_utils import configure_logging

logger = configure_logging()

BOUTIQAAT_CONTEXT = """
Boutiqaat is a GCC-focused e-commerce platform. Prioritize GCC audience relevance,
beauty/fashion/lifestyle product alignment, commercial intent, product demonstration,
trustworthy engagement, and suitability for measurable campaigns. A brand tag is not
proof of sponsorship.
"""


@dataclass(frozen=True)
class DerivedMetrics:
    gcc_audience_pct: float
    gcc_reachable_audience: float
    calculated_engagement_rate: float
    likes_to_comments_ratio: float | None
    commercial_content_rate: float
    content_count: int


@dataclass(frozen=True)
class PreprocessedCandidate:
    anonymous_id: str
    account_id: str
    username: str
    metrics: DerivedMetrics
    anomaly_flags: list[str] = field(default_factory=list)
    hard_rule_decision: str | None = None
    hard_rule_reasons: list[str] = field(default_factory=list)
    scoring_payload: dict[str, Any] = field(default_factory=dict)


class PostSignals(BaseModel):
    commercial_intent_score: int = Field(ge=0, le=100)
    has_call_to_action: bool
    has_discount_code: bool
    has_restock_signal: bool
    has_product_review: bool
    has_unboxing: bool
    has_product_education: bool
    sales_framing: str
    evidence: list[str] = Field(default_factory=list)
    confidence: float = Field(ge=0, le=1)
    source: str = "llm"
    error: str | None = None


class BrandFit(BaseModel):
    brand: str
    brand_category: str
    prestige_tier: str
    catalog_fit_score: float | None = Field(default=None, ge=0, le=100)
    catalog_fit_reason: str
    confidence: float = Field(ge=0, le=1)
    source: str = "gemini"
    error: str | None = None


class FinalExplanation(BaseModel):
    summary: str
    trade_offs: list[str] = Field(default_factory=list)
    recommended_next_action: str
    source: str = "gemini-3.6-flash"
    error: str | None = None


class ScoreBreakdown(BaseModel):
    audience_commercial_viability: float = Field(ge=0, le=30)
    commercialization_and_intent: float = Field(ge=0, le=25)
    category_and_brand_alignment: float = Field(ge=0, le=25)
    content_quality_and_consistency: float = Field(ge=0, le=20)


class CandidateAnalysis(BaseModel):
    metadata: dict[str, str]
    anonymous_id: str
    derived_metrics: dict[str, Any]
    anomaly_flags: list[str]
    hard_rule_decision: str | None
    hard_rule_reasons: list[str]
    model_signals: dict[str, Any]
    score_breakdown: ScoreBreakdown
    final_score: float
    decision: str
    positive_signals: list[str]
    negative_signals: list[str]
    next_action: str
    limitations: list[str]
    final_explanation: str = ""
    trade_offs: list[str] = Field(default_factory=list)
    explanation_source: str = "pending"


def _clean_json(text: str) -> Any:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
    return json.loads(cleaned)


_qwen = None
_gemini_client = None


def run_qwen(prompt: str) -> tuple[Any | None, str | None]:
    global _qwen
    if os.getenv("QWEN_LOCAL_ENABLED", "false").lower() != "true":
        return None, "Qwen local inference is disabled"
    try:
        if _qwen is None:
            from transformers import AutoModelForCausalLM, AutoTokenizer
            name = os.getenv("QWEN_MODEL", "Qwen/Qwen2.5-14B-Instruct")
            _qwen = (
                AutoModelForCausalLM.from_pretrained(name, torch_dtype="auto", device_map="auto"),
                AutoTokenizer.from_pretrained(name),
            )
        model, tokenizer = _qwen
        inputs = tokenizer.apply_chat_template(
            [{"role": "user", "content": prompt}],
            add_generation_prompt=True,
            tokenize=True,
            return_dict=True,
            return_tensors="pt",
        ).to(model.device)
        out = model.generate(**inputs, max_new_tokens=400, do_sample=False)
        return _clean_json(tokenizer.decode(out[0][inputs["input_ids"].shape[-1]:], skip_special_tokens=True)), None
    except Exception as e:
        return None, str(e)


def run_gemini(
    prompt: str,
    schema: Any,
    model: str | None = None,
) -> tuple[Any | None, str | None]:
    global _gemini_client
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        return None, "GEMINI_API_KEY not set"
    try:
        model_name = model or os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite")
        logger.info("step=gemini_start model=%s", model_name)
        if _gemini_client is None:
            _gemini_client = genai.Client(api_key=api_key)
        chat = _gemini_client.chats.create(
            model=model_name,
            config=types.GenerateContentConfig(
                temperature=0,
                response_mime_type="application/json",
                response_schema=schema,
            ),
        )
        res = chat.send_message(prompt)
        logger.info("step=gemini_done model=%s", model_name)
        return _clean_json(res.text), None
    except Exception as e:
        logger.info("step=gemini_error error=%s", type(e).__name__)
        return None, str(e)


def extract_post_signals(post: dict[str, Any]) -> PostSignals:
    prompt = (
        f"{BOUTIQAAT_CONTEXT}\n"
        "Analyze this creator post for e-commerce suitability. Do not infer sponsorship merely from a brand tag.\n"
        f"Post:\n{json.dumps(post, ensure_ascii=False)}"
    )
    if os.getenv("QWEN_LOCAL_ENABLED", "false").lower() == "true":
        data, err = run_qwen(prompt)
        source = "qwen2.5-14b-transformers"
    else:
        data, err = run_gemini(prompt, PostSignals)
        source = "gemini-3.5-flash-lite"

    if data:
        try:
            return PostSignals.model_validate({**data, "source": source})
        except Exception as e:
            err = f"Validation error: {e}"

    comm = bool(post.get("has_commercial_intent"))
    return PostSignals(
        commercial_intent_score=70 if comm else 0,
        has_call_to_action=False,
        has_discount_code=False,
        has_restock_signal=False,
        has_product_review=False,
        has_unboxing=False,
        has_product_education=False,
        sales_framing="commercial" if comm else "none",
        evidence=["Fallback mock used."],
        confidence=0.5 if comm else 0.8,
        source="fallback_mock_field",
        error=err,
    )


def classify_brands(brands: list[str], creator_category: str) -> list[BrandFit]:
    if not brands:
        return []
    prompt = (
        f"{BOUTIQAAT_CONTEXT}\n"
        f"Classify these brands for a Boutiqaat creator in category: {creator_category}. "
        "Assess category, prestige tier, and fit. A tag is not proof of a paid deal.\n"
        f"Brands: {json.dumps(brands, ensure_ascii=False)}"
    )
    data, err = run_gemini(prompt, list[BrandFit])
    if isinstance(data, list):
        try:
            return [
                BrandFit.model_validate({**brand, "source": "gemini-3.5-flash-lite"})
                for brand in data
            ]
        except Exception as e:
            err = f"Validation error: {e}"

    return [
        BrandFit(
            brand=b,
            brand_category="unknown",
            prestige_tier="unknown",
            catalog_fit_reason="Brand verification fallback.",
            confidence=0.0,
            source="fallback_unavailable",
            error=err,
        )
        for b in brands
    ]


def extract_candidate_signals(payload: dict[str, Any]) -> dict[str, Any]:
    posts = payload["recent_content_signals"]
    brands = sorted({b for p in posts for b in p.get("brands_tagged", [])})
    signals = {
        "anonymous_id": payload["anonymous_id"],
        "post_signals": [extract_post_signals(p).model_dump() for p in posts],
        "brand_fits": [f.model_dump() for f in classify_brands(brands, payload["profile"]["category"])],
    }
    logger.info("step=model_extraction_done posts=%d brands=%d", len(posts), len(brands))
    return signals


def generate_final_explanation(analysis: CandidateAnalysis) -> FinalExplanation:
    """Explain the deterministic result without changing its score or decision."""
    evidence = analysis.model_dump(
        include={
            "anonymous_id",
            "derived_metrics",
            "anomaly_flags",
            "hard_rule_decision",
            "hard_rule_reasons",
            "score_breakdown",
            "final_score",
            "decision",
            "positive_signals",
            "negative_signals",
            "next_action",
            "limitations",
        }
    )
    prompt = (
        f"{BOUTIQAAT_CONTEXT}\n"
        "Explain this deterministic Boutiqaat candidate decision for a non-technical manager. "
        "Do not change the score or decision. Mention trade-offs and limitations. "
        "Return a concise summary, a trade_offs list, and recommended_next_action.\n"
        f"Evidence:\n{json.dumps(evidence, ensure_ascii=False)}"
    )
    data, error = run_gemini(
        prompt,
        FinalExplanation,
        model=os.getenv("GEMINI_REASONING_MODEL", "gemini-3.6-flash"),
    )
    if data:
        try:
            return FinalExplanation.model_validate({**data, "source": "gemini-3.6-flash"})
        except Exception as validation_error:
            error = f"Validation error: {validation_error}"
    return FinalExplanation(
        summary=f"Decision: {analysis.decision} at {analysis.final_score}/100.",
        trade_offs=analysis.negative_signals,
        recommended_next_action=analysis.next_action,
        source="fallback_template",
        error=error,
    )
