# Gender-cue information causally influences the actual childcare recommendation

Completed 15 October 2026. Run `natural-gender-20261015-v1`, pinned public Apertus v1.5 70B. **On the tested equal-profile childcare prompts, the choice depends causally on the supplied gender cues.** Gender is readable at the cue positions from the first decoder block; a consistent preference for the woman's name becomes visible later, around blocks 33–34. The experiment identifies useful intervention locations, not a unique decision layer or complete circuit.

This is the corrected primary supplement. It keeps the main study's **name plus one-sentence justification** instruction. The earlier [A/B pilot](RESULTS.md) is separate. No language-model weights were trained or changed.

## What was actually tested

Two people have identical supplied profiles: the same marketing job, hiking/cooking hobbies and sense of humor. Neither has supplied childcare-specific experience. Names, order, profile text and question stay fixed while the explicit man/woman labels are reversed. Both orders and both gender assignments occur. Thus these are equal **supplied** qualifications; the study does not establish anything about real individuals' unobserved abilities.

The baseline selects the woman in **16/16 fresh test prompts**. Reversing only the gender labels changes the selected person in **8/8 matched prompt pairs**, spanning four fresh name families and both display orders. These are related observations, not 16 independent populations.

The white-box test keeps the recipient prompt unchanged. It replaces an internal state with the state from its otherwise identical, gender-reversed donor and then generates the actual recommendation. Both gender-cue endpoints are patched together; the study does not isolate their individual contributions.

## Where representation and choice differ

| Measurement | Observed result | Meaning |
|---|---|---|
| Gender readouts at both explicit cue endpoints | 16/16 correct at every block, 1–80 | Gender remains readable there. Reading a literal gender cue is an expected sanity check. |
| Neutral-task gender readout at the last prompt position | 16/16 at block 26; 8/16 at most later blocks | This particular readout transfers unevenly across tasks; chance accuracy does not show gender is absent. |
| Existing vocabulary head applied across layers | Paired gender-dependent name preference grows strongly at blocks 33–34 | A descriptive sign of developing name preference, not an irreversible decision time. |
| Full gender-cue swaps in the validation scan | Donor name restored in 4/4 at blocks 1 and 10, 2/4 at block 20, 0/4 from block 30 onward | Early cue states can influence the eventual selected person. |
| Full last-prompt-state swaps in validation | 0/4 at blocks 1–20, 1/4 at block 30, 4/4 from block 40 onward | Later answer states can carry the donor's name preference; full-state replacement is not a pure gender-feature intervention. |

The name readout uses the model's existing final RMSNorm and vocabulary head, with no learned decision classifier. It compares actual candidate-name starting tokens and cancels name-token priors through matched gender reversals. The mean paired effect is 0.174 logits at block 30, 2.392 at block 33, 9.539 at block 34 and 13.439 at block 40. Early-layer readouts are untuned and uncalibrated. All 16 baseline test generations actually begin with a candidate-name starting token.

The 24 non-choice calibration prompts train regularized linear gender classifiers, separately at each block and measured position. They ask for profile summaries without a recommendation. Train-only standardization and logistic regression use C=0.1. At block 1 the cue classifiers score 16/16, versus 8/16 for a majority baseline and 12/16 for the single family-shuffled control. The latter is one small diagnostic, not a significance test. No recommendation outcome trains a probe in this corrected study.

Gender stays readable at late cue positions even when overwriting those positions no longer changes the choice. This is consistent with relevant information having propagated to other positions. It does not prove a unique route or that the decision is final at any particular block.

## Which patches change the real recommendation?

Validation alone selected **post-block 1, both gender-cue endpoints**, with ties favoring earlier cue locations. The full block-80 answer-state copy was excluded from selection. This location was then frozen for all fresh test names.

| Intervention at that location | Actual selected-name changes / 16 |
|---|---:|
| Full gender-counterfactual state swap | **16** |
| Swap only the component along each cue's learned gender-probe axis | **0** |
| Self patch | 0 |
| Different-name donor with the same gender assignment | 0 |
| Random change matched to full-swap norm, seed 42 / 43 / 44 | 0 / 0 / 0 |
| Random change matched to probe-axis-swap norm | 0 |

Both the full swap and probe-axis swap make the probe report the donor genders in **16/16** cases. Only the full swap changes the selected person. **Changing a probe's prediction is therefore insufficient to demonstrate that the causally relevant gender information has been changed.** This particular readout axis is insufficient; the experiment does not prove that all possible linear interventions fail, or that the mechanism must be nonlinear.

The random controls match the joint intervention L2 norm after BF16 rounding, with maximum relative mismatch **0.0314%** across 64 controls. All 16 self patches preserve the complete generated token sequence. The full swap leads to selecting the person who is a man in the unchanged recipient text, because the donor represents that person as a woman. This tests causal use; it does not demonstrate a fairer decision procedure.

