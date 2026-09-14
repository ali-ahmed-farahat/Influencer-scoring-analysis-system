import copy
import unittest

from models import classify_brands, extract_candidate_signals, extract_post_signals
from pipeline import get_candidate, preprocess_candidate, score_candidate, write_reports


class PipelinePreprocessingTests(unittest.TestCase):
    def test_gcc_and_reachable_audience(self):
        result = preprocess_candidate(get_candidate("HQ-110-HIGH-CONVERSION"))

        self.assertAlmostEqual(result.metrics.gcc_audience_pct, 0.92)
        self.assertAlmostEqual(result.metrics.gcc_reachable_audience, 170_200)

    def test_low_gcc_candidate_is_passed(self):
        result = preprocess_candidate(get_candidate("HQ-102-GL"))

        self.assertEqual(result.hard_rule_decision, "PASS")
        self.assertIn("gcc_audience_below_45_percent", result.hard_rule_reasons)

    def test_anomaly_candidate_requires_manual_review(self):
        result = preprocess_candidate(get_candidate("HQ-109-POD-SUSPECT"))

        self.assertEqual(result.hard_rule_decision, "MANUAL REVIEW")
        self.assertIn("source_anomaly_detected", result.anomaly_flags)

    def test_identity_does_not_change_features_or_decision(self):
        candidate = get_candidate("HQ-110-HIGH-CONVERSION")
        renamed_candidate = copy.deepcopy(candidate)
        renamed_candidate["account_id"] = "arbitrary-label"
        renamed_candidate["profile"]["username"] = "arbitrary-username"

        original = preprocess_candidate(candidate)
        renamed = preprocess_candidate(renamed_candidate)

        self.assertEqual(original.metrics, renamed.metrics)
        self.assertEqual(original.anomaly_flags, renamed.anomaly_flags)
        self.assertEqual(original.hard_rule_decision, renamed.hard_rule_decision)
        self.assertEqual(
            original.scoring_payload["anonymous_id"],
            renamed.scoring_payload["anonymous_id"],
        )
        self.assertNotIn(
            "HQ-110",
            repr(original.scoring_payload),
        )

    def test_post_extraction_has_structured_fallback_without_qwen(self):
        post = get_candidate("HQ-110-HIGH-CONVERSION")["recent_content_signals"][0]
        result = extract_post_signals(post)

        self.assertEqual(result.source, "fallback_mock_field")
        self.assertTrue(result.commercial_intent_score > 0)

    def test_brand_fallback_is_explicit_without_gemini(self):
        result = classify_brands(["Unknown Brand"], "Beauty")

        self.assertEqual(result[0].source, "fallback_unavailable")
        self.assertIsNone(result[0].catalog_fit_score)

    def test_candidate_extraction_uses_anonymous_payload(self):
        candidate = get_candidate("HQ-110-HIGH-CONVERSION")
        payload = preprocess_candidate(candidate).scoring_payload
        result = extract_candidate_signals(payload)

        self.assertEqual(result["anonymous_id"], "candidate_001")
        self.assertNotIn("HQ-110", repr(result))

    def test_scoring_and_reports_are_generated(self):
        import tempfile

        result = preprocess_candidate(get_candidate("HQ-110-HIGH-CONVERSION"))
        analysis = score_candidate(result, {"post_signals": [], "brand_fits": []})

        self.assertIn(analysis.decision, {"ONBOARD", "HOLD", "PASS", "MANUAL REVIEW"})
        self.assertTrue(analysis.final_explanation)
        with tempfile.TemporaryDirectory() as output_dir:
            json_path, markdown_path = write_reports(analysis, output_dir)
            self.assertTrue(json_path.exists())
            self.assertTrue(markdown_path.exists())


if __name__ == "__main__":
    unittest.main()
