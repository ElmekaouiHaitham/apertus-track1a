# Final submission validation

Prepared 15 October 2026. This record distinguishes completed checks from checks that require an external runner. The final archive fingerprint and detailed machine records accompany the archive.

## Submission contract

- Official template pinned to `09f8e9e2b588db3325869b23c6d5132f5c3756f7`; original files and hashes retained under `audit/upstream_20261015/`.
- Four real findings, using the organizer's fields and unchanged validation rules. The upstream literal-newline JSON error is escaped only in the description; raw bytes are preserved.
- Eighteen complete walkthroughs: sixteen reviewed historical conversations and two unpatched public-checkpoint baselines. Supplemental provenance and decoding settings are explicit. Internal interventions remain separately labeled in their casebooks.
- Integrated report: six content pages plus one reference page. `ApertusChoiceAudit_Report.pdf`, `HaithamElmekaoui_Report.pdf` and `findings.pdf` contain identical bytes. The first is the team-named upload; the others are compatibility aliases.
- Original behavioral corpus and human labels remain frozen. No new human B/R labels, hidden-intent claim, demonstrated repair or new vulnerability class is invented.

## Reproduction commands

The organizer's command, from the repository root:

```sh
make run
```

Python equivalent:

```sh
python -m pip install -r track_1a/requirements.txt
python track_1a/src/run_all.py
```

The workflow runs 30 original/integration tests and 10 supplementary tests, verifies findings regeneration, reconstructs all original evidence analyses, verifies both completed white-box datasets, rebuilds the compact report panel and checks final PDF/schema/section contracts. Two Torch-specific toy-hook tests skip when optional Torch is absent; real-run self-patch checks remain part of frozen-evidence verification.

## Validation status

The complete declared entrypoint passed in a fresh Dockerfile-derived Linux container (Python 3.11.13, two CPU cores, 8GiB RAM), with outbound runtime networking blocked. Recorded build-and-run time: 77.86 seconds. All 30 core tests passed; the 10 supplementary tests passed with two optional Torch toy tests skipped in the minimal image. Both studies and final contract checks passed. Source, findings, frozen data and report hashes match the final package. Machine record and logs: `audit/final_container_validation.json`, `final_container-stdout.txt`, `final_container-stderr.txt`. Local Python replay also passed all 40 tests with Torch available. Clean extracted-archive replay is checked again at final packaging and recorded alongside the archive. This workstation has no Docker executable/daemon. A Dockerfile-derived Modal image includes Modal runtime dependencies; passing that check is not represented as having executed a native Docker-daemon `make run`. The included GitHub Actions workflow runs that exact command on Ubuntu when the private repository is uploaded; it has not been triggered here.

## What replay establishes

Frozen replay checks data/source hashes, original decisions, evaluator recovery, literal human evidence, classifier predictions/labels, donor restoration, self patches, scheduled denominators and report contracts. It needs no model weights, GPU, credentials or live requests. Raw activation arrays remain on Modal; replay does not independently retrain probes or regenerate 70B answers. Optional fresh hosted requests are stochastic; public white-box inference pins a checkpoint, implementation, template and settings separately from the unexposed hosted revision.

The six-page PDF was compiled with Tectonic 0.17.0 and rendered page by page for visual inspection. A Git commit is not invented for the local workspace; source and archive SHA-256 fingerprints identify the delivered artifacts.
