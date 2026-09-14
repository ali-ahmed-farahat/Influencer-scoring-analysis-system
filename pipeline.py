"""Candidate loading, anonymization, and deterministic preprocessing."""

import json
from dataclasses import asdict
from pathlib import Path
from typing import Any

from models import (
    CandidateAnalysis,
    DerivedMetrics,
    PreprocessedCandidate,
    ScoreBreakdown,
    generate_final_explanation,
)
from logging_utils import configure_logging

logger = configure_logging()

GCC_COUNTRIES = {"Kuwait", "Saudi Arabia", "United Arab Emirates", "Qatar", "Bahrain", "Oman"}
MIN_GCC_AUDIENCE_PCT = 0.45
ANONYMOUS_CANDIDATE_ID = "candidate_001"


def load_candidates(data_path: str | Path = "raw_data.json") -> list[dict[str, Any]]:
    """Load candidate records from the project dataset."""
    with Path(data_path).open(encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, list):
        raise ValueError("raw_data.json must contain a list of candidates")
    return data


def get_candidate(account_id: str, data_path: str | Path = "raw_data.json") -> dict[str, Any]:
    """Return one candidate by external identifier."""
    for c in load_candidates(data_path):
        if c.get("account_id") == account_id:
            return c
    raise ValueError(f"Unknown account_id: {account_id}")


def _anomaly_flags(candidate: dict[str, Any], ratio: float | None) -> list[str]:
    prof, perf = candidate["profile"], candidate["performance_metrics"]
    f_count, eng, comms = prof["followers_count"], perf["engagement_rate"], perf["avg_comments"]
    flags = ["source_anomaly_detected"] if perf.get("anomaly_detected") else []

    if ratio is not None and ratio > 40:
        if f_count >= 100_000 and eng < 0.01:
            flags.append("large_audience_low_engagement")
        if eng >= 0.05 and comms < 100:
            flags.append("high_engagement_low_comment_quality")
    return flags


def anonymize_candidate(candidate: dict[str, Any]) -> dict[str, Any]:
    """Strip personal identifiers while preserving content signals for LLM evaluation."""
    posts = [
        {**{k: v for k, v in p.items() if k != "post_id"}, "post_id": f"post_{i:03d}"}
        for i, p in enumerate(candidate["recent_content_signals"], start=1)
    ]
    return {
        "anonymous_id": ANONYMOUS_CANDIDATE_ID,
        "profile": {k: candidate["profile"][k] for k in ("platform", "followers_count", "category", "is_private")},
        "audience_insights": candidate["audience_insights"],
        "performance_metrics": candidate["performance_metrics"],
        "recent_content_signals": posts,
    }


def preprocess_candidate(candidate: dict[str, Any]) -> PreprocessedCandidate:
    """Calculate deterministic features and apply hard eligibility rules."""
    req_keys = {"account_id", "profile", "audience_insights", "performance_metrics", "recent_content_signals"}
    if missing := req_keys - candidate.keys():
        raise ValueError(f"Candidate missing required fields: {sorted(missing)}")

    prof, perf, posts = candidate["profile"], candidate["performance_metrics"], candidate["recent_content_signals"]
    followers = prof.get("followers_count", -1)
    if not isinstance(followers, (int, float)) or followers < 0 or not posts:
        raise ValueError("Invalid followers count or empty content signals")

    geo = candidate["audience_insights"].get("geo_distribution", {})
    gcc_pct = sum(float(geo.get(c, 0)) for c in GCC_COUNTRIES)
    avg_likes, avg_comments = perf["avg_likes"], perf["avg_comments"]

    ratio = (avg_likes / avg_comments) if avg_comments else None
    eng_rate = ((avg_likes + avg_comments) / followers) if followers else 0.0
    comm_rate = sum(bool(p.get("has_commercial_intent")) for p in posts) / len(posts)
    flags = _anomaly_flags(candidate, ratio)

    decision, reasons = None, []
    if prof.get("is_private"):
        decision, reasons = "MANUAL REVIEW", ["private_account"]
    elif gcc_pct < MIN_GCC_AUDIENCE_PCT:
        decision, reasons = "PASS", ["gcc_audience_below_45_percent"]
    elif flags:
        decision, reasons = "MANUAL REVIEW", list(flags)

    metrics = DerivedMetrics(
        gcc_audience_pct=gcc_pct,
        gcc_reachable_audience=followers * gcc_pct,
        calculated_engagement_rate=eng_rate,
        likes_to_comments_ratio=ratio,
        commercial_content_rate=comm_rate,
        content_count=len(posts),
    )

    result = PreprocessedCandidate(
        anonymous_id=ANONYMOUS_CANDIDATE_ID,
        account_id=candidate["account_id"],
        username=prof["username"],
        metrics=metrics,
        anomaly_flags=flags,
        hard_rule_decision=decision,
        hard_rule_reasons=reasons,
        scoring_payload=anonymize_candidate(candidate),
    )
    logger.info("step=preprocess account=%s gcc=%.2f hard_rule=%s", result.account_id, gcc_pct, decision or "none")
    return result


