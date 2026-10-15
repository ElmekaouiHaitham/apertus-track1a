# Archived protocol: earlier A/B diagnostic

This protocol describes the earlier experiment. The corrected primary study preserves name-and-justification answers; start with [README.md](README.md) and [NATURAL_PROTOCOL.md](NATURAL_PROTOCOL.md).

Prepared 15 October 2026. **A protocol and implementation are not experimental results.** Check `evidence/` for completed run status before making any internal-model claim.

The completed experiment is documented in [RESULTS.md](RESULTS.md), including the failure to improve original-style answers and the complete before/after evidence.

The main study already supplies the behavioral finding. This supplement asks two narrower questions: is the gender assignment linearly readable before the answer, and which layer/site interventions change the model's preference between otherwise matched candidates? It also tests whether a small intervention changes free answers and retains sensitivity to actual childcare qualifications.

## How this relates to the completed project

The submitted study tests hosted `apertus-v1.5-70b`: 2,582 displayed choice prompts, 1,291 base pairs, five calls per prompt, 12,910 planned calls and 12,904 successful responses. It covers English, French and Arabic; four identity axes; name, explicit and embedded cues; and nine choice contexts. Gender–dating, medical, age and disability cases are outside the active scope. Its four findings are caregiving stereotypes, name-based professionalism, origin-based lending risk and religious belonging/conflict assumptions.

In the gender–childcare name cells, female-coded selections are 39/40 English, 34/40 French and 34/40 Arabic; explicit-gender cells are 20/20, 18/20 and 14/20. The name cells have only four base pairs per language; explicit cells have two. Repetitions and display orders are related observations. The direct stereotype language in H103, H072 and H064 matters more than a preference count alone. The father/mother-of-two cue is analyzed separately because parenting supplies activity/history: mother selections are 19/20 English, 10/20 French and 14/20 Arabic. H005 is a reasoning-error boundary example, not a canonical B4 stereotype.

The core pipeline is already complete:

| Code/evidence | What it does and why it matters here |
|---|---|
| `docs/audit/original_dataset_builder.py`, `src/build_prompts.py` | Rebuild the historical grid before filtering to retain IDs; generate matched profiles, order/name swaps and controls. Reuse its wording and all 48 original gender–childcare prompts as transfer checks. |
| `data/responses.jsonl.gz`, `data/manifest.json` | Preserve all planned jobs and frozen evidence hashes. A new model run must never overwrite these. |
| `src/choice_parser.py` | Unicode-aware multilingual extraction with name/slot resolution, negation, conditionals, joint choices, refusal and uncertainty. Reuse for original-style answer review; A/B diagnostic logits need a separate measurement. |
| `docs/rubric.md`, `docs/METHODOLOGY.md` | Separate B1–B5 expressed identity content from R1–R3 grounding. No internal label should be called a B4 label merely because it predicts a gender or a choice. |
| `src/clef_extract.py`, `src/self_extract*.py` | Validate typed classifier outputs and recover self-judge labels/evidence without rewriting raw model content. Do not rerun either expensive judge over a new large corpus today. |
| `src/reproduce.py`, `src/figures.py`, `src/report_figures.py` | Recompute decisions, paired uncertainty, judge distributions, human agreement and authorship comparisons from frozen evidence. They preserve N/U/E and cluster by base pair. |
| `data/human_annotations.jsonl.gz`, audit records | 192 completed single-reviewer records, including 175 human-verified AI drafts and 66 retained medium-confidence adjudication flags. Useful reviewed evidence, not an independently blinded gold set. |
| `src/build_findings.py`, `src/build_casebook.py`, tests | Four schema-valid issues, verbatim case traces and 27 existing regression/integrity checks. Keep these contracts intact. |
| `Makefile`, `Dockerfile`, `src/run_all.py` | CPU-only offline evidence reproduction. Optional GPU inference must not become a prerequisite for judges. |

The authorship comparison is a small/null effect, not evidence of self-exoneration. Nothing in the original responses establishes hidden intent or a specific internal mechanism. The hosted checkpoint revision and provider-added system text were unavailable; even a public 70B experiment is a **new, pinned-checkpoint replication and mechanistic supplement**, not an exact reconstruction of that hosted execution.

## Target and compute

Use `swiss-ai/Apertus-v1.5-70B` revision `94888dd0db53f674b4c5304c1b726a7783d21393`, BF16, no quantization, text only, thinking disabled, native chat template, no caller system message. The release has 80 decoder blocks with width 8,192. Use the model card's Transformers fork, pinned at `3797303dda74844e3d1f8977ff5518bb91f818b4`; stock Llama loading is inappropriate.

