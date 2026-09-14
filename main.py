"""CLI for the first deterministic preprocessing stage."""

import argparse
import json

from logging_utils import configure_logging
from models import extract_candidate_signals
from pipeline import get_candidate, preprocess_candidate, score_candidate, to_jsonable, write_reports

try:
    from dotenv import load_dotenv
except ImportError:
    load_dotenv = None


if load_dotenv is not None:
    load_dotenv()
logger = configure_logging()


DEFAULT_ACCOUNT_ID = "HQ-110-HIGH-CONVERSION"


def main() -> None:
    parser = argparse.ArgumentParser(description="Preprocess one Boutiqaat candidate")
    parser.add_argument("--account-id", default=DEFAULT_ACCOUNT_ID)
    parser.add_argument(
        "--with-models",
        action="store_true",
        help="Run Step 4 model extraction or its clearly labelled fallback.",
    )
    parser.add_argument("--output-dir", default="outputs")
    args = parser.parse_args()

    candidate = get_candidate(args.account_id)
    logger.info("step=cli_start account=%s models=%s", args.account_id, args.with_models)
    result = preprocess_candidate(candidate)
    output = to_jsonable(result)
    if args.with_models:
        model_signals = extract_candidate_signals(
            result.scoring_payload
        )
        analysis = score_candidate(result, model_signals)
        write_reports(analysis, args.output_dir)
        output = analysis.model_dump()
        logger.info("step=cli_done account=%s score=%.2f decision=%s", args.account_id, analysis.final_score, analysis.decision.replace(" ", "_"))
    print(json.dumps(output, indent=2))


if __name__ == "__main__":
    main()