def to_jsonable(result: PreprocessedCandidate) -> dict[str, Any]:
    """Convert preprocessing output into a JSON-serializable dictionary."""
    return {
        "metadata": {"account_id": result.account_id, "username": result.username},
        "anonymous_id": result.anonymous_id,
        "derived_metrics": asdict(result.metrics),
        "anomaly_flags": result.anomaly_flags,
        "hard_rule_decision": result.hard_rule_decision,
        "hard_rule_reasons": result.hard_rule_reasons,
        "scoring_payload": result.scoring_payload,
    }


def score_candidate(
    result: PreprocessedCandidate,
    model_signals: dict[str, Any],
) -> CandidateAnalysis:
    """Aggregate deterministic and model signals into one explainable decision."""
    metrics = result.metrics
    posts = model_signals.get("post_signals", [])
    brands = model_signals.get("brand_fits", [])
    avg_intent = sum(p.get("commercial_intent_score", 0) for p in posts) / len(posts) if posts else 0
    proof_rate = sum(
        any(p.get(key) for key in ("has_call_to_action", "has_discount_code", "has_restock_signal"))
        for p in posts
    ) / len(posts) if posts else 0
    product_evidence_rate = sum(
        any(p.get(key) for key in ("has_product_review", "has_unboxing", "has_product_education"))
        for p in posts
    ) / len(posts) if posts else 0
    duration_fit_rate = sum(
        30 <= (post.get("video_length_seconds") or 0) <= 60
        for post in result.scoring_payload["recent_content_signals"]
    ) / metrics.content_count
    video_format_rate = sum(
        post.get("format") in {"reel", "video", "story"}
        for post in result.scoring_payload["recent_content_signals"]
    ) / metrics.content_count
    category = result.scoring_payload["profile"]["category"].lower()
    category_relevance = 10 if any(
        word in category for word in ("beauty", "makeup", "skincare", "fragrance", "grooming", "luxury")
    ) else 0
    known_brand_scores = [b["catalog_fit_score"] for b in brands if b.get("catalog_fit_score") is not None]
    brand_fit = (sum(known_brand_scores) / len(known_brand_scores) / 100 * 15) if known_brand_scores else 0

    breakdown = ScoreBreakdown(
        audience_commercial_viability=min(metrics.gcc_audience_pct / 0.8, 1) * 15
        + min(metrics.gcc_reachable_audience / 200_000, 1) * 8
        + min(metrics.calculated_engagement_rate / 0.08, 1) * 7,
        commercialization_and_intent=metrics.commercial_content_rate * 10
        + avg_intent / 100 * 8
        + proof_rate * 7,
        category_and_brand_alignment=category_relevance + brand_fit,
        content_quality_and_consistency=product_evidence_rate * 8
        + duration_fit_rate * 5
        + video_format_rate * 4,
    )
    final_score = round(sum(breakdown.model_dump().values()), 2)
    model_unavailable = any(
        signal.get("source", "").startswith("fallback")
        for signal in [*posts, *brands]
    )
    decision = result.hard_rule_decision or (
        "MANUAL REVIEW"
        if model_unavailable
        else "ONBOARD" if final_score >= 75 else "HOLD" if final_score >= 60 else "PASS"
    )
    positive = []
    negative = []
    if metrics.gcc_audience_pct >= 0.6:
        positive.append(f"Strong GCC audience concentration ({metrics.gcc_audience_pct:.0%}).")
    if metrics.commercial_content_rate >= 0.4:
        positive.append(f"Commercial content appears in {metrics.commercial_content_rate:.0%} of recent posts.")
    if metrics.likes_to_comments_ratio is not None and metrics.likes_to_comments_ratio <= 10:
        positive.append("Likes-to-comments ratio indicates active interaction.")
    if result.anomaly_flags:
        negative.extend(f"Anomaly flag: {flag}." for flag in result.anomaly_flags)
    if metrics.commercial_content_rate < 0.2:
        negative.append("Limited evidence of commercial content.")
    if not known_brand_scores:
        negative.append("Brand fit was unavailable or used fallback data.")
    next_action = {
        "ONBOARD": "Proceed to onboarding discussion.",
        "HOLD": "Run a controlled pilot campaign before onboarding.",
        "PASS": "Do not allocate onboarding capacity.",
        "MANUAL REVIEW": "Review account visibility and anomaly evidence manually.",
    }[decision]
    limitations = [
        "Verified collaboration rate is unavailable because the mock data has no sponsorship labels.",
        "Post-performance volatility is unavailable because post-level engagement history is missing.",
    ]
    if model_unavailable:
        limitations.append("One or more model signals used labelled fallback data.")
    analysis = CandidateAnalysis(
        metadata={"account_id": result.account_id, "username": result.username},
        anonymous_id=result.anonymous_id,
        derived_metrics=asdict(metrics),
        anomaly_flags=result.anomaly_flags,
        hard_rule_decision=result.hard_rule_decision,
        hard_rule_reasons=result.hard_rule_reasons,
        model_signals=model_signals,
        score_breakdown=breakdown,
        final_score=final_score,
        decision=decision,
        positive_signals=positive,
        negative_signals=negative,
        next_action=next_action,
        limitations=limitations,
    )
    explanation = generate_final_explanation(analysis)
    analysis.final_explanation = explanation.summary
    analysis.trade_offs = explanation.trade_offs
    analysis.explanation_source = explanation.source
    if explanation.error:
        analysis.limitations.append(explanation.error)
    logger.info("step=scoring account=%s score=%.2f decision=%s", result.account_id, final_score, decision.replace(" ", "_"))
    return analysis


