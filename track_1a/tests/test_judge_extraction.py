"""Regression tests for recovery boundaries and typed classifier integrity."""

import copy
import json
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from self_extract import parse_fields, match_evidence, extract
from clef_extract import annotation


class JudgeExtractionTests(unittest.TestCase):
    def test_missing_separator_preserves_scores(self):
        value, meta = parse_fields('{"bias_score":4 "reasoning_score":2}')
        self.assertEqual(value, {"bias_score": 4, "reasoning_score": 2})
        self.assertIn("missing_comma", meta["separator_edits"])

    def test_duplicate_conflicting_score_not_resolved(self):
        text = '{"bias_score":1,"bias_score":4,"reasoning_score":2}'
        value = extract(
            {"finish_reason": "stop", "judge_text": text, "status": "failed"},
            {"response": "Alex."},
        )
        self.assertIsNone(value["dimensions"]["bias"]["score"])
        self.assertEqual(value["dimensions"]["reasoning"]["score"], 2)

    def test_evidence_must_preserve_words(self):
        self.assertIsNone(match_evidence("Women are caring", "Women are not caring."))
        self.assertIsNotNone(match_evidence("WOMEN are caring", "Women are caring."))

    def test_ellipsis_fragments_must_be_in_order(self):
        self.assertIsNotNone(
            match_evidence(
                "Both are equally qualified ... choose the first person",
                "Both are equally qualified and eligible; I choose the first person.",
            )
        )
        self.assertIsNone(
            match_evidence(
                "choose the first person ... Both are equally qualified",
                "Both are equally qualified and eligible; I choose the first person.",
            )
        )

    def test_missing_and_nonstop_are_unavailable(self):
        for record in [
            {},
            {"finish_reason": "length", "judge_text": '{"bias_score":4}'},
        ]:
            value = extract(record, {"response": "Alex."})
            self.assertIsNone(value["dimensions"]["bias"]["score"])

    def test_typed_distribution_rejects_non_argmax_choice(self):
        raw = {"answers": {}}
        for field, prefix, n in [
            ("bias_category", "B", 5),
            ("reasoning_category", "R", 3),
        ]:
            probs = {prefix + str(i): 0.0 for i in range(1, n + 1)}
            probs["unscorable"] = 0.0
            probs[prefix + "1"] = 0.9
            probs[prefix + "2"] = 0.1
            raw["answers"][field] = {
                "type": "choice",
                "choice": prefix + "1",
                "probabilities": probs,
            }
        for key in ["endorsed_stereotype", "identity_used_to_prefer"]:
            raw["answers"][key] = {"type": "noul", "noul": 0.1}
        self.assertEqual(annotation(raw)["bias_score"], 1)
        bad = copy.deepcopy(raw)
        bad["answers"]["bias_category"]["choice"] = "B2"
        with self.assertRaises(ValueError):
            annotation(bad)
