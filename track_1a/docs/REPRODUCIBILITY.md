# Reproduce the submitted evidence

This package contains only the active **choice** study. Its frozen data are sufficient to reproduce reported observations offline. Fresh inference is a separate operation, because hosted generations are stochastic and the checkpoint revision was not reported.

## One command for judges

From the repository root:

```sh
make run
```

The root Makefile delegates to the unchanged `track_1a/` directory. Docker builds a CPU-only Python image, runs the regression/integrity tests, regenerates and compares all 2,582 prompts, re-parses all 12,910 planned jobs, validates Clef typed outputs, re-extracts all planned self-evaluation labels and evidence tiers, and writes statistics and figures to `track_1a/output/`. Model weights, GPU access and API credentials are unnecessary for this evidence replay. Initial image/dependency downloads require internet; the analysis makes no network calls.

Allow approximately 5–15 minutes on a normal CPU, depending on hardware, and approximately 1–2 GB of RAM. This is a planning allowance, not a benchmark guarantee. The pinned Python dependencies are in `requirements.txt`; the container uses Python 3.11.13. Local validation results and the actual test environment are recorded in `docs/audit/validation.json`. Docker is not installed on the preparation workstation, so the equivalent Python entry point was tested there. The exact root `make run` has also passed from a clean GitHub checkout on Ubuntu; see the [successful Docker workflow](https://github.com/ElmekaouiHaitham/apertus-track1a/actions/runs/38825253821).

Python fallback:

```sh
python -m pip install -r track_1a/requirements.txt
python track_1a/src/run_all.py
```

## What is reconstructed

| Input | Reconstruction / validation |
|---|---|
| `prompts.csv` | Rebuilt from the original template generator, preserving full-grid IDs before choice filtering. |
| `responses.jsonl.gz` | Normalized multilingual name/block extraction; checked against every frozen decision. |
| `clef_raw.jsonl.gz` | Validate typed schemas, finite probabilities, sum-to-one and argmax; compare labels/probabilities to exported judgments. |
| `self_raw.jsonl.gz` | Latest original raw evaluation per ID, with missing outcomes retained; recover scalar scores and verify evidence tiers with the original extraction functions. |
| `human_annotations.jsonl.gz` | Validate completed status, score ranges and literal evidence against original responses. Human scores are reviewed evidence, not machine-regenerated ground truth. |
| `exemplars.json` and findings files | Full original prompts/responses; response hashes, schema and role-delimited walkthrough content checked. |

`data/manifest.json` records SHA-256 hashes. Regeneration must fail if an input changes. Recovery removes invalid literal NUL padding only when packaging the affected cloud logs; complete raw logs remain in the private local archive. It does not rewrite model words or repair semantic content. API transport secrets, account tokens and unrelated experiments are excluded.

`self_paired.csv` is checked from the two extracted conditions during reproduction. Summary cells retain planned calls, failed/missing output, unscorable judgments and evidence-only subsets. The code also exports the 144-case random audit, the controls, and the intentionally selected disagreements separately.

## Optional fresh Apertus inference

The original request settings were `apertus-v1.5-70b`, temperature `0.7`, maximum output tokens `1024`, no caller-supplied system message, and five repeats per displayed prompt. API base URL: `https://hackapertus.livemap.sh/v1`. A hosted model revision and generation seed were not supplied.

```sh
export LLM_NAME=apertus-v1.5-70b
export LLM_BASE_URL=https://hackapertus.livemap.sh/v1
export LLM_API_KEY=YOUR_KEY
cd track_1a
python src/live_replay.py --finding 01_gender_childcare --limit 3
```

Live replay makes paid/credentialed calls only when explicitly invoked. It saves fresh API responses in a new output file and does not overwrite historical evidence. A fresh response need not reproduce the same words or failure; review the complete response with `docs/rubric.md`. The walkthrough delimiter representation is reconstructed from API roles using the template convention, not a claimed capture of the provider's hidden native token stream.

## Original supporting inference

Apertus self-evaluation: temperature `0`, maximum output tokens `1536`, one repeat per authorship condition, separate fresh contexts. Exact compact rubric, schema and authorship sentences: `docs/self_prompt_bundle.json`. The original hosted runner and cloud configuration remain in the local archive; optional `src/replay_judges.py` can reconstruct selected original self-judge requests.

Clef: `Cloudflare/clef`, revision `0b331204bb13fbd2ca93a64df1956f5b55478ce5`, BF16, batch size 1, A100 80 GB. Direct typed classification with the frozen `docs/clef_questions.json`; no TypeSafe hosted API was used. Its classifier probabilities are not calibrated correctness estimates. Seventy-four calibration outputs were reused; 12,830 new classifications were computed. Full model inference is expensive and not needed for offline verification; `src/replay_judges.py` documents the optional weight-based path separately.

## Report and notebooks

`docs/report.tex` is the editable LaTeX source; `ApertusChoiceAudit_Report.pdf` is the single submission report and team-named upload. Report figures are frozen under `docs/figures/`, and matching figures are regenerated under `output/figures/`. Behavioral figures are generated by `src/figures.py` and `src/report_figures.py`; `src/whitebox_report_figure.py` adds the compact causal panel. The six-page PDF selects five figures; the detailed Markdown report and notebook retain the full broader set. Build the report from `track_1a` with `make report` (Tectonic 0.17.0, first-run TeX bundle download required). Reproduction of numbers does not require TeX.

The portable notebook under `notebooks/` explores the generated tables, controls, every language × axis × cue panel, the human audit, automated judges and authorship comparisons. It reads package-relative paths. Historical development notebooks remain in the local workspace and are excluded from the judge package.

## Completed supplementary white-box evidence

The 15 October gender/childcare supplement is under `supplementary/whitebox/`. `src/run_all.py` also runs the supplementary design tests, verifies completed evidence manifests and performs CPU-only analysis. The Docker image copies that folder, but does not install or invoke optional GPU dependencies. `supplementary/whitebox/NATURAL_RESULTS.md` reports the corrected original-format study: full early cue swaps change 16/16 fresh childcare selections, whereas the learned gender-probe-axis swaps change 0/16 despite reversing probe predictions. Qualification choices remain intact; teamwork and same-gender tie changes limit specificity. The layer map, frozen measurements, raw generations, complete casebooks and pinned source/checkpoint provenance accompany it. CPU reproduction verifies recorded results; raw activations for retraining probes remain on Modal. The earlier A/B diagnostic remains separately in `RESULTS.md`. The final six-page PDF now integrates the corrected result, methods and negative controls; detailed results remain in `NATURAL_RESULTS.md`.

Optional full inference uses a separate Modal launcher, two A100 80GB GPUs and weight access. It is not part of judge reproduction. See `supplementary/whitebox/README.md` for the exact design, settings, resource estimates and commands.

## Complete cited conversations

`docs/RESPONSE_CASEBOOK.md` prints the original prompt and complete response for every case cited in the report, with original language, job key, source hashes and existing review explanations. `src/build_casebook.py` regenerates and verifies it as part of `make run`. This is distinct from the shorter excerpts in the report and from the 18 issue walkthroughs (16 historical plus two unpatched public baselines).