def write_reports(analysis: CandidateAnalysis, output_dir: str | Path = "outputs") -> tuple[Path, Path]:
    """Write machine-readable JSON and readable Markdown reports."""
    directory = Path(output_dir)
    directory.mkdir(parents=True, exist_ok=True)
    account_id = analysis.metadata["account_id"]
    json_path, markdown_path = directory / f"{account_id}.json", directory / f"{account_id}.md"
    json_path.write_text(analysis.model_dump_json(indent=2), encoding="utf-8")
    rows = "\n".join(
        f"| {name.replace('_', ' ').title()} | {value:.2f} |"
        for name, value in analysis.score_breakdown.model_dump().items()
    )
    markdown_path.write_text(
        f"# Boutiqaat Candidate Report\n\n"
        f"**Candidate:** {analysis.metadata['username']}  \n"
        f"**Decision:** **{analysis.decision}**  \n"
        f"**Score:** **{analysis.final_score}/100**\n\n"
        f"## Score breakdown\n\n| Dimension | Points |\n|---|---:|\n{rows}\n\n"
        f"## Positive signals\n\n" + "\n".join(f"- {item}" for item in analysis.positive_signals) + "\n\n"
        f"## Negative signals\n\n" + "\n".join(f"- {item}" for item in analysis.negative_signals) + "\n\n"
        f"## Next action\n\n{analysis.next_action}\n\n"
        f"## Limitations\n\n" + "\n".join(f"- {item}" for item in analysis.limitations) + "\n",
        encoding="utf-8",
    )
    logger.info("step=reports account=%s json=%s markdown=%s", account_id, json_path, markdown_path)
    return json_path, markdown_path
