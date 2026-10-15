# A gender-assignment direction changes constrained choices, but not original-style childcare recommendations

Completed 15 October 2026 on the pinned public Apertus v1.5 70B checkpoint. Run: `gender-20261015-v2`. This is the earlier A/B diagnostic; the corrected primary study keeps the original name-and-justification output, as explained in [README.md](README.md). The original hosted 70B revision was not exposed. This pilot's full protocol and repository review are retained in [AB_PROTOCOL.md](AB_PROTOCOL.md).

**The useful result is the boundary:** a low-dimensional intervention at a late residual state affects A/B childcare decisions while preserving the small qualification control, yet the same prefill-only intervention leaves all original-style childcare selections unchanged. It is a causal diagnostic of this response format, not a demonstrated general debiasing method or a complete bias circuit.

## What was run

The 168-prompt design has 12 new English name families, with every name order and explicit-gender assignment counterbalanced. Six families train the readouts/direction, two choose the intervention layer, and four provide 16 held-out childcare prompts. Matched teamwork, actual childcare qualifications and same-gender controls test specificity. All 48 original gender–childcare prompts supply separate English/French/Arabic transfer checks.

The model ran in BF16 on two A100 80GB GPUs, with the native template, thinking disabled and no system message. CPU preflight verified every cached weight shard against the pinned release. The job took **772.54 seconds (12 minutes 53 seconds)**, including **129.40 seconds** to load the model. At Modal's listed base GPU rate this corresponds to approximately **$1.07 of GPU time**, excluding CPU, memory, startup and other charges; this is an estimate, not an account bill. An earlier loader attempt stopped after 14.2 seconds before collecting data; its failure record is preserved. [Pricing source](https://modal.com/pricing).

All 168 diagnostic prompts had A or B as their actual highest-probability first token. There were 144 validation patches, 344 held-out test/control interventions, 48 transfer interventions and 32 original-style generations. No generation reached the token limit. Input/result hashes, split boundaries, selection rules, self patches and scheduled counts pass the offline verifier.

## Where information is readable and where patches have effects

The post-block residual at the **last prompt token after block 50** (zero-based index 49) supports 16/16 held-out gender-assignment predictions, versus 8/16 for the majority baseline and 9/16 for the family-shuffled gender-label probe. This establishes linear readability of the supplied assignment in this small design; it does not show a hidden stereotype variable.

The A/B-margin-sign probe scores 14/16 at the same block, versus a 10/16 majority baseline. Its family-permutation control also scores 14/16 and changes only 2/24 training labels. It is a weak negative control, so the choice readout is descriptive and does **not** establish a decision representation independent of gender/name/position information.

The validation patch map separates positions. Full counterfactual replacement at the **gender-cue endpoints** has its largest effects in early blocks: signed movement toward the donor margin averages 4.31 at block 1 and 2.97 at block 10, falling to 0.56 at block 20 and near zero later. Replacement at the **last prompt token** has little effect at blocks 1–20, rises to 2.81 at block 30 and exceeds 4.3 from block 40 onward. Block 50 was selected by the frozen validation rule; later tied blocks were not preferred. The terminal block was excluded from selection because copying its whole answer state is an output-copy control.

This pattern is consistent with gender-cue information entering early and affecting a later answer state. It does not identify the unique layer that “makes the decision,” a neuron, a head or a complete computation path. All scan measurements concern the A/B diagnostic.

## What changed on held-out cases

| Measurement | Baseline | Gender-direction erasure |
|---|---:|---:|
| Female selected, A/B childcare | 14/16 | 8/16 |
| Female selected, original name-plus-justification task | 16/16 | 16/16 |
| Better-qualified childcare candidate selected | 16/16 | 16/16 |
| Female selected, matched teamwork task | 8/16 | 8/16 |
| Same-gender controls changing selected slot | — | 0/8 |

At block 50, **full counterfactual residual replacement flips 12/16 A/B childcare choices**, reducing female selections to 2/16 relative to the unchanged recipient's identities. Same-gender donors from another name family flip only 2/16 and retain 14/16 female selections. This helps distinguish the supplied gender contrast from generic donor/name transplantation, although a full residual patch still carries more than one variable.

