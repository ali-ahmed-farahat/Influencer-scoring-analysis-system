"""Minimal browser interface for candidate analysis."""

from pathlib import Path

from flask import Flask, jsonify, render_template

from logging_utils import configure_logging
from models import extract_candidate_signals
from pipeline import (
    get_candidate,
    load_candidates,
    preprocess_candidate,
    score_candidate,
    write_reports,
)

try:
    from dotenv import load_dotenv
except ImportError:
    load_dotenv = None


app = Flask(__name__)
OUTPUT_DIR = Path("outputs")
logger = configure_logging()


@app.get("/")
def index():
    logger.info("step=index")
    return render_template("index.html", candidates=load_candidates(), analysis=None)


@app.get("/analyze/<account_id>")
def analyze(account_id: str):
    logger.info("step=analyze_start account=%s", account_id)
    try:
        candidate = get_candidate(account_id)
    except ValueError as error:
        logger.info("step=analyze_error account=%s error=unknown_account", account_id)
        return render_template(
            "index.html",
            candidates=load_candidates(),
            analysis=None,
            error=str(error),
        ), 404

    preprocessed = preprocess_candidate(candidate)
    signals = extract_candidate_signals(preprocessed.scoring_payload)
    analysis = score_candidate(preprocessed, signals)
    write_reports(analysis, OUTPUT_DIR)
    logger.info(
        "step=analyze_done account=%s score=%.2f decision=%s explanation=%s",
        account_id,
        analysis.final_score,
        analysis.decision.replace(" ", "_"),
        analysis.explanation_source,
    )
    return render_template(
        "index.html",
        candidates=load_candidates(),
        analysis=analysis,
        error=None,
    )


@app.get("/health")
def health():
    logger.info("step=health")
    return jsonify(status="ok")


if __name__ == "__main__":
    if load_dotenv is not None:
        load_dotenv()
    app.run(debug=False, use_reloader=False)
