# Choice dataset dictionary

`data/prompts.csv` has 2,582 rows. Names, prompt text and stable IDs are unchanged from the active study. Values are experimental design metadata, not verified demographic facts about actual people. The profiles are synthetic.

| Column | Meaning |
|---|---|
| `id` | Stable original displayed-prompt ID; gaps remain after scope filtering. |
| `tier` | Original pilot/core/full allocation; not a severity label. |
| `lang` | `en`, `fr`, or `ar`. |
| `task` | Always `choice` in this submission. |
| `domain` | Professional decision or social preference. |
| `cue` | `name`, `explicit`, `embedded`, or `none` for identity-free controls. |
| `profile_form` | `stated_identical` short comparison or `full_profile`. |
| `scenario` | Hiring, loan, admission, housing, coworker, friend, date, neighbor or childcare. |
| `framing` | Original framing condition; active collection uses `neutral`. |
| `axis` | Experimental gender/race/national-origin/religion axis, or none in identity-free controls. |
| `group_tag` | Specific local comparison variant; useful for separating Muslim/Jewish/Christian or origin pairings. |
| `name_variant` | Identifier for the neutral-name assignment/cue variant. |
| `pair_id` | Base unit shared by the two display orders; bootstrap cluster. |
| `shown` | `both` for a two-person choice. |
| `target_slot` | A or B block containing the target experimental side. |
| `reference_name` | Exact reference-side displayed identifier, sometimes including an explicit cue suffix. |
| `target_name` | Exact target-side displayed identifier, sometimes including an explicit cue suffix. |
| `ref_cue_text` | Reference-side explicit/embedded attribute text, when supplied. |
| `tgt_cue_text` | Target-side explicit/embedded attribute text, when supplied. |
| `about_role` | Reserved historical metadata; empty for these choice rows. |
| `valence` | Reserved historical metadata; empty for these choice rows. |
| `prompt` | Complete original user prompt, verbatim. |
| `ideal_behavior` | Builder's intended evaluation behavior; not a gold individual decision. |
| `control_type` | `none` for comparisons, `no_identity`, or `same_identity`. |
| `control_group` | Shared original side's cue in same-identity controls; otherwise empty. |

`responses.jsonl.gz` adds collection fields to those prompt columns. There is one selected final result per planned `(run_id, id, repetition)`, after resolving raw attempt records. `status`, `error`, `attempt`, timestamps and token usage preserve collection context; `model`, `temperature`, `max_tokens` and `system_prompt` preserve caller settings. `response` is untouched model text. `finish_reason` retains truncation/stop information. `api_response_id` is a provider identifier, not a credential. Six unsuccessful planned jobs remain as errors. The original attempt logs remain in the local archive.

`job_key` in judge/review data is `run_id|id|repetition`. It joins one original response across evaluators. `evaluation_id` identifies one judge condition/request. Judge evaluation IDs are not interchangeable with original response IDs.

## Extracted decisions

`recorded_decisions.jsonl.gz` freezes the original parser's outcome for regression comparison. `output/decisions.csv` regenerates it from the raw response, adding the recognized name, slot, selection side, literal evidence, matching rule, equivalence/refusal flags and uncertainty notes. T/R/N/U/E retain all planned jobs. Detailed N reasons are not discarded. Unclear and collection errors remain separate.

## Automated evaluation

- `clef_raw.jsonl.gz`: original typed answers, category probabilities and binary-question values, keyed by job/evaluation ID. NUL padding from a cloud-log corruption was removed when packaging; no JSON scalar or wording was altered.
- `clef_judgments.jsonl.gz`: derived B/R scores, probabilities, confidence and reuse status. Full original text is joined from responses rather than duplicated.
- `self_raw.jsonl.gz`: latest original raw judgment/status per known evaluation ID; nine unknown outcomes have no raw record. The complete attempt history remains local.
- `self_judgments.jsonl.gz`: all 25,808 planned condition rows, recovered scores, raw/matched evidence, explanations, extraction quality, original strict status and metadata/rubric flags.
- `self_paired.csv`: one row per original successful response, scores from both authorship conditions, evidence-qualified flags and separately labeled all-extracted/evidence-qualified score differences.
- `self_prompt_bundle.json`: exact system rubric/schema and the two authorship sentences. `clef_questions.json`: exact typed question definitions.

`score_only` means a numeric label was recovered but its evidence/explanation was insufficient. `evidence_backed` is the original field name for evidence-qualified extraction: the source quote could be located, not that the score is semantically correct. `unavailable` retains missing/uninterpretable dimensions as null/empty. Raw labels were not replaced by another judge.

## Human evaluation

`human_annotations.jsonl.gz` contains the 192 completed records, each with B/R scores, exact evidence, explanations, operative decision/name/slot, equality, tie-break, identity use, stereotype endorsement, context, confidence and adjudication flags. The original `case_id` H001–H192 is stable. `sampling_cohort`, `sampling_stratum`, eligible-frame sizes and sampling probabilities preserve the design. `review_method` distinguishes directly entered human labels from human verification of AI drafts. Drafting notices were removed from the visible notes after human confirmation; the audit provenance remains.

`exemplars.json` contains the 12 cited human-reviewed examples with full prompts/responses and response hashes. Findings walkthroughs reconstruct API roles using template delimiters; they do not contain hidden provider instructions or a native-token capture. English translations in the report are editorial aids, never substituted for original-language evidence values.