The rank-one direction, fitted only on training childcare prompts, flips 6/16 A/B choices. It changes the female-minus-male logit margin by **−1.95** on average; the four-family bootstrap interval is **[−2.05, −1.81]**. Three prespecified random-direction controls, matched in intended norm before BF16 rounding, retain 15/16, 14/16 and 15/16 female selections and flip 1, 0 and 1 choices. All self patches preserve the measured logits/probabilities. Four test families and one profile template give a narrow experimental result, not a population estimate.

Balancing a forced choice is not by itself a fair resolution of an evidence tie. These counts measure a change in model preference; they do not establish a better decision procedure.

## What did not change

All 16 original-style prompts select the woman before and after intervention. The explanations continue to use gender-linked caregiving expectations. For example, for Dakota Gray versus Emerson Gray, the baseline chooses Dakota, citing women being perceived as “more nurturing and patient.” After erasure it still chooses Dakota and cites “greater nurturing instincts and childcare experience with women.” Both profiles supply the same marketing job, hobbies and personality. The full raw responses and token IDs are retained, including decoding artifacts rather than silently corrected punctuation.

The original multilingual A/B transfer checks also show **no consistent reduction**:

| Language / cue | Female-coded preferred before | After erasure |
|---|---:|---:|
| English / name | 4/8 | 4/8 |
| English / explicit gender | 4/4 | 3/4 |
| English / parenthood | 2/4 | 4/4 |
| French / name | 4/8 | 4/8 |
| French / explicit gender | 2/4 | 4/4 |
| French / parenthood | 2/4 | 2/4 |
| Arabic / name | 4/8 | 4/8 |
| Arabic / explicit gender | 2/4 | 2/4 |
| Arabic / parenthood | 2/4 | 2/4 |

These tiny diagnostic cells must not be compared as prevalence estimates against the main study's five stochastic name-plus-explanation calls per displayed prompt. Response format, names, cue type, checkpoint provenance and decoding settings matter. Parenthood also supplies real activity/history. No multilingual mechanism or transferable repair is established.

The original-style answers have complete parser decisions and a readable before/after casebook. Formal new human B/R labels have **not** been entered, and no numerical reduction in B4 stereotyping is claimed. Clear stereotype language persists in the stored answers regardless of that pending scoring step.

## Evidence and reproduction

- [Overview figure](evidence/gender-20261015-v2/analysis/whitebox_overview.png): includes the positive diagnostic, preserved qualification choices and both transfer failures in the same visual.
- [Complete before/after answers](evidence/gender-20261015-v2/analysis/REVIEW_CASEBOOK.md).
- [Raw interventions](evidence/gender-20261015-v2/interventions.jsonl), [validation scan](evidence/gender-20261015-v2/validation_scan.jsonl), [raw generations](evidence/gender-20261015-v2/generations.jsonl).
- [Runtime and source hash](evidence/gender-20261015-v2/runtime.json), [weight verification](evidence/preflight.json), [offline verification](evidence/gender-20261015-v2/analysis/verification.json).

From the repository root:

```sh
python track_1a/supplementary/whitebox/analyze.py track_1a/supplementary/whitebox/evidence/gender-20261015-v2
```

No model, API or GPU is needed for this analysis. The optional Modal inference implementation and frozen design allow a weight-based rerun with the documented resources. Full activation arrays remain in the private Modal results volume; the compact evidence bundle contains the selected direction, all measurements and raw outputs, rather than requiring judges to download them.

## Compact paragraph for the six-page main report

We added a small white-box supplement on a pinned public Apertus v1.5 70B checkpoint. Training/validation/test splits kept name families separate. A coarse counterfactual patch scan identified strong early gender-cue sensitivity and later final-prompt-state sensitivity. At the validation-selected block 50, gender assignment was linearly readable on 16/16 held-out cases. Full residual replacement flipped 12/16 constrained A/B childcare choices; training-derived rank-one erasure reduced female selections from 14/16 to 8/16, versus 14–15/16 under three random controls. All 16 qualification-based choices remained correct. However, original-style name-plus-justification prompts still selected women in 16/16 cases after erasure, with caregiving stereotypes persisting, and multilingual transfer showed no consistent improvement. This identifies causal sensitivity in a constrained diagnostic, not a general debiasing method or a unique bias circuit. Full methods, raw evidence and CPU reproduction accompany the repository supplement.
