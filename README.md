# Apertus Choice Audit

**Haitham Elmekaoui | HackApertus Track 1A | final integrated submission**

Start with the [six-page report plus references](track_1a/ApertusChoiceAudit_Report.pdf), [full technical report](track_1a/technical_report.md), [behavioral casebook](track_1a/docs/RESPONSE_CASEBOOK.md), and [reproduction guide](track_1a/docs/REPRODUCIBILITY.md).

We test whether Apertus turns demographic cues into unsupported reasons to choose between people with equal supplied qualifications. The submission combines 12,904 successful English/French/Arabic behavioral responses, separate stereotyping and reasoning evaluation, completed human verification and an original-format white-box childcare supplement.

| Finding | Documented failure |
|---|---|
| [Gender and childcare](track_1a/findings/01_gender_childcare.json) | Gender becomes nurturing, empathy or invented caregiving experience. Early internal cue swaps change 16/16 fresh recommendations; changing a readable probe axis changes 0/16. |
| [Names and professionalism](track_1a/findings/02_name_professionalism.json) | Names become communication, reliability and workplace-quality claims, sometimes framed as avoiding bias. |
| [Origin and lending](track_1a/findings/03_origin_lending.json) | Birthplace or names become invented citizenship, jurisdiction and repayment-risk advantages. |
| [Religion and belonging](track_1a/findings/04_religious_belonging.json) | Faith becomes unsupported conflict risk, assumed shared values or cultural fit; equivalent activities are treated asymmetrically. |

The four issue files follow the organizer's schema and contain 18 complete conversations: 16 historical reviewed cases and two unpatched public-checkpoint baselines. Patched outputs are separately labeled. Reasoning failures are evaluated independently from expressed stereotyping; no hidden intent or actual denied opportunity is claimed.

```sh
make run
```

This is the organizer's root command. It builds the supplied CPU Docker image and verifies frozen evidence without API keys, GPUs, weights or cloud credentials. It runs 30 core/integration tests and 10 supplementary tests, reconstructs the original analyses, verifies both supplementary runs, rebuilds figures/casebooks and checks the final report/schema contracts. Two optional Torch toy-hook tests skip in the minimal CPU image; actual-run self-patch evidence remains verified.

For local Python:

```sh
python -m pip install -r track_1a/requirements.txt
python track_1a/src/run_all.py
```

See [measured validation and exact limits](track_1a/docs/FINAL_VALIDATION.md). A native Docker daemon is unavailable on the preparation workstation; Dockerfile-derived Linux-container and clean-package checks are recorded separately. The included GitHub Actions workflow runs the exact root `make run` command on Ubuntu when the private repository is uploaded; it has not been triggered here.

The report integrates the completed white-box result, methods and negative controls. Its [full supplement](track_1a/supplementary/whitebox/NATURAL_RESULTS.md) preserves actual name-plus-explanation output, fresh name families, qualification controls and incomplete specificity (2/16 teamwork and 6/8 same-gender tie changes). The [earlier A/B pilot](track_1a/supplementary/whitebox/RESULTS.md) is retained separately. Frozen replay verifies saved measurements; it does not rerun the 70B model or retrain probes from remote activation arrays. Optional paid inference is documented separately and never launched by `make run`.

| Location | Contents |
|---|---|
| `track_1a/findings/` | Four schema-valid red-teaming issues. |
| `track_1a/data/` | Frozen behavioral responses, evaluator outputs, reviews and hashes. |
| `track_1a/docs/` | Rubric, complete cases, methods, editable LaTeX, provenance and validation. |
| `track_1a/supplementary/whitebox/` | Original-format causal study, earlier pilot, frozen evidence and CPU verifiers. |
| `track_1a/notebooks/` | Executed, package-relative behavioral analysis notebook. |
| `track_1a/output/` | Regenerated results; not an input or a submission prerequisite. |

The official Track 1A README is retained in place. The report follows its section template; raw organizer files and revision fingerprints are preserved under `docs/audit/upstream_20261015/`. A literal newline in the upstream schema description was escaped without changing its validation rules.

Keep the submission PRIVATE until 1 December 2026. The organizer requires a private GitHub repository with `judgeailights` added and a report upload through its submission page. This preparation has not published or submitted anything. Code: Apache-2.0; findings/data: CDLA-Permissive-2.0; report: CC-BY-4.0.
