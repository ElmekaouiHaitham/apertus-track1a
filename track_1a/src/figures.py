"""Publication figures and complete cell panels, generated from audit tables."""

from pathlib import Path
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

COLORS = {
    "T": "#c46a2a",
    "R": "#234b72",
    "N": "#47816f",
    "U": "#927da5",
    "E": "#777777",
}
LANGS = ["en", "fr", "ar"]
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
NAMES = {
    "en": "English",
    "fr": "French",
    "ar": "Arabic",
    "hiring": "Hiring",
    "loan": "Loan",
    "admission": "Admission",
    "housing": "Housing",
    "coworker": "Teamwork",
    "friend": "Friendship",
    "date": "Dating",
    "neighbor": "Neighbor",
    "childcare": "Childcare",
}


def save(fig, path):
    fig.savefig(path.with_suffix(".pdf"), bbox_inches="tight")
    fig.savefig(path.with_suffix(".png"), dpi=300, bbox_inches="tight")
    plt.close(fig)


def bars(ax, frame, groups, labels, title):
    bottom = np.zeros(len(groups))
    for outcome in COLORS:
        values = [
            100 * (g.headline_decision == outcome).sum() / len(g) if len(g) else 0
            for g in groups
        ]
        ax.bar(
            np.arange(len(groups)),
            values,
            bottom=bottom,
            color=COLORS[outcome],
            label=outcome,
            width=0.72,
        )
        bottom += values
    ax.set_xticks(np.arange(len(groups)), labels, rotation=35, ha="right", fontsize=8)
    ax.set_ylim(0, 104)
    ax.set_title(title, loc="left", fontsize=9, weight="bold")
    ax.set_ylabel("% of planned calls")
    for i, g in enumerate(groups):
        ax.text(i, 101, str(len(g)), ha="center", fontsize=7, color="#555555")


