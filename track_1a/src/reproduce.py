"""Reproduce the choice audit from frozen evidence, without API keys or GPUs.

Outputs are regenerated, not copied from the report. All rates retain N/U/E;
repetitions and A/B swaps are clustered by the original pair_id for bootstrap
intervals. Automated rubric scores remain fallible measurements.
"""

from __future__ import annotations

import argparse
from collections import Counter
import gzip
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd
import choice_parser

ROOT = Path(__file__).resolve().parents[1]
SCENARIOS = [
    "hiring",
    "loan",
    "admission",
    "housing",
    "coworker",
    "friend",
    "date",
    "neighbor",
    "childcare",
]
LANGUAGES = ["en", "fr", "ar"]
AXES = ["gender", "race", "national_origin", "religion"]
LABELS = ["T", "R", "N", "U", "E"]


def load(name):
    with gzip.open(ROOT / "data" / name, "rt", encoding="utf-8") as stream:
        return [json.loads(line) for line in stream]


def write_json(path, value):
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )


def validate_inputs():
    manifest = json.loads((ROOT / "data/manifest.json").read_text())
    for name, expected in manifest["files"].items():
        actual = hashlib.sha256((ROOT / name).read_bytes()).hexdigest()
        if actual != expected:
            raise ValueError("Frozen data hash mismatch: " + name)
    return manifest


def outcome_table(frame, keys):
    result = (
        frame.groupby(keys + ["headline_decision"], dropna=False)
        .size()
        .unstack(fill_value=0)
        .reindex(columns=LABELS, fill_value=0)
    )
    result["n"] = result.sum(axis=1)
    for label in LABELS:
        result[label + "_pct"] = 100 * result[label] / result["n"]
    result["target_among_selected_pct"] = (
        100 * result["T"] / (result["T"] + result["R"]).replace(0, np.nan)
    )
    return result.reset_index()


def paired_interval(frame, seed=42, replicates=2000):
    """Bootstrap base pairs, preserving both orders and all repeated calls.

    This is the count difference (T-R)/all planned jobs; unknown/error outcomes
    retain their denominator. It does not interpret them as neutral judgments.
    """
    values = (
        frame.assign(delta=frame.headline_decision.map({"T": 1, "R": -1}).fillna(0))
        .groupby("pair_id")
        .agg(delta=("delta", "sum"), n=("delta", "size"))
        .to_numpy()
    )
    rng = np.random.default_rng(seed)
    draws = rng.integers(len(values), size=(replicates, len(values)))
    boot = values[draws].sum(axis=1)
    low, high = np.quantile(100 * boot[:, 0] / boot[:, 1], [0.025, 0.975])
    return dict(
        n_pairs=len(values),
        target_minus_reference_pp=float(100 * values[:, 0].sum() / values[:, 1].sum()),
        ci_low=float(low),
        ci_high=float(high),
    )


def agreement(left, right, maximum):
    a = np.asarray(left, dtype=int)
    b = np.asarray(right, dtype=int)
    n = len(a)
    confusion = np.zeros((maximum, maximum), dtype=int)
    for x, y in zip(a, b):
        confusion[x - 1, y - 1] += 1
    weights = (np.arange(maximum)[:, None] - np.arange(maximum)[None, :]) ** 2 / (
        maximum - 1
    ) ** 2
    observed = confusion / n
    expected = np.outer(confusion.sum(axis=1), confusion.sum(axis=0)) / n**2
    den = (weights * expected).sum()
    return dict(
        n=n,
        exact_pct=float(100 * np.mean(a == b)),
        adjacent_pct=float(100 * np.mean(np.abs(a - b) <= 1)),
        quadratic_weighted_kappa=(
            float(1 - (weights * observed).sum() / den) if den else None
        ),
        confusion=confusion.tolist(),
    )


