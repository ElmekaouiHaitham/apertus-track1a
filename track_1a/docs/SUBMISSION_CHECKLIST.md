# Final submission steps

- Keep `track_1a/` and its prerequisite filenames; the root Makefile delegates to it.
- The Dockerfile-derived Linux container and local Python replay pass; see FINAL_VALIDATION.md. Native Docker-daemon `make run` remains to be confirmed by the included Ubuntu CI workflow or a Docker-equipped machine.
- Review `ApertusChoiceAudit_Report.pdf` (six total pages including references), `technical_report.md`, and the four issue files under `findings/`.
- Revisit the medium-confidence audit records if time permits. Their uncertainty is retained in the report, not silently resolved by marking review complete.
- Create the PRIVATE GitHub repository from the official template and add `judgeailights` as collaborator. This package does not create, upload or publish a repository.
- Submit the repository URL and PDF using the official organizer submission page linked from the track README. Do not assume Devpost handles submission.
- Preserve the organizer embargo until 1 December 2026. Code: Apache-2.0; findings/data: CDLA-Permissive-2.0; report: CC-BY-4.0.
- Review the completed original-format gender/childcare supplement in `supplementary/whitebox/NATURAL_RESULTS.md`, including the same-gender and teamwork limits. Its methods, frozen evidence and CPU verifier are packaged; the six-page main PDF now integrates the behavioral and white-box evidence.

Sources: the preserved `README.md` and official template URLs in the report references. No guarantee of ranking or novelty beyond the documented evidence is claimed.
