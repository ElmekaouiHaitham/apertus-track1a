# Where gender is represented and where it influences the actual childcare recommendation

This is the corrected primary question: **with names, position and supplied qualifications fixed, where is gender readable inside Apertus, and which gender-related internal interventions change the actual selected name?**

The earlier A/B experiment is retained as a separate diagnostic. It changed the response format and therefore did not fully answer this question. This follow-up keeps the original name-plus-justification instruction throughout the behavioral experiment. Its four test name families are fresh; earlier test outcomes do not become new held-out evidence.

## Three measurements with different meanings

1. **Gender representation.** Train linear gender readouts on 24 neutral profile-summary prompts that never request a recommendation. Read activations at each candidate's gender-cue endpoint and at the last prompt token, after every decoder block. Evaluate on the childcare task and unseen test names. Readability alone establishes available gender information, not its use to choose.
2. **Developing name preference.** Apply the model's existing final normalization and vocabulary output head to the last-prompt residual at each block, and inspect the logits of the actual candidate-name starting tokens. No decision classifier or A/B answer instruction is introduced. This untuned intermediate readout is descriptive; early-layer states are not calibrated final predictions. Its relevance is checked against the actual generated first token and completed recommendation.
3. **Causal use.** For an original prompt, obtain a donor from the otherwise identical prompt with only man/woman labels reversed. Keep the recipient's text unchanged, patch a prespecified internal location, and generate the real name and justification. If the selection moves toward the donor's chosen name, information at that location contributes to the recommendation. A full final-state patch can transfer a formed answer, so it must not automatically be called a pure gender intervention.

The causal scan therefore includes both **full residual replacement** and **replacement of only the component along a gender-probe direction learned on the non-choice calibration task**. Probe coefficients are converted from standardized features back to raw activation coordinates before intervention. At the gender-cue positions, the task question has not occurred yet: the identical prefix makes these representations independent of the later childcare-versus-summary instruction. This helps separate gender-cue representation from a later task-conditioned answer state.

The experiment does not assume a single irreversible decision layer. It measures a map of gender readability, emerging name preference and intervention effects. A failed selective patch does not prove that gender is unused; the fitted readout axis may omit other causally relevant features, including other linear directions. It does not by itself prove a nonlinear or distributed mechanism.

Reading gender at an explicit man/woman token is an expected sanity check. The substantive test is whether a donor differing only in those cues changes a later recommendation through internal patching. Both cue endpoints are patched together, so the study does not separate their individual contributions or identify a particular head/neuron. The complete layer map is a small validation measurement; only the validation-selected location is confirmed on the fresh test families.

## Design and safeguards against a misleading answer

- Six training name families supply 24 neutral calibration prompts. Two validation families supply eight original-format childcare prompts. Four fresh test families supply 16 original-format childcare prompts.
- Both name orders and both gender assignments occur for every family. Donors keep names, order and supplied qualifications fixed, reversing only the explicit gender labels.
- Held-out teamwork, better-qualified childcare candidates in both gender directions, and same-gender cases test whether a patch merely forces a name/position or destroys use of individual evidence.
- Sixteen auxiliary qualification donors reverse gender while keeping the better-qualified person fixed. The complete frozen design has 108 prompts, including 24 calibration prompts and 84 baseline generations.
- Four exact English explicit-gender childcare prompts from the main dataset are a separate transfer check. Name-only cues remain a separate semantic confound; this study's strongest causal conclusions concern explicit supplied gender.
- A coarse scan uses blocks 1, 10, 20, 30, 40, 50, 60, 70 and 80 at the cue endpoints and last prompt token. Four validation prompts, two patch types and two sites give 144 scan generations. The scan's 48-token cap prioritizes an actual selected name; truncations remain flagged and do not support a full justification score.
- Freeze the best full-replacement location using validation donor-name restoration, exclude terminal answer-state copying, and break ties toward cue sites then earlier blocks. Confirm full and gender-component replacement there on all 16 fresh test prompts.
- Compare self patches, other-name donors with the same gender assignment, three random directions matched to the full-patch norm and one matched to the gender-projection norm. Test prompts never choose the layer, direction or strength.
- Confirmation uses greedy generation and a 96-token limit. Preserve the full response, token IDs, exact name/slot extraction, neutral/unclear outcomes and truncation. Random controls are matched after BF16 rounding as closely as the recorded construction permits; report intended and actual norms.

CPU tokenizer preparation verified distinct first-name starting tokens for all 108 prompts. Every recipient/donor pair also has identical token length and corresponding cue/answer positions, avoiding a positional mismatch in the gender contrast. Name-start logits remain descriptive; completed generated recommendations are the primary outcomes.

Primary outcomes are **actual selected name and donor-name restoration**, not an A/B score or a probe's own prediction. A patch that causes the model to treat a recipient as the donor's gender is a causal diagnostic, not a proposed fairness repair. Explanations can reveal misattribution after patching and must be read in full.

Public 70B weights, revision, template and BF16 settings are pinned as in the first experiment. The hosted revision of the main study remains unknown. One two-A100 job is capped at 90 minutes with no automatic retries; existing verified weights and the existing inference image are reused.
