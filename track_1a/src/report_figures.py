"""Compact report panels for quantitative claims, using unchanged audit data.

Called by figures.make_figures during offline reproduction. To refresh just
these panels from existing generated tables: python src/report_figures.py.
"""

from pathlib import Path
from decimal import Decimal, ROUND_HALF_UP
import gzip
import json

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
LANGS = ["en", "fr", "ar"]
NAMES = ["English", "French", "Arabic"]
COLORS = {"T": "#c46a2a", "R": "#234b72", "N": "#47816f", "U": "#927da5"}


def save(fig, folder, name):
    fig.savefig(folder / (name + ".pdf"), bbox_inches="tight")
    fig.savefig(folder / (name + ".png"), dpi=300, bbox_inches="tight")
    plt.close(fig)


def make_report_figures(frame, human, out, self_j=None):
    folder = out / "figures"
    folder.mkdir(exist_ok=True)
    plt.rcParams.update(
        {
            "font.family": "serif",
            "font.serif": ["STIXGeneral", "DejaVu Serif"],
            "font.size": 8,
            "axes.labelsize": 7.5,
            "xtick.labelsize": 7,
            "ytick.labelsize": 7.5,
            "axes.linewidth": 0.6,
            "axes.spines.top": False,
            "axes.spines.right": False,
            "pdf.fonttype": 42,
        }
    )

    # Denominators differ deliberately: planned controls vs successful outputs.
    fig, axs = plt.subplots(1, 3, figsize=(7.05, 1.65))
    x = np.arange(3)
    for offset, kind, label, color in [
        (-0.17, "no_identity", "Identity-free", "#47816f"),
        (0.17, "same_identity", "Same identity", "#b4cdc3"),
    ]:
        groups = [
            frame[(frame.lang == lang) & (frame.control_type == kind)] for lang in LANGS
        ]
        values = [100 * (g.headline_decision == "N").mean() for g in groups]
        axs[0].bar(x + offset, values, 0.32, color=color, label=label)
        for pos, v in zip(x + offset, values):
            axs[0].text(pos, v + 0.45, f"{v:.1f}", ha="center", fontsize=6.8)
    axs[0].set_ylim(0, 19)
    axs[0].set_ylabel("Planned control calls (%)")
    axs[0].set_title("(a) Neutral / refusal / information / neither", fontsize=8)
    axs[0].legend(frameon=False, fontsize=6.7, loc="upper right")
    groups = [
        frame[(frame.lang == lang) & (frame.control_type == "no_identity")]
        for lang in LANGS
    ]
    counts = [int((g.picked_slot == "A").sum()) for g in groups]
    values = [100 * c / len(g) for c, g in zip(counts, groups)]
    axs[1].bar(x, values, 0.55, color="#63707d")
    for pos, v, c in zip(x, values, counts):
        axs[1].text(pos, v + 2, f"{c}/130", ha="center", fontsize=7)
    axs[1].axhline(50, color="#888888", ls=":", lw=0.7)
    axs[1].set_ylim(0, 100)
    axs[1].set_ylabel("Planned identity-free calls (%)")
    axs[1].set_title("(b) First-position choices", fontsize=8)
    groups = [
        frame[(frame.lang == lang) & (frame.status == "success")] for lang in LANGS
    ]
    values = [100 * (g.headline_decision == "U").mean() for g in groups]
    axs[2].bar(x, values, 0.55, color=COLORS["U"])
    for pos, v in zip(x, values):
        axs[2].text(pos, v + 0.15, f"{v:.2f}%", ha="center", fontsize=7)
    axs[2].set_ylim(0, 6.5)
    axs[2].set_ylabel("Successful outputs (%)")
    axs[2].set_title("(c) Unclear decision extraction", fontsize=8)
    for ax in axs:
        ax.set_xticks(x, ["EN", "FR", "AR"])
    fig.tight_layout(w_pad=1.1)
    save(fig, folder, "controls_and_coverage")

    # Exact count bars directly visualize the paragraph about national-origin loans.
    sub = frame[
        (frame.control_type == "none")
        & (frame.axis == "national_origin")
        & (frame.scenario == "loan")
    ]
    groups = [sub[sub.lang == lang] for lang in LANGS]
    fig, ax = plt.subplots(figsize=(3.35, 1.65))
    left = np.zeros(3)
    for label, color in COLORS.items():
        counts = np.array([int((g.headline_decision == label).sum()) for g in groups])
        ax.barh(x, counts, left=left, height=0.55, color=color, label=label)
        if label in {"T", "R"}:
            for y, start, c in zip(x, left, counts):
                ax.text(
                    start + c / 2,
                    y,
                    str(c),
                    ha="center",
                    va="center",
                    color="white",
                    fontsize=8,
                )
        left += counts
    ax.set_yticks(x, NAMES)
    ax.invert_yaxis()
    ax.set_xlim(0, 140)
    ax.set_xticks([0, 35, 70, 105, 140])
    ax.set_xlabel("Number of planned calls (140 per language)")
    ax.legend(
        frameon=False,
        ncol=4,
        loc="upper center",
        bbox_to_anchor=(0.5, 1.33),
        fontsize=7,
        labels=["Target", "Reference", "Neutral", "Unclear"],
    )
    fig.tight_layout(rect=[0, 0, 1, 0.94])
    save(fig, folder, "origin_loan_counts")

    # Keep random, controls and selected disagreements visible as distinct cohorts.
    fig, axs = plt.subplots(
        1, 3, figsize=(7.05, 1.85), gridspec_kw={"width_ratios": [1, 0.9, 1.55]}
    )
    cohort_colors = ["#234b72", "#b4cdc3", "#d6b58a"]
    cohorts = ["stratified_random", "controls", "targeted_disagreement"]
    for ax, dim, maximum, title in zip(
        axs[:2],
        ["bias", "reasoning"],
        [5, 3],
        ["(a) Reviewed bias labels", "(b) Reviewed reasoning labels"],
    ):
        bottom = np.zeros(maximum)
        for cohort, color in zip(cohorts, cohort_colors):
            values = (
                human.loc[human.sampling_cohort == cohort, dim + "_score"]
                .value_counts()
                .reindex(range(1, maximum + 1), fill_value=0)
                .to_numpy()
            )
            ax.bar(np.arange(maximum), values, bottom=bottom, color=color, width=0.65)
            bottom += values
        for pos, v in enumerate(bottom):
            ax.text(pos, v + 2, str(int(v)), ha="center", fontsize=7)
        ax.set_xticks(
            np.arange(maximum),
            [("B" if dim == "bias" else "R") + str(i) for i in range(1, maximum + 1)],
        )
        ax.set_ylim(0, max(bottom) * 1.19)
        ax.set_ylabel("Reviewed cases")
        ax.set_title(title, fontsize=8)
    agreements = pd.DataFrame(
        json.loads((out / "human_judge_agreement.json").read_text())
    )
    agreements = agreements[agreements.cohort == "stratified_random"]
    judges = ["Clef", "Apertus undisclosed", "Apertus disclosed"]
    for offset, dim, color in [
        (-0.16, "bias", COLORS["T"]),
        (0.16, "reasoning", COLORS["R"]),
    ]:
        values = [
            float(
                agreements[
                    (agreements.judge == j) & (agreements.dimension == dim)
                ].exact_pct.iloc[0]
            )
            for j in judges
        ]
        axs[2].barh(x + offset, values, 0.3, color=color, label=dim.capitalize())
        for y, v in zip(x + offset, values):
            rounded = Decimal(str(v)).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)
            axs[2].text(v + 1, y, str(rounded), va="center", fontsize=7)
    axs[2].set_yticks(x, ["Clef", "Apertus\nundisclosed", "Apertus\ndisclosed"])
    axs[2].invert_yaxis()
    axs[2].set_xlim(0, 102)
    axs[2].set_xlabel("Exact agreement (%)")
    axs[2].set_title("(c) Random-audit agreement", fontsize=8)
    handles, labels = axs[2].get_legend_handles_labels()
    fig.legend(
        handles,
        labels,
        ncol=2,
        frameon=False,
        loc="upper right",
        bbox_to_anchor=(0.99, 1.075),
        fontsize=7,
    )
    from matplotlib.patches import Patch

    fig.legend(
        [Patch(color=c) for c in cohort_colors],
        ["Random (144)", "Controls (24)", "Targeted (24)"],
        ncol=3,
        frameon=False,
        loc="upper left",
        bbox_to_anchor=(0.025, 1.075),
        fontsize=7,
    )
    fig.tight_layout(rect=[0, 0.04, 1, 0.91], w_pad=1.1)
    save(fig, folder, "human_audit")

    auth = pd.DataFrame(json.loads((out / "authorship.json").read_text()))
    auth = auth[auth.subset == "all_extractable"].set_index("dimension")
    bias = auth.loc["bias"]
    fig, axs = plt.subplots(
        1, 3, figsize=(7.05, 1.65), gridspec_kw={"width_ratios": [1, 1.05, 1]}
    )
    vals = [bias.same_pct, bias.lower_pct, bias.higher_pct]
    axs[0].barh(x, vals, color=["#63707d", "#47816f", "#c46a2a"], height=0.55)
    for y, v in zip(x, vals):
        axs[0].text(
            v - 2 if v > 80 else v + 2,
            y,
            f"{v:.2f}%",
            va="center",
            fontsize=7,
            color="white" if v > 80 else "#222222",
            ha="right" if v > 80 else "left",
        )
    axs[0].set_yticks(x, ["Same", "Lower", "Higher"])
    axs[0].invert_yaxis()
    axs[0].set_xlim(0, 105)
    axs[0].set_xlabel("Paired main responses (%)")
    axs[0].set_title("(a) Bias score after disclosure", fontsize=8)
    axs[1].axvline(0, color="#888888", ls=":", lw=0.7)
    for y, dim, color in [(0, "bias", COLORS["T"]), (1, "reasoning", COLORS["R"])]:
        r = auth.loc[dim]
        axs[1].errorbar(
            r.mean_delta,
            y,
            xerr=[[r.mean_delta - r.ci_low], [r.ci_high - r.mean_delta]],
            fmt="o",
            color=color,
            capsize=3,
            ms=4,
            lw=1,
        )
        axs[1].text(
            r.mean_delta, y - 0.22, f"{r.mean_delta:+.5f}", ha="center", fontsize=7
        )
    axs[1].set_yticks([0, 1], ["Bias", "Reasoning"])
    axs[1].set_ylim(1.5, -0.55)
    axs[1].set_xlim(-0.003, 0.016)
    axs[1].set_xticks([0, 0.005, 0.01, 0.015], ["0", ".005", ".010", ".015"])
    axs[1].set_xlabel("Mean score change (disclosed - undisclosed)", fontsize=6.8)
    axs[1].set_title("(b) Change with 95% bootstrap CI", fontsize=8)
    if self_j is None:
        with gzip.open(
            ROOT / "data/self_judgments.jsonl.gz", "rt", encoding="utf-8"
        ) as stream:
            self_j = pd.DataFrame(json.loads(line) for line in stream)
    total = len(self_j)
    both_numeric = (
        self_j[["bias_score", "reasoning_score"]]
        .apply(pd.to_numeric, errors="coerce")
        .notna()
        .all(axis=1)
    )
    both_evidence = (
        self_j[["bias_tier", "reasoning_tier"]].eq("evidence_backed").all(axis=1)
    )
    coverage = [
        int(self_j.original_status.eq("success").sum()),
        int(both_numeric.sum()),
        int(both_evidence.sum()),
    ]
    (out / "report_figure_coverage.json").write_text(
        json.dumps(
            {
                "planned": total,
                "strict": coverage[0],
                "both_numeric": coverage[1],
                "both_evidence": coverage[2],
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    axs[2].barh(
        x,
        [100 * c / total for c in coverage],
        height=0.55,
        color=["#b4cdc3", "#234b72", "#47816f"],
    )
    for y, c in zip(x, coverage):
        axs[2].text(100 * c / total + 1, y, f"{c:,}", va="center", fontsize=7)
    axs[2].set_yticks(x, ["Strict", "Numeric", "Evidence"])
    axs[2].invert_yaxis()
    axs[2].set_xlim(0, 132)
    axs[2].set_xticks([0, 50, 100])
    axs[2].set_xlabel("All planned self-evaluations (%)")
    axs[2].set_title("(c) Both-dimension coverage", fontsize=8)
    fig.tight_layout(w_pad=1.25)
    save(fig, folder, "authorship_and_coverage")


if __name__ == "__main__":
    out = ROOT / "output"
    make_report_figures(
        pd.read_csv(out / "decisions.csv", keep_default_na=False),
        pd.read_csv(out / "human_review.csv", keep_default_na=False),
        out,
    )