def analyze(out):
    manifest = validate_inputs()
    out.mkdir(parents=True, exist_ok=True)
    rows = load("responses.jsonl.gz")
    recorded = load("recorded_decisions.jsonl.gz")
    parsed = [choice_parser.parse_row(r) for r in rows]
    for row, old, new in zip(rows, recorded, parsed):
        for field in (
            "headline_decision",
            "parse_outcome",
            "picked_name",
            "picked_slot",
            "parse_method",
        ):
            if str(old[field]) != str(new[field]):
                raise ValueError(
                    f'Parser mismatch {row["id"]}/{row["repetition"]}: {field}'
                )
    frame = pd.DataFrame(
        [
            {**r, **p, "job_key": "|".join([r["run_id"], r["id"], r["repetition"]])}
            for r, p in zip(rows, parsed)
        ]
    )
    assert len(frame) == 12910 and frame.job_key.is_unique
    assert (
        set(frame.task) == {"choice"}
        and not set(frame.axis) & {"age", "disability"}
        and "medical" not in set(frame.scenario)
    )
    frame.to_csv(out / "decisions.csv", index=False)
    main = frame[frame.control_type == "none"].copy()
    for name, subset, keys in [
        ("selection_by_language_scenario", main, ["lang", "scenario"]),
        (
            "selection_by_language_axis_cue_scenario",
            main,
            ["lang", "axis", "cue", "scenario"],
        ),
        ("selection_by_language_axis_cue", main, ["lang", "axis", "cue"]),
        (
            "arabic_religion_by_cue_scenario",
            main[(main.lang == "ar") & (main.axis == "religion")],
            ["cue", "scenario"],
        ),
        ("controls", frame[frame.control_type != "none"], ["control_type", "lang"]),
        ("uncertainty", frame, ["control_type", "lang", "cue"]),
        ("position", frame, ["control_type", "lang", "target_slot"]),
    ]:
        outcome_table(subset, keys).to_csv(out / (name + ".csv"), index=False)
    intervals = []
    for (lang, axis, scenario, cue), sub in main.groupby(
        ["lang", "axis", "scenario", "cue"]
    ):
        intervals.append(
            dict(
                lang=lang, axis=axis, scenario=scenario, cue=cue, **paired_interval(sub)
            )
        )
    pd.DataFrame(intervals).to_csv(out / "selection_pair_bootstrap.csv", index=False)
    # Position-symmetrized per-pair summaries prevent treating swaps as independent cases.
    main.assign(
        target=(main.headline_decision == "T").astype(int),
        reference=(main.headline_decision == "R").astype(int),
    ).groupby(["pair_id", "lang", "axis", "cue", "scenario"]).agg(
        n=("id", "size"),
        target_rate=("target", "mean"),
        reference_rate=("reference", "mean"),
    ).to_csv(
        out / "pair_selection.csv"
    )
    clef = pd.DataFrame(load("clef_judgments.jsonl.gz"))
    self_j = pd.DataFrame(load("self_judgments.jsonl.gz"))
    # Derive automated labels from original raw outputs before accepting frozen tables.
    from clef_extract import annotation as clef_annotation
    from self_extract import extract as self_extract

    clef_lookup = clef.set_index("job_key").to_dict("index")
    for raw in load("clef_raw.jsonl.gz"):
        value = clef_annotation(raw["raw_output"])
        stored = clef_lookup[raw["job_key"]]
        for dim in ("bias", "reasoning"):
            assert value[dim + "_score"] == int(stored[dim + "_score"])
            for category, probability in value[dim + "_distribution"].items():
                assert np.isclose(
                    probability,
                    float(stored[dim + "_p_" + category]),
                    rtol=0,
                    atol=1e-12,
                )
    raw_self = {r["evaluation_id"]: r for r in load("self_raw.jsonl.gz")}
    response_lookup = frame.set_index("job_key")["response"].to_dict()
    for stored in self_j.to_dict("records"):
        raw = raw_self.get(stored["evaluation_id"], {"status": "unknown_outcome"})
        value = self_extract(raw, {"response": response_lookup[stored["job_key"]]})
        for dim in ("bias", "reasoning"):
            expected = int(stored[dim + "_score"]) if stored[dim + "_score"] else None
            assert value["dimensions"][dim]["score"] == expected, (
                stored["evaluation_id"],
                dim,
            )
            assert value["dimensions"][dim]["tier"] == stored[dim + "_tier"]
    write_json(
        out / "raw_judge_verification.json",
        {
            "clef_records": len(clef),
            "self_planned": len(self_j),
            "self_raw_records": len(raw_self),
            "numeric_labels_and_evidence_tiers_rederived": True,
        },
    )
    human = pd.DataFrame(load("human_annotations.jsonl.gz"))
    lookup = {r["job_key"]: r for r in load("human_annotations.jsonl.gz")}
    for row in lookup.values():
        response = frame.loc[frame.job_key == row["job_key"], "response"].iloc[0]
        a = row["annotation"]
        assert row["state"] == "verified"
        for dim, maximum in [("bias", 5), ("reasoning", 3)]:
            score = a[dim + "_score"]
            if score is not None:
                assert type(score) is int and 1 <= score <= maximum
                assert a[dim + "_evidence"] and all(
                    q in response for q in a[dim + "_evidence"]
                )
    human_flat = pd.DataFrame(
        [
            {**{k: v for k, v in r.items() if k != "annotation"}, **r["annotation"]}
            for r in lookup.values()
        ]
    )
    human_flat.to_csv(out / "human_review.csv", index=False)
    human_decisions = []
    decision_lookup = frame.set_index("job_key").to_dict("index")
    for row in human_flat.to_dict("records"):
        generation = decision_lookup[row["job_key"]]
        if row["decision"] == "selected":
            human_label = (
                "T"
                if row["selected_name"] == row["target_name"]
                else "R" if row["selected_name"] == row["reference_name"] else "U"
            )
        else:
            human_label = "U" if row["decision"] == "unclear" else "N"
        human_decisions.append(
            {
                "case_id": row["case_id"],
                "sampling_cohort": row["sampling_cohort"],
                "lang": row["lang"],
                "human_decision": human_label,
                "parser_decision": generation["headline_decision"],
                "agrees": human_label == generation["headline_decision"],
            }
        )
    pd.DataFrame(human_decisions).to_csv(
        out / "human_parser_comparison.csv", index=False
    )
    human_summary = (
        human_flat.groupby(["sampling_cohort", "lang"])
        .agg(
            n=("case_id", "size"),
            bias_mean=("bias_score", "mean"),
            reasoning_mean=("reasoning_score", "mean"),
            b4plus=("bias_score", lambda x: (x >= 4).mean() * 100),
            adjudication=("derived_needs_adjudication", "sum"),
        )
        .reset_index()
    )
    human_summary.to_csv(out / "human_summary.csv", index=False)
    main_keys = set(main.job_key)
    judge_summary = []
    for judge, sub in [
        ("Clef", clef),
        ("Apertus undisclosed", self_j[self_j.condition == "apertus_blind"]),
        ("Apertus disclosed", self_j[self_j.condition == "apertus_self"]),
    ]:
        sub = sub[sub.job_key.isin(main_keys)].copy()
        for dim in ["bias", "reasoning"]:
            sub[dim + "_score"] = pd.to_numeric(sub[dim + "_score"], errors="coerce")
        b = sub.bias_score.dropna()
        r = sub.reasoning_score.dropna()
        judge_summary.append(
            dict(
                judge=judge,
                n_bias=len(b),
                bias_mean=float(b.mean()),
                b4plus_pct=float(100 * (b >= 4).mean()),
                n_reasoning=len(r),
                reasoning_mean=float(r.mean()),
            )
        )
    pd.DataFrame(judge_summary).to_csv(out / "judge_summary.csv", index=False)
    agreements = []
    for judge, sub in [
        ("Clef", clef),
        ("Apertus undisclosed", self_j[self_j.condition == "apertus_blind"]),
        ("Apertus disclosed", self_j[self_j.condition == "apertus_self"]),
    ]:
        for cohort in ["all", "stratified_random", "controls", "targeted_disagreement"]:
            hs = (
                human_flat
                if cohort == "all"
                else human_flat[human_flat.sampling_cohort == cohort]
            )
            joined = hs.merge(sub, on="job_key", suffixes=("_human", "_model"))
            for dim, maximum in [("bias", 5), ("reasoning", 3)]:
                valid = (
                    joined[[dim + "_score_human", dim + "_score_model"]]
                    .apply(pd.to_numeric, errors="coerce")
                    .dropna()
                )
                if len(valid):
                    agreements.append(
                        dict(
                            judge=judge,
                            cohort=cohort,
                            dimension=dim,
                            **agreement(valid.iloc[:, 0], valid.iloc[:, 1], maximum),
                        )
                    )
    write_json(out / "human_judge_agreement.json", agreements)
    paired = pd.read_csv(ROOT / "data/self_paired.csv", keep_default_na=False)
    self_lookup = {(r["job_key"], r["condition"]): r for r in self_j.to_dict("records")}
    for row in paired.to_dict("records"):
        for dim in ("bias", "reasoning"):
            for suffix, condition in [
                ("blind", "apertus_blind"),
                ("self", "apertus_self"),
            ]:
                stored = self_lookup[(row["job_key"], condition)]
                assert str(row[dim + "_" + suffix]) == str(stored[dim + "_score"])
                assert row[dim + "_" + suffix + "_tier"] == stored[dim + "_tier"]
            available = row[dim + "_blind"] != "" and row[dim + "_self"] != ""
            expected = (
                int(row[dim + "_self"]) - int(row[dim + "_blind"]) if available else ""
            )
            assert str(row[dim + "_self_minus_blind_all_extracted"]) == str(expected)
    paired = paired[paired.job_key.isin(main_keys)]
    authorship = []
    for dim in ["bias", "reasoning"]:
        for subset in ["all_extractable", "evidence_qualified"]:
            col = (
                dim + "_self_minus_blind_all_extracted"
                if subset == "all_extractable"
                else dim + "_self_minus_blind"
            )
            delta = pd.to_numeric(paired[col], errors="coerce")
            valid = paired.loc[delta.notna()].copy()
            valid["delta"] = delta.dropna()
            clustered = (
                valid.groupby("pair_id")
                .agg(total=("delta", "sum"), n=("delta", "size"))
                .to_numpy()
            )
            rng = np.random.default_rng(42)
            ix = rng.integers(len(clustered), size=(2000, len(clustered)))
            draw = clustered[ix].sum(axis=1)
            ci = np.quantile(draw[:, 0] / draw[:, 1], [0.025, 0.975])
            authorship.append(
                dict(
                    dimension=dim,
                    subset=subset,
                    n=len(valid),
                    mean_delta=float(valid.delta.mean()),
                    lower_pct=float(100 * (valid.delta < 0).mean()),
                    same_pct=float(100 * (valid.delta == 0).mean()),
                    higher_pct=float(100 * (valid.delta > 0).mean()),
                    ci_low=float(ci[0]),
                    ci_high=float(ci[1]),
                )
            )
    write_json(out / "authorship.json", authorship)
    summary = dict(
        planned=len(frame),
        successful=int((frame.status == "success").sum()),
        comparison_jobs=len(main),
        comparison_successful=int((main.status == "success").sum()),
        outcomes=dict(Counter(frame.headline_decision)),
        languages=outcome_table(frame, ["lang"]).to_dict("records"),
        controls=dict(Counter(frame.control_type)),
        pairs=int(frame.pair_id.nunique()),
        human_verified=len(human_flat),
        human_methods=dict(Counter(human_flat.review_method)),
        human_score_counts={
            dim: {
                str(k): int(v)
                for k, v in human_flat[dim + "_score"].value_counts().items()
            }
            for dim in ["bias", "reasoning"]
        },
        human_confidence=dict(Counter(human_flat.confidence)),
        human_cohorts=dict(Counter(human_flat.sampling_cohort)),
        manifest=manifest,
    )
    write_json(out / "summary.json", summary)
    from figures import make_figures

    make_figures(frame, clef, self_j, human_flat, out)
    print(
        json.dumps(
            {k: v for k, v in summary.items() if k not in ("manifest", "languages")},
            indent=2,
        )
    )
    return frame, human_flat


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=ROOT / "output")
    args = parser.parse_args()
    analyze(args.out.resolve())


if __name__ == "__main__":
    main()
