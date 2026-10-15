"""Rebuild the compact report panel from verified original-format measurements."""

import argparse
import json
from pathlib import Path
import shutil

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
RUN=ROOT/"supplementary/whitebox/evidence/natural-gender-20261015-v1"


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write-docs",action="store_true")
    args=parser.parse_args()
    out=ROOT/"output/figures"
    out.mkdir(parents=True,exist_ok=True)
    lens=json.loads((RUN/"analysis/name_preference_by_layer.json").read_text())
    scan=[json.loads(s) for s in (RUN/"validation_scan.jsonl").read_text(encoding="utf-8").splitlines()]
    coarse=[0,9,19,29,39,49,59,69,79]
    values=[]
    for site in ["cues","answer"]:
        values.append([sum(bool(r["donor_name_restored"]) for r in scan if r["condition"]=="counterfactual" and r["site"]==site and r["layer"]==layer) for layer in coarse])
    plt.rcParams.update({"font.size":8.5,"axes.spines.top":False,"axes.spines.right":False,"pdf.fonttype":42})
    fig,ax=plt.subplots(1,2,figsize=(7.05,2.25),layout="constrained",gridspec_kw={"width_ratios":[1,1.12]})
    x=np.arange(1,81)
    ax[0].plot(x,lens["mean"],color="#bf6835",linewidth=1.5)
    ax[0].fill_between(x,lens["ci_low"],lens["ci_high"],color="#bf6835",alpha=.18)
    ax[0].axhline(0,color="#777777",linewidth=.6)
    ax[0].set(title="(a) Name preference becomes visible",xlabel="Decoder block",ylabel="Paired gender effect on logits",xlim=(1,80))
    ax[1].imshow(values,aspect="auto",vmin=0,vmax=4,cmap="YlGnBu")
    for a in range(2):
        for b in range(9):
            ax[1].text(b,a,str(values[a][b]),ha="center",va="center",color="white" if values[a][b]>=3 else "#253644",fontsize=8)
    ax[1].set(title="(b) Full-state swaps: donor name restored",xticks=range(9),xticklabels=[v+1 for v in coarse],yticks=[0,1],yticklabels=["Gender cues","Before answer"],xlabel="Patched decoder block")
    for extension in ["pdf","png"]:
        path=out/("whitebox_summary."+extension)
        kwargs={"metadata":{"CreationDate":None,"ModDate":None}} if extension=="pdf" else {"dpi":220}
        fig.savefig(path,**kwargs)
        if args.write_docs:shutil.copyfile(path,ROOT/"docs/figures"/path.name)
    plt.close(fig)
    print("Rebuilt white-box report panel: paired logits and exact 4-case validation counts")


if __name__=="__main__":main()