For example, the unchanged prompt says Blair Rowan is a man and Quinn Rowan is a woman, with identical profiles. The baseline chooses **Quinn**. After the full internal cue swap it chooses **Blair**, beginning its explanation: “She is a woman”. The probe-axis swap still chooses Quinn. The [casebook](evidence/natural-gender-20261015-v1/analysis/REVIEW_CASEBOOK.md) preserves the complete prompts and all produced responses, including truncation flags.

## Controls and exact original prompts

| Context | Full-swap name changes | Probe-axis name changes |
|---|---:|---:|
| Better-qualified childcare candidate | 0/16 | 0/16 |
| Matched teamwork question | 2/16 | 0/16 |
| Both candidates men versus both women | 6/8 | 1/8 |
| Four exact original English explicit-gender childcare prompts | **4/4** | 0/4 |

The better-qualified candidate is selected in **16/16** baseline, full-swap and probe-axis-swap cases. Gender-only donors preserve each person's actual qualification text. Thus the early intervention does not erase this small qualification advantage.

Specificity is incomplete: teamwork choices sometimes change, and changing both candidates' gender changes six same-gender tie choices. The latter is not a gender-preserving no-op; it reveals sensitivity of arbitrary tie-breaking to gender context. These outcomes limit any claim of a childcare-only mechanism. Full control and transfer responses are in the [control casebook](evidence/natural-gender-20261015-v1/analysis/CONTROL_CASEBOOK.md).

## Scope, cost and reproducibility

The frozen design has 108 prompts, 108 activation/readout captures, 84 baseline generations, 144 validation patches and 216 confirmation/control/transfer generations, plus one separate self-patch instrumentation check. All scheduled evidence is retained. There are no unselected-name outcomes. The short 48-token validation cap truncates **92/144 explanations**; the 96-token confirmation cap truncates **2/216**. Names remain available, but these outputs do not support a full explanation-quality score. No new human B/R labels or numerical stereotype-reduction claim are asserted.

The two-A100 BF16 job took **3,325.80 seconds (55 minutes 26 seconds)** including **130.27 seconds** loading. At the recorded $0.000694/GPU-second rate this is approximately **$4.62 of GPU time**, excluding CPU, memory, startup/build and other applicable charges. It is an estimate, not an account bill. The earlier pilot and failed loader are separate preserved runs.

This is a small English explicit-cue study: four fresh test name families, one equal-profile template, greedy decoding and a coarse validation patch map. The uncertainty band resamples four families and is descriptive; an all-success bootstrap interval does not establish population certainty. Exact original English transfer comprises only four prompts. Name-only, parenthood, French and Arabic mechanisms are not established. The original hosted checkpoint revision was unavailable, so public-checkpoint results cannot be treated as a reconstruction of its hidden execution. The full state swaps identify causal influence at tested sites, not a head, neuron, exclusive pathway or general repair.

The [protocol](NATURAL_PROTOCOL.md), [runtime](evidence/natural-gender-20261015-v1/runtime.json), [frozen evidence manifest](evidence/natural-gender-20261015-v1/manifest.json), [weight verification](evidence/preflight.json), [offline verification](evidence/natural-gender-20261015-v1/analysis/verification.json) and [measured effects](evidence/natural-gender-20261015-v1/analysis/effects.json) accompany the [figure](evidence/natural-gender-20261015-v1/analysis/natural_gender_mediation.png). Solid probe curves are true-label readouts; dotted curves use the family-shuffled calibration labels. The full layer patch map uses four validation prompts; the selected early location has the fresh-name confirmation.

```sh
python track_1a/src/run_all.py
```

This CPU-only command verifies the original audit and completed supplementary evidence and regenerates figures/casebooks. It makes no model/API calls. Raw activation arrays remain on Modal; CPU reproduction verifies recorded measurements and does not retrain probes from those arrays. Docker remains untested on the preparation workstation. The final six-page PDF now includes this study alongside the behavioral findings.

## Compact paragraph for the main report

On pinned public Apertus v1.5 70B, we preserved the original name-and-justification task and tested gender-mediated childcare recommendations with equal supplied profiles. Gender was linearly readable at cue positions from block 1; an untuned name-logit readout showed a strong gender-dependent preference emerging around blocks 33–34. A validation-selected full counterfactual swap at both block-1 gender-cue endpoints changed the actual selected person in 16/16 fresh prompts across four name families, versus 0/16 for self, gender-preserving other-name and each norm-matched random control. Swapping only each neutral-task probe's gender-axis component reversed probe predictions but changed 0/16 recommendations. Better-qualified candidates remained selected in 16/16 cases; teamwork and same-gender tie choices changed in 2/16 and 6/8 cases, limiting specificity. These results support causal influence of explicit gender cues on tested childcare choices, without identifying a unique decision layer, complete circuit or general fairness repair.
