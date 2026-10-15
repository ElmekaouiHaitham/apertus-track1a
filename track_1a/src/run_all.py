"""Judge entry point: validate, regenerate prompts, analyze and export findings."""

import subprocess
import sys
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    # Findings and data are frozen inputs; regeneration is checked in tests.
    commands = [
        ["-m", "unittest", "discover", "-s", "tests"],
        ["src/build_findings.py", "--check"],
        ["src/build_prompts.py"],
        ["src/build_casebook.py"],
        ["src/reproduce.py"],
    ]
    supplementary_tests = ROOT / "supplementary/whitebox/tests"
    if supplementary_tests.exists():
        commands.insert(1,["-m", "unittest", "discover", "-s", "supplementary/whitebox/tests"])
    # Completed supplementary evidence is also verified on CPU. GPU inference
    # and optional Torch/Transformers dependencies never enter this workflow.
    evidence = ROOT / "supplementary/whitebox/evidence"
    for manifest in sorted(evidence.glob("*/manifest.json")):
        status = manifest.parent / "status.json"
        if status.exists() and json.loads(status.read_text())["status"] == "completed":
            analyzer = "natural_analyze.py" if (manifest.parent / "natural_design.json").exists() else "analyze.py"
            commands.append(["supplementary/whitebox/" + analyzer, str(manifest.parent)])
    commands.extend([["src/whitebox_report_figure.py"],["src/verify_submission.py"]])
    for args in commands:
        subprocess.run([sys.executable, *args], cwd=ROOT, check=True)
    print("Completed offline evidence reproduction. No live requests were made.")


if __name__ == "__main__":
    main()
