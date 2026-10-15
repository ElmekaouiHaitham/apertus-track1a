# Gender and childcare: original-format white-box supplement

The question is: **when two people have the same supplied qualifications, where is their gender represented, and does that information causally influence whom Apertus recommends for childcare?** This supplements the completed behavioral audit, prepared on 15 October 2026.

The corrected experiment preserves the original instruction to name a person and give a one-sentence justification. It is complete: **full early gender-cue swaps change 16/16 fresh childcare selections; probe-axis swaps change 0/16 despite reversing the probe's gender prediction.** Start with [NATURAL_RESULTS.md](NATURAL_RESULTS.md) and its [figure](evidence/natural-gender-20261015-v1/analysis/natural_gender_mediation.png). See [NATURAL_PROTOCOL.md](NATURAL_PROTOCOL.md) for the frozen design.

## What the three measurements establish

| Measurement | Question it answers | What it cannot establish alone |
|---|---|---|
| Linear gender probes learned on neutral profile summaries | Can gender be read from this internal location? | Whether the model uses it to choose. |
| Existing vocabulary head applied across layers | Where does a gender-dependent preference between the actual names become visible? | An exact or irreversible decision time. |
| Internal counterfactual patches, followed by real generations | Does changing this state change the selected person while the recipient text stays fixed? | A unique neuron/circuit or a deployable fairness repair. |

Donors reverse only the two gender labels; names, display order, qualifications, question and output instruction stay fixed. The experiment patches either both gender-cue endpoints or the final prompt position after a decoder block. It compares full-state swaps with swaps along a gender-probe direction. A probe can change its prediction even when the actual recommendation does not change.

The primary outcome is the **actual generated selected name**, parsed using the main study's choice parser. Probe accuracy and intermediate name logits are separate supporting measurements. No model weights are trained or updated.

## Design, scope and compute

`natural_design.json` freezes 108 prompts: 24 non-choice calibration prompts, 8 childcare validation prompts, 16 childcare test prompts from four fresh name families, teamwork/qualification/same-gender controls, auxiliary donors preserving real qualifications, and 4 exact original English explicit-gender prompts. Both name orders and both gender assignments occur. The coarse layer scan uses validation only; confirmation names never choose a layer or direction.

The pinned public `swiss-ai/Apertus-v1.5-70B` checkpoint is loaded in BF16 on two A100 80GB GPUs. Its 80 decoder blocks have width 8,192. The checkpoint revision is `94888dd0db53f674b4c5304c1b726a7783d21393`; the required Transformers fork is pinned at `3797303dda74844e3d1f8977ff5518bb91f818b4`. Greedy generation, the native template, thinking disabled and no caller-supplied system message are recorded. The hosted main-study revision and provider system text were unavailable, so this is a pinned public-checkpoint replication and mechanistic supplement.

Existing cached weights and their hashes were verified before GPU allocation. One corrected-study job is capped at 90 minutes, internally at 85 minutes, with no retries. Two GPUs cost approximately $5/hour at the recorded rate, plus CPU, memory and other applicable charges; this is an estimate, not an account-wide bill or cap. Weights and raw activations remain on Modal and are not bundled for judges.

## Reproduce the completed evidence on CPU

After collection, the normal repository entry point verifies all completed supplement manifests and reconstructs figures and casebooks without a GPU, credentials or optional inference packages:

```sh
python -m pip install -r track_1a/requirements.txt
python track_1a/src/run_all.py
```

The corrected run's collector and analyzer are:

```sh
python track_1a/supplementary/whitebox/collect.py natural-gender-20261015-v1
python track_1a/supplementary/whitebox/natural_analyze.py track_1a/supplementary/whitebox/evidence/natural-gender-20261015-v1
```

Collection reads an existing Modal volume; analysis is offline. Only collect once inference has completed, so the frozen manifest describes final files.

## Optional paid inference

With Modal authenticated, the `apertus-hf` secret and existing `apertus-v1-5-70b-weights` volume:

```powershell
$env:PYTHONUTF8='1'
python -m unittest discover -s track_1a/supplementary/whitebox/tests
modal run track_1a/supplementary/whitebox/modal_run.py --stage preflight
modal run track_1a/supplementary/whitebox/modal_run.py --stage natural-study --run-id YOUR_FRESH_RUN_ID
```

The corrected stage performs CPU tokenization checks before allocating its GPU job. Never reuse a run ID. Paid inference is not part of `make run`. Exact methods and limitations are in [NATURAL_PROTOCOL.md](NATURAL_PROTOCOL.md).

## Relationship to the main audit and earlier pilot

The main study remains frozen: 2,582 displayed prompts, 12,910 planned calls, 12,904 successful responses, three languages and four findings. Gender-childcare explicit-cue choices selected women in 20/20 English, 18/20 French and 14/20 Arabic responses. Those related repetitions are not independent demographic samples. The main parser, B/R rubric, 192 completed human reviews, provenance and original 27 tests remain authoritative. New intervention outputs have not received human B/R scores.

The earlier experiment changed the output format to A/B. Its result and methods are retained in [RESULTS.md](RESULTS.md) and [AB_PROTOCOL.md](AB_PROTOCOL.md), with separate evidence under `gender-20261015-v2`. It demonstrated that changing a constrained answer statistic did not improve original-style recommendations. It is a secondary diagnostic, not the primary answer to the gender-mediated recommendation question. The corrected test names are fresh and its evidence is separate.

The retained hackathon requirements allow at most five issues, retain the `track_1a/` directory, require offline Docker reproduction and limit the main report to six pages excluding references. This supplement supports the existing childcare issue; it adds no fifth issue. The final six-page PDF now integrates the original-format study, its methods and specificity limits. Docker was unavailable on the workstation and still needs a clean-machine smoke test. Keep the submission private through 1 December 2026. Licensing is stated in [NOTICE.md](NOTICE.md).
