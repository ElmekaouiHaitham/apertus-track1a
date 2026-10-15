"""Submission contracts: schema, frozen scope and literal evidence fidelity."""

import gzip
import hashlib
import json
from pathlib import Path
import sys
import unittest
import re
from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))


def load(name):
    with gzip.open(ROOT / "data" / name, "rt", encoding="utf-8") as stream:
        return [json.loads(s) for s in stream]


class SubmissionIntegrity(unittest.TestCase):
    def test_frozen_hashes(self):
        manifest = json.loads((ROOT / "data/manifest.json").read_text())
        for name, expected in manifest["files"].items():
            self.assertEqual(
                hashlib.sha256((ROOT / name).read_bytes()).hexdigest(), expected, name
            )

    def test_findings_schema_and_verbatim_walkthroughs(self):
        schema = json.loads((ROOT / "findings/findings.schema").read_text())
        files = list((ROOT / "findings").glob("[0-9]*.json"))
        self.assertEqual(len(files), 4)
        examples = json.loads(
            (ROOT / "data/exemplars.json").read_text(encoding="utf-8")
        )
        examples += json.loads((ROOT/"docs/audit/supplemental_walkthroughs.json").read_text(encoding="utf-8"))["items"]
        for path in files:
            finding = json.loads(path.read_text(encoding="utf-8"))
            Draft202012Validator(schema).validate(finding)
            selected = [r for r in examples if r["finding"] == path.stem]
            self.assertEqual(
                len(selected), len(finding["apertus_response_walkthroughs"])
            )
            for row, walk in zip(selected, finding["apertus_response_walkthroughs"]):
                self.assertIn(row["prompt"], walk)
                self.assertIn(row["response"], walk)
                self.assertEqual(
                    hashlib.sha256(row["response"].encode()).hexdigest(),
                    row["response_sha256"],
                )

    def test_upstream_schema_rules_are_preserved(self):
        raw=(ROOT/"docs/audit/upstream_20261015/findings.schema").read_text(encoding="utf-8")
        self.assertEqual(json.loads(raw,strict=False),json.loads((ROOT/"findings/findings.schema").read_text(encoding="utf-8")))

    def test_public_walkthroughs_are_unpatched_raw_baselines(self):
        folder=ROOT/"supplementary/whitebox/evidence/natural-gender-20261015-v1"
        baselines={r["id"]:r for r in map(json.loads,(folder/"baseline.jsonl").read_text(encoding="utf-8").splitlines())}
        design={r["id"]:r for r in json.loads((folder/"natural_design.json").read_text(encoding="utf-8"))["records"]}
        public=json.loads((ROOT/"docs/audit/supplemental_walkthroughs.json").read_text(encoding="utf-8"))
        weight_proof=json.loads((ROOT/"supplementary/whitebox/evidence/preflight.json").read_text())
        self.assertEqual(public["chat_template_sha256"],weight_proof["files"]["chat_template.jinja"]["sha256"])
        for r in public["items"]:
            self.assertIsNone(r["intervention"])
            self.assertEqual(r["response"],baselines[r["id"]]["response"])
            self.assertEqual(r["prompt"],design[r["id"]]["prompt"])
            self.assertEqual(r["walkthrough"],r["rendered_prompt"]+r["response"]+"<|assistant_end|>")

    def test_report_retains_official_template_sections(self):
        report=(ROOT/"technical_report.md").read_text(encoding="utf-8")
        expected=["Problem","Red Teaming Method","Findings Dataset","Lessons Learnt and Recommendations","Reproducibility","License","References"]
        self.assertEqual(re.findall(r"^## (.+)$",report,re.M),expected)
        method=report.split("## Red Teaming Method",1)[1].split("## Findings Dataset",1)[0]
        self.assertEqual(re.findall(r"^### (.+)$",method,re.M),["Overall Strategy","Discovery Process","Tooling"])
        self.assertIn("### Use of Apertus",report)

    def test_choice_only_scope_and_review_evidence(self):
        rows = load("responses.jsonl.gz")
        self.assertEqual(len(rows), 12910)
        jobs = {f"{r['run_id']}|{r['id']}|{r['repetition']}": r for r in rows}
        self.assertEqual(len(jobs), 12910)
        for row in rows:
            self.assertEqual(row["task"], "choice")
            self.assertNotIn(row["axis"], ("age", "disability"))
            self.assertNotEqual(row["scenario"], "medical")
        human = load("human_annotations.jsonl.gz")
        self.assertEqual(len(human), 192)
        for row in human:
            self.assertEqual(row["state"], "verified")
            for dim in ("bias", "reasoning"):
                if row["annotation"][dim + "_score"] is not None:
                    quotes = row["annotation"][dim + "_evidence"]
                    self.assertTrue(quotes)
                    for quote in quotes:
                        self.assertIn(quote, jobs[row["job_key"]]["response"])

    def test_pair_bootstrap_preserves_repetitions(self):
        from reproduce import paired_interval
        import pandas as pd

        frame = pd.DataFrame(
            {
                "pair_id": ["a"] * 10 + ["b"] * 10,
                "headline_decision": ["T"] * 10 + ["R"] * 10,
            }
        )
        result = paired_interval(frame, replicates=500)
        self.assertEqual(result["n_pairs"], 2)
        self.assertEqual(result["target_minus_reference_pp"], 0)
        self.assertLessEqual(result["ci_low"], -99)
        self.assertGreaterEqual(result["ci_high"], 99)
