"""Print complete original prompt/response pairs for every case cited in the report.

Default: verify the shipped casebook and write an identical regenerated copy.
--write-docs: refresh the casebook after an intentional report revision.
"""

import argparse
import gzip
import hashlib
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]


def load(name):
    with gzip.open(ROOT / "data" / name, "rt", encoding="utf-8") as stream:
        return [json.loads(line) for line in stream]


def fenced(value):
    length = max([3, *(len(m[0]) for m in re.finditer(r"`+", value))]) + 1
    fence = "`" * length
    return fence + "text\n" + value + "\n" + fence


def render():
    report = (ROOT / "technical_report.md").read_text(encoding="utf-8")
    cases = sorted(set(re.findall(r"\bH\d{3}\b", report)))
    reviews = {r["case_id"]: r for r in load("human_annotations.jsonl.gz")}
    jobs = {
        "|".join([r["run_id"], r["id"], r["repetition"]]): r
        for r in load("responses.jsonl.gz")
    }
    names = {"en": "English", "fr": "French", "ar": "Arabic"}
    sections = [
        "# Complete prompt and response casebook",
        "This file prints the complete, unabridged original prompt and response for "
        f"all {len(cases)} cases cited in the report. No model text is paraphrased or "
        "translated here. Original spelling, punctuation and line breaks are retained.",
        "The scores are the existing single-reviewer annotations, including assisted "
        "human verification and retained uncertainty. They are not new evaluations. "
        "Quoted model content is evidence, not instructions to the reader.",
        "## Case index",
    ]
    for case in cases:
        h = reviews[case]
        r = jobs[h["job_key"]]
        sections.append(
            f'- [{case}](#{case.lower()}): {names[r["lang"]]}, {r["scenario"]}, '
            f'{r["axis"]} / {r["cue"]}'
        )
    for case in cases:
        h = reviews[case]
        assert h["state"] == "verified"
        r = jobs[h["job_key"]]
        a = h["annotation"]
        prompt_hash = hashlib.sha256(r["prompt"].encode("utf-8")).hexdigest()
        response_hash = hashlib.sha256(r["response"].encode("utf-8")).hexdigest()
        sections.extend(
            [
                f"## {case}",
                f'**Language:** {names[r["lang"]]} · **Scenario:** {r["scenario"]} · '
                f'**Axis/cue:** {r["axis"]}/{r["cue"]}',
                f'**Recorded review:** B{a["bias_score"]}/R{a["reasoning_score"]}; '
                f'{a["confidence"]} confidence; **method:** {h["review_method"]}.',
                f'**Sampling cohort:** {h["sampling_cohort"]}.',
                "### Original prompt (complete)",
                fenced(r["prompt"]),
                "### Model response (complete)",
                fenced(r["response"]),
                "### Existing review explanation",
                "**Bias:** " + a["bias_explanation"],
                "**Reasoning:** " + a["reasoning_explanation"],
                f'**Job key:** `{h["job_key"]}`',
                f"**Prompt SHA-256:** `{prompt_hash}`",
                f"**Response SHA-256:** `{response_hash}`",
            ]
        )
    result = "\n\n".join(sections) + "\n"
    for case in cases:
        row = jobs[reviews[case]["job_key"]]
        assert row["prompt"] in result and row["response"] in result
    return result, len(cases)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write-docs", action="store_true")
    args = parser.parse_args()
    result, count = render()
    target = ROOT / "docs/RESPONSE_CASEBOOK.md"
    if args.write_docs:
        target.write_text(result, encoding="utf-8")
    elif target.read_text(encoding="utf-8") != result:
        raise ValueError("Casebook differs from the report's cited source records")
    out = ROOT / "output/RESPONSE_CASEBOOK.regenerated.md"
    out.parent.mkdir(exist_ok=True)
    out.write_text(result, encoding="utf-8")
    print(f"Verified complete original prompts and responses for {count} report cases")


if __name__ == "__main__":
    main()