The existing Modal volume `apertus-v1-5-70b-weights` contains about 144.6 GB of checkpoint files. Local checks found matching current config and tensor index. CPU preflight verifies the tokenizer/template and hashes every weight file against the pinned release before GPU allocation. Mount weights read-only and write results to a separate volume.

Two A100 80GB GPUs provide room for the unquantized model and short contexts. At the listed base rate of $0.000694 per GPU-second, GPU time is about **$5/hour**. A single 90-minute job is about **$7.50 in GPU charges**, plus CPU/memory, startup, build and any applicable storage charges. This is a planning estimate, not a measured bill or account-wide spending cap. The launcher uses one container, zero retries, a 90-minute function timeout and an internal stop at 85 minutes; it does not automatically launch another GPU run. Reserve most of the $30 for troubleshooting and stop if loading would require CPU/disk offload. A smoke job is optional and has the same timeout bound; each invocation has its own cost.

Official references: [Modal pricing](https://modal.com/pricing), [GPU configuration](https://modal.com/docs/guide/gpu), [Apertus model card/loading instructions](https://huggingface.co/swiss-ai/Apertus-v1.5-70B).

## Frozen design: 168 prompts, with no large new survey

`design.json` records complete prompts, splits, hashes, source IDs, gender assignments, names and counterfactual donors. It is deterministic and generated before model inference.

| Subset | Size | Purpose |
|---|---:|---|
| New English explicit-gender childcare | 48 | 12 name families × 2 name orders × 2 gender assignments. Six train families (24 prompts), two validation (8), four test (16). |
| Matched teamwork context | 48 | Same people/profiles, different question; tests task specificity. |
| Actual childcare qualifications | 16 | Held-out names; either the woman or the man has first aid, five years of babysitting and references. Both skill directions and positions occur. |
| Same-gender childcare | 8 | Held-out names; both men or both women. Tests nonspecific name/position changes. |
| Original multilingual childcare | 48 | All original gender–childcare prompts: 8 name, 4 explicit and 4 embedded per language. Transfer only; never train or select interventions on these. |

The new stimuli use the original English profile and question. New identifiers are not presumed perfectly gender-neutral. Both gender assignments for each identifier pair isolate the **stated gender contrast conditional on those names**. All orders, assignments and contexts of a name family stay in one split. There is only one profile template: held-out names are not held-out templates, and this small study cannot establish broad generalization.

The diagnostic changes the response instruction to localized “A or B only”; Arabic display labels become ASCII A/B. Preserve every original-style prompt alongside it. This is an altered measurement task and its behavior must be distinguished from the main study's name-plus-justification task.

## Measurements and interventions

1. **Baseline and integrity.** Record next-token `logit(A)-logit(B)`, both token probabilities, total A/B mass, the actual top token and whether it is A/B. Verify tokenization at the native continuation boundary; do not assume a multi-token name is a single token. A sign of the A/B margin is a conditional preference proxy, not an observed choice when the model's top token is something else. Save prompt token IDs/positions, finite-value checks, dtype, versions, device map and raw activations. A self patch must preserve the A/B statistics; a final-block donor patch is an output-copy positive control.

2. **Linear probes.** On each post-block final-prompt residual, fit a regularized logistic probe for (a) woman in slot A and (b) the model's A/B margin sign. Fit scaling and coefficients on train families only; report validation/test predictions, majority baselines and a family-preserving label-shuffle control. These are gender-assignment/choice-readout probes, not latent-prejudice, care-competence or stereotype probes. Decision readout can merely recover gender or position; it does not identify a separate decision variable. A weak probe does not prove information is absent.

3. **Counterfactual patch scan.** Hold names, order, profiles and question fixed; flip only the two explicit gender labels. On the eight validation childcare prompts, transplant the donor's post-block residual at either both gender-cue endpoints or the last prompt token. Scan zero-based blocks 0, 9, 19, 29, 39, 49, 59, 69 and 79 in both gender directions. Align by semantic token offsets, not absolute donor token indices. Report the raw margin change and the source-to-donor gap; normalized transport is undefined for gaps smaller than 0.25. A full residual transplant can carry multiple variables, including the donor answer preference.

4. **Freeze a final-token layer.** For confirmation, choose the final-token block with the largest validation mean movement toward the counterfactual margin; break ties toward the earlier block. Exclude block 79 from selection, since copying the terminal answer state is a trivial output intervention. The cue scan remains a separate localization map. No test outcomes choose the layer, rank, strength or direction. This single-block scan does not locate a unique circuit, head or neuron.

5. **Held-out causal checks and erasure.** At that frozen layer, test full counterfactual replacement, self patch, same-gender donors from another name family, and rank-one gender-assignment erasure. Learn the erasure direction only from training childcare contrasts: `u = normalize(mean(h|woman-A) - mean(h|man-A))`, with their mean as center; apply `h' = h - u * dot(h-center,u)`. This is a measured assignment-contrast direction, not a pure gender concept. Compare against three prespecified random directions with the same intended intervention norm before BF16 rounding. Apply the frozen erasure to teamwork, both skill directions, same-gender controls and original multilingual prompts. A direction that flips everyone toward one slot or destroys qualification sensitivity is not a useful repair.

6. **Original-style answers.** Generate 16 held-out childcare prompts before and after erasure, greedy, up to 96 tokens; retain truncation flags. Recompute the original-style prefill, and intervene only during that prefill. Each generation creates its own downstream cache; never reuse a clean cache after a patch. Review all 32 answers with the existing B/R rubric and record exact evidence, selection, grounding and uncertainty. Do not claim B4 reduction until these answers have been reviewed. The generation limit is a time-saving supplement setting, distinct from the historical 1,024-token sampling experiment.

Report family-cluster intervals and actual denominators, not 16 independent demographic populations. Four test families are very few. Include negative and null patches, random controls, A/B noncompliance, incomplete generations, failures and utility changes. A 50/50 choice rate is not automatically an appropriate answer when the evidence is tied; asking for relevant information or proposing a neutral procedure remains valid.

Method references: [Zhang & Nanda, activation-patching metrics and methods](https://arxiv.org/abs/2309.16042), [Heimersheim & Nanda, interpreting activation patching](https://arxiv.org/abs/2404.15255). Probe information and intervention evidence answer different questions.

## Run today

From the repository root, with Modal authenticated and the existing `apertus-hf` secret available:

```powershell
$env:PYTHONUTF8='1'
python track_1a/supplementary/whitebox/design.py
python -m unittest discover -s track_1a/supplementary/whitebox/tests
modal run track_1a/supplementary/whitebox/modal_run.py --stage preflight
modal run track_1a/supplementary/whitebox/modal_run.py --stage prepare
modal run track_1a/supplementary/whitebox/modal_run.py --stage study --run-id gender-20261015-v1
```

Optional instrumentation smoke run before the study:

```powershell
modal run track_1a/supplementary/whitebox/modal_run.py --stage study --run-id gender-20261015-smoke --smoke
```

Use a fresh run ID on every invocation. Existing outputs are never overwritten. The launcher returns a compact summary and preserves detailed evidence on `apertus-gender-whitebox-results`. Download the run directory with `modal volume get`; activations can remain remote to keep the submission small. Do not include credentials in an evidence package.

The small collector excludes raw activations and records evidence hashes. After a completed run:

```powershell
python track_1a/supplementary/whitebox/collect.py gender-20261015-v2
python track_1a/supplementary/whitebox/analyze.py track_1a/supplementary/whitebox/evidence/gender-20261015-v2
```

The second command is offline. It verifies the input hashes, denominators, validation-only layer selection, training-only direction IDs and self patches, then recreates the overview figure, family-cluster intervals, original-style parser outcomes and complete before/after review casebook. Its analysis uses the original main-study NumPy/matplotlib dependencies; it does not need the optional inference environment.

Allow roughly 30–60 minutes for environment/cache checks and instrumentation, 30–90 minutes for the bounded model job (measure actual time), and 45–90 minutes for answer review, plotting and report editing. If the baseline has low A/B compliance or the original-style behavior does not replicate, report that boundary and the diagnostic results separately. If cloud access or instrumentation remains broken after a focused repair, retain this reproducible protocol and the completed behavioral submission; do not invent a mechanistic result to meet the deadline.

## Hackathon integration

The retained official requirements accept Apertus 8B or 70B, at most five issue files, the unchanged `track_1a/` directory, schema-valid findings, `make run` in Docker, a report of at most six pages excluding references, and private sharing until 1 December 2026. The project already has four issues; this experiment strengthens issue 01 rather than manufacturing a fifth issue from the same failure. Keep detailed methods/evidence here and use a compact panel and paragraph in the existing report **after results and review are complete**. Findings/data use CDLA-Permissive-2.0, code Apache-2.0 and report prose CC-BY-4.0.

The original offline entry point remains authoritative. The supplement must not make judges download 145 GB or supply a paid account. Include frozen results, their hashes, raw intervention measurements and a CPU analysis/verification command when a run completes. Docker still needs its previously documented clean-machine smoke test.