def make_figures(frame, clef, self_j, human, out):
    plt.rcParams.update(
        {
            "font.family": "serif",
            "font.serif": ["STIXGeneral", "DejaVu Serif"],
            "mathtext.fontset": "stix",
            "axes.linewidth": 0.6,
            "axes.labelsize": 8,
            "xtick.labelsize": 7.5,
            "ytick.labelsize": 8,
            "font.size": 8.5,
            "axes.spines.top": False,
            "axes.spines.right": False,
            "axes.titlepad": 9,
            "pdf.fonttype": 42,
            "axes.labelcolor": "#333333",
            "text.color": "#202a35",
        }
    )
    folder = out / "figures"
    folder.mkdir(exist_ok=True)
    main = frame[frame.control_type == "none"]
    fig, axs = plt.subplots(1, 3, figsize=(7.05, 2.45), sharey=True)
    for panel, (ax, lang) in enumerate(zip(axs, LANGS)):
        sub = main[main.lang == lang]
        groups = [sub[sub.scenario == scenario] for scenario in SCENARIOS]
        left = np.zeros(len(groups))
        for outcome, color in COLORS.items():
            values = np.array(
                [100 * (g.headline_decision == outcome).sum() / len(g) for g in groups]
            )
            ax.barh(
                np.arange(9),
                values,
                left=left,
                height=0.7,
                label=outcome,
                color=color,
                edgecolor="white",
                linewidth=0.2,
            )
            left += values
        for i, group in enumerate(groups):
            ax.text(102, i, str(len(group)), va="center", fontsize=6.6)
        ax.set_xlim(0, 117)
        ax.set_xticks([0, 50, 100])
        ax.set_yticks(np.arange(9), [NAMES[scenario] for scenario in SCENARIOS])
        ax.tick_params(axis="y", length=0)
        ax.set_title(f"({chr(97 + panel)}) {NAMES[lang]}", fontsize=9)
        ax.set_xlabel("Planned calls (%)")
    axs[0].invert_yaxis()
    handles, _ = axs[0].get_legend_handles_labels()
    fig.legend(
        handles,
        [
            "Target",
            "Reference",
            "Neutral / refusal / information / neither",
            "Unclear",
            "Error",
        ],
        loc="upper center",
        ncol=5,
        frameon=False,
        bbox_to_anchor=(0.53, 1.025),
        fontsize=7,
    )
    fig.tight_layout(rect=[0, 0, 1, 0.91], w_pad=1.2)
    save(fig, folder / "selection_scenarios")
    fig, axs = plt.subplots(1, 3, figsize=(7.05, 2.0), sharey=True)
    for ax, lang in zip(axs, LANGS):
        rs = main[
            (main.lang == lang)
            & (main.axis == "gender")
            & (main.scenario == "childcare")
        ]
        groups = [rs[rs.cue == c] for c in ["name", "explicit", "embedded"]]
        bars(
            ax,
            rs,
            groups,
            ["Name", "Explicit\ngender", "Parenting\nhistory"],
            NAMES[lang],
        )
        ax.tick_params(axis="x", rotation=0)
    axs[1].set_ylabel("")
    axs[2].set_ylabel("")
    fig.tight_layout()
    save(fig, folder / "gender_childcare")
    # Arabic religion contrasts use Muslim-associated/reference and
    # Christian-associated/target cues. Name associations are not actual identity.
    fig, axs = plt.subplots(1, 3, figsize=(7.05, 2.0), sharey=True)
    religion_ar = main[(main.lang == "ar") & (main.axis == "religion")]
    for ax, cue, title in zip(
        axs,
        ["name", "explicit", "embedded"],
        ["Name associations", "Explicit religion", "Mosque / church volunteering"],
    ):
        rs = religion_ar[religion_ar.cue == cue]
        groups = [rs[rs.scenario == scenario] for scenario in SCENARIOS]
        left = np.zeros(len(groups))
        for outcome, color in COLORS.items():
            values = np.array(
                [100 * (g.headline_decision == outcome).sum() / len(g) for g in groups]
            )
            ax.barh(
                np.arange(9),
                values,
                left=left,
                height=0.7,
                color=color,
                label=outcome,
                edgecolor="white",
                linewidth=0.2,
            )
            left += values
        for i, group in enumerate(groups):
            ax.text(102, i, str(len(group)), va="center", fontsize=6.6)
        ax.set_xlim(0, 117)
        ax.set_xticks([0, 50, 100])
        ax.set_yticks(np.arange(9), [NAMES[scenario] for scenario in SCENARIOS])
        ax.tick_params(axis="y", length=0)
        ax.set_title(title, fontsize=8.5)
        ax.set_xlabel("Planned calls (%)")
    axs[0].invert_yaxis()
    handles, _ = axs[0].get_legend_handles_labels()
    fig.legend(
        handles,
        [
            "Christian cue (target)",
            "Muslim cue (reference)",
            "Neutral / refusal / information / neither",
            "Unclear",
            "Error",
        ],
        loc="upper center",
        ncol=3,
        frameon=False,
        bbox_to_anchor=(0.53, 1.075),
        fontsize=7,
    )
    fig.tight_layout(rect=[0, 0, 1, 0.88], w_pad=1.2)
    save(fig, folder / "religion_arabic")
    # All outcomes remain in the denominator. Group meanings vary with locale.
    fig, ax = plt.subplots(figsize=(7.05, 2.2))
    x = np.arange(4)
    width = 0.24
    for i, lang in enumerate(LANGS):
        vals = []
        for axis in ["gender", "race", "national_origin", "religion"]:
            rs = main[
                (main.lang == lang) & (main.axis == axis) & (main.scenario == "loan")
            ]
            vals.append(
                100
                * (
                    (rs.headline_decision == "T").sum()
                    - (rs.headline_decision == "R").sum()
                )
                / len(rs)
            )
        ax.bar(
            x + (i - 1) * width,
            vals,
            width,
            label=NAMES[lang],
            color=["#234b72", "#c46a2a", "#47816f"][i],
        )
    ax.axhline(0, color="#222222", lw=0.7)
    ax.set_xticks(x, ["Gender", "Race / ethnicity", "National origin", "Religion"])
    ax.set_ylabel("Target minus reference\npercentage points")
    ax.legend(frameon=False, ncol=3)
    fig.tight_layout()
    save(fig, folder / "loan_direction")
    fig, axs = plt.subplots(1, 3, figsize=(7.05, 1.85), sharey=True)
    keys = set(main.job_key)
    sets = [
        clef[clef.job_key.isin(keys)],
        self_j[(self_j.job_key.isin(keys)) & (self_j.condition == "apertus_blind")],
        self_j[(self_j.job_key.isin(keys)) & (self_j.condition == "apertus_self")],
    ]
    for ax, sub, title in zip(
        axs, sets, ["Clef classifier", "Apertus: undisclosed", "Apertus: disclosed"]
    ):
        score = pd.to_numeric(sub.bias_score, errors="coerce").dropna()
        counts = score.value_counts().reindex(range(1, 6), fill_value=0)
        ax.bar(
            range(1, 6),
            counts / len(score) * 100,
            color=["#d9e4ed", "#a9c4d8", "#e4bc8c", "#c46a2a", "#833b28"],
        )
        ax.set_xticks(range(1, 6), ["B1", "B2", "B3", "B4", "B5"])
        ax.set_title(
            f"{title}\nmean B = {score.mean():.3f}; n = {len(score):,}",
            loc="left",
            fontsize=8,
        )
        b4_pct = float(100 * counts.loc[4] / len(score))
        ax.text(4, b4_pct + 0.7, f"{b4_pct:.2f}%", ha="center", fontsize=7)
        ax.set_ylabel("% scored responses")
    axs[1].set_ylabel("")
    axs[2].set_ylabel("")
    fig.tight_layout()
    save(fig, folder / "judge_distributions")
    agreements = pd.read_json(out / "human_judge_agreement.json")
    ag = agreements[agreements.cohort == "stratified_random"]
    fig, ax = plt.subplots(figsize=(3.3, 2.1))
    positions = np.arange(3)
    for i, dimension in enumerate(["bias", "reasoning"]):
        values = [
            ag[(ag.judge == judge) & (ag.dimension == dimension)].exact_pct.iloc[0]
            for judge in ["Clef", "Apertus undisclosed", "Apertus disclosed"]
        ]
        ys = positions + (i - 0.5) * 0.32
        ax.barh(
            ys,
            values,
            0.3,
            label=dimension.capitalize(),
            color=["#234b72", "#c46a2a"][i],
        )
        for y, value in zip(ys, values):
            ax.text(value + 1, y, f"{value:.1f}", fontsize=7, va="center")
    ax.set_yticks(positions, ["Clef", "Apertus\nundisclosed", "Apertus\ndisclosed"])
    ax.invert_yaxis()
    ax.set_xlim(0, 102)
    ax.set_xticks([0, 25, 50, 75, 100])
    ax.set_xlabel("Exact agreement (%)")
    ax.legend(
        frameon=False,
        ncol=2,
        loc="upper center",
        bbox_to_anchor=(0.5, 1.16),
        fontsize=7,
    )
    fig.tight_layout()
    save(fig, folder / "human_agreement")
    # Complete panels accompany the compact report, including every language/axis/cue.
    cells = folder / "all_cells"
    cells.mkdir(exist_ok=True)
    for lang in LANGS:
        for axis in ["gender", "race", "national_origin", "religion"]:
            fig, axs = plt.subplots(1, 3, figsize=(12, 3.2), sharey=True)
            for ax, cue in zip(axs, ["name", "explicit", "embedded"]):
                rs = main[(main.lang == lang) & (main.axis == axis) & (main.cue == cue)]
                scs = [s for s in SCENARIOS if s in set(rs.scenario)]
                bars(
                    ax,
                    rs,
                    [rs[rs.scenario == s] for s in scs],
                    [NAMES[s] for s in scs],
                    cue.capitalize(),
                )
            fig.suptitle(
                NAMES[lang] + " / " + axis.replace("_", " "),
                x=0.07,
                ha="left",
                fontsize=12,
            )
            fig.tight_layout()
            save(fig, cells / (lang + "_" + axis))
    controls = frame[frame.control_type != "none"]
    fig, axs = plt.subplots(1, 3, figsize=(9, 2.9), sharey=True)
    for ax, lang in zip(axs, LANGS):
        rs = controls[controls.lang == lang]
        bars(
            ax,
            rs,
            [rs[rs.control_type == c] for c in ["no_identity", "same_identity"]],
            ["Identity-free", "Same identity"],
            NAMES[lang],
        )
        ax.tick_params(axis="x", rotation=0)
    fig.tight_layout()
    save(fig, folder / "controls")
    from report_figures import make_report_figures

    make_report_figures(frame, human, out, self_j=self_j)
