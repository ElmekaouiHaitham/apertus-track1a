"""Offline verification/figures for a completed small white-box run.

Only NumPy/matplotlib and the existing choice parser are needed; no weights,
GPU, cloud credentials or Transformers. Raw results remain unchanged.
"""

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parents[1] / "src"))
from choice_parser import parse_row


def read_jsonl(path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_json(path, value):
    path.write_text(json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False)+"\n",encoding="utf-8")


def interval(rows,field):
    families = sorted({r["family_id"] for r in rows})
    array = np.asarray([[sum(r[field] for r in rows if r["family_id"]==f),
                         sum(r["family_id"]==f for r in rows)] for f in families])
    if not families:
        return dict(mean=None,ci_low=None,ci_high=None,n_families=0)
    rng = np.random.default_rng(42)
    samples = array[rng.integers(len(array),size=(2000,len(array)))].sum(1)
    lo,hi = np.quantile(samples[:,0]/samples[:,1],[.025,.975])
    return dict(mean=float(array[:,0].sum()/array[:,1].sum()),ci_low=float(lo),ci_high=float(hi),n_families=len(families))


def analyze(run):
    manifest = json.loads((run / "manifest.json").read_text())
    for name,expected in manifest["files"].items():
        if Path(name).name!=name or hashlib.sha256((run/name).read_bytes()).hexdigest()!=expected:
            raise ValueError("Evidence file hash mismatch: "+name)
    design = json.loads((run / "design.json").read_text(encoding="utf-8"))
    serialized = json.dumps(design["records"],ensure_ascii=False,sort_keys=True,separators=(",",":"))
    if hashlib.sha256(serialized.encode()).hexdigest()!=design["manifest"]["design_sha256"]:
        raise ValueError("Design hash mismatch")
    rows = {r["id"]:r for r in design["records"]}
    baseline_list = read_jsonl(run / "baseline.jsonl")
    baseline = {r["id"]:r for r in baseline_list}
    if len(baseline_list)!=168 or set(baseline)!=set(rows):
        raise ValueError("Expected all 168 baseline records without duplicate IDs")
    scan = read_jsonl(run / "validation_scan.jsonl")
    interventions = read_jsonl(run / "interventions.jsonl")
    transfer = read_jsonl(run / "transfer.jsonl")
    selection = json.loads((run / "selection.json").read_text())
    if len(scan)!=144 or len(interventions)!=344 or len(transfer)!=48:
        raise ValueError("Incomplete scheduled interventions/transfer")
    if any(rows[r["id"]]["split"]!="validation" for r in scan):
        raise ValueError("Layer scan leaked outside validation")
    candidates = []
    for layer in design["manifest"]["coarse_layers"]:
        if layer==79:
            continue
        candidates.append((np.mean([r["signed_transport"] for r in scan if r["layer"]==layer and r["site"]=="answer"]),layer))
    expected_layer = max(candidates,key=lambda x:(x[0],-x[1]))[1]
    if expected_layer!=selection["layer"] or selection["site"]!="answer":
        raise ValueError("Selection rule mismatch")
    if any(rows[x]["split"]!="train" for x in selection["direction_fit_ids"]):
        raise ValueError("Direction fitting leaked outside training")
    for record in baseline_list+interventions+transfer:
        for key in ["margin","p_a","p_b","ab_mass"]:
            if not np.isfinite(record[key]):
                raise ValueError("Non-finite measurement")
        if abs(record["p_a"]+record["p_b"]-record["ab_mass"])>1e-6:
            raise ValueError("A/B probability mismatch")
    for record in interventions:
        if rows[record["id"]]["split"]!="test":
            raise ValueError("Confirmation contains a non-test record")
        if abs(record["delta_margin"]-(record["margin"]-baseline[record["id"]]["margin"]))>1e-6:
            raise ValueError("Intervention contrast mismatch")
        if record["condition"]=="noop" and abs(record["delta_margin"])>1e-5:
            raise ValueError("Self patch changed held-out logits")
    if len({(r["id"],r["condition"]) for r in interventions})!=len(interventions):
        raise ValueError("Duplicate test condition")
    effects = []
    for task in ["childcare","coworker","merit","same_identity"]:
        for condition in sorted({r["condition"] for r in interventions if r["scenario"]==task}):
            selected = [dict(r) for r in interventions if r["scenario"]==task and r["condition"]==condition]
            for r in selected:
                r["female_margin_change"] = r["delta_margin"]*(1 if r["female_a"] else -1) if r["female_a"] is not None else r["delta_margin"]
                r["absolute_margin_change"] = abs(r["delta_margin"])
            effects.append(dict(scenario=task,condition=condition,n=len(selected),
                         female_margin_change=interval(selected,"female_margin_change") if task!="same_identity" else None,
                         absolute_margin_change=interval(selected,"absolute_margin_change"),
                         signed_transport=interval(selected,"signed_transport") if task in ["childcare","coworker"] else None,
                         preferred_slot_flips=sum(r["preferred_slot_flip"] for r in selected),
                         female_preferred_count=sum((r["margin"]>0)==bool(r["female_a"]) for r in selected) if task!="same_identity" else None,
                         top_is_ab_count=sum(r["top_is_ab"] for r in selected),
                         merit_preferred_count=sum(r["preferred_slot"]==r["expected_merit_slot"] for r in selected) if task=="merit" else None))
    out = run / "analysis"
    out.mkdir(exist_ok=True)
    write_json(out / "effects.json",effects)
    train = [r for r in design["records"] if r["scenario"]=="childcare" and r["split"]=="train"]
    groups = sorted({r["family_id"] for r in train})
    permutation = dict(zip(groups,np.random.default_rng(42).permutation(groups)))
    train_labels = {(r["family_id"],r["order"],r["female_a"]):int(baseline[r["id"]]["margin"]>0) for r in train}
    changed = sum(train_labels[r["family_id"],r["order"],r["female_a"]] !=
                  train_labels[permutation[r["family_id"]],r["order"],r["female_a"]] for r in train)
    write_json(out / "probe_control_check.json",dict(decision_null_changed_training_labels=changed,
        n_training_labels=len(train),decision_null_label_change_fraction=changed/len(train),
        interpretation="Decision readout is descriptive and may recover gender/position. This permutation changes few labels and is a weak negative control; it does not establish an independent decision representation."))
    # Preserve parser uncertainty and offer complete pairs for human review.
    generations = read_jsonl(run / "generations.jsonl")
    if len(generations)!=32 or len({(r["id"],r["condition"]) for r in generations})!=32:
        raise ValueError("Expected 16 complete before/after pairs")
    parsed = []
    for generation in generations:
        row = rows[generation["id"]]
        female_a = bool(row["female_a"])
        source = dict(task="choice",status="success",lang="en",response=generation["response"],
                      reference_name=row["names"][1 if female_a else 0],
                      target_name=row["names"][0 if female_a else 1],
                      target_slot="A" if female_a else "B",prompt=row["prompt"])
        parsed.append(dict(id=row["id"],condition=generation["condition"],family_id=row["family_id"],
                           truncated=generation["truncated"],**parse_row(source)))
    write_json(out / "generation_decisions.json",parsed)
    casebook = ["# Original-style answers for supplementary review", "",
                "Greedy public-checkpoint generations; no human B/R ratings have been entered by this analysis. "
                "Read each complete answer, including disclaimers. Parser decisions are fallible; truncated outputs remain flagged.", ""]
    for row in design["records"]:
        pair = [r for r in generations if r["id"]==row["id"]]
        if not pair:
            continue
        casebook.extend([f"## {row['id']}", "", "**Prompt**", "", row["prompt"], ""])
        for record in pair:
            decision = next(p for p in parsed if p["id"]==row["id"] and p["condition"]==record["condition"])
            casebook.extend([f"**{record['condition']}** — parser {decision['headline_decision']}; "
                             f"truncated={record['truncated']}","",record["response"],""])
    (out / "REVIEW_CASEBOOK.md").write_text("\n".join(casebook),encoding="utf-8")
    plot(run,out,scan,effects,baseline,rows)
    files = [p for p in run.glob("*") if p.is_file() and p.name!="manifest.json"]
    hashes = {p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(files)}
    write_json(out / "verification.json",dict(design_hash_verified=True,n_baseline=168,n_validation_patches=144,
               n_test_interventions=344,n_transfer=48,n_generations=32,selected_layer=expected_layer,
               weight_proof="../../preflight.json",files=hashes))
    summary = {condition:dict(Counter(r["headline_decision"] for r in parsed if r["condition"]==condition)) for condition in ["baseline","gender_erasure"]}
    write_json(out / "generation_summary.json",summary)
    print(json.dumps(dict(selected_layer=expected_layer,generation_decisions=summary,verification="passed"),indent=2))


def plot(run,out,scan,effects,baseline,rows):
    probes = json.loads((run / "probes.json").read_text())
    plt.rcParams.update({"font.size":9,"axes.spines.top":False,"axes.spines.right":False,"pdf.fonttype":42})
    fig,axes = plt.subplots(3,2,figsize=(11,10),layout="constrained")
    for label,color,title in [("female_in_A","#245675","Gender assignment"),("ab_margin_sign","#bf6835","A/B margin sign")]:
        selected = [r for r in probes if r["label"]==label and not r["shuffled"] and r.get("split")=="test" and r["status"]=="scored"]
        if selected:
            axes[0,0].plot([r["layer"]+1 for r in selected],[r["accuracy"] for r in selected],color=color,label=title)
        null = [r for r in probes if r["label"]==label and r["shuffled"] and r.get("split")=="test" and r["status"]=="scored"]
        # The decision-label family permutation can be non-informative when
        # every training family has the same choice pattern; report it in JSON
        # but do not portray it as a successful negative control in the figure.
        if null and label=="female_in_A":
            axes[0,0].plot([r["layer"]+1 for r in null],[r["accuracy"] for r in null],color=color,alpha=.4,linestyle=":",label="Gender labels shuffled")
    axes[0,0].set(title="Held-out linear readouts (4 name families)",xlabel="Decoder block (1-based)",ylabel="Accuracy",ylim=(0,1.03))
    axes[0,0].legend(fontsize=8)
    coarse = sorted({r["layer"] for r in scan})
    values = [[np.mean([r["signed_transport"] for r in scan if r["layer"]==layer and r["site"]==site]) for layer in coarse] for site in ["cues","answer"]]
    bound = max(float(np.abs(values).max()),.01)
    image = axes[0,1].imshow(values,aspect="auto",cmap="RdBu_r",vmin=-bound,vmax=bound)
    axes[0,1].set(yticks=[0,1],yticklabels=["Gender endpoints","Last prompt token"],xticks=range(len(coarse)),xticklabels=[l+1 for l in coarse],xlabel="Decoder block (1-based)",title="Validation patch transport (2 name families)")
    fig.colorbar(image,ax=axes[0,1],label="Signed movement toward donor margin")
    conditions = ["noop","counterfactual","same_gender_other_family","gender_erasure","random_42","random_43","random_44"]
    selected = [next(r for r in effects if r["scenario"]=="childcare" and r["condition"]==c) for c in conditions]
    values = [r["female_margin_change"]["mean"] for r in selected]
    error = np.array([[v-r["female_margin_change"]["ci_low"],r["female_margin_change"]["ci_high"]-v] for r,v in zip(selected,values)]).T
    axes[1,0].bar(range(len(conditions)),values,color=["#888888","#245675","#7897a8","#bf6835","#aaa9a6","#aaa9a6","#aaa9a6"],yerr=error,capsize=3)
    axes[1,0].axhline(0,color="#555555",linewidth=.6)
    axes[1,0].set(xticks=range(len(conditions)),xticklabels=["Self","Flip gender","Other family","Erase","Random 42","Random 43","Random 44"],ylabel="Change in female-minus-male logit margin",title="Held-out childcare interventions (4 families)")
    axes[1,0].tick_params(axis="x",rotation=25)
    controls = ["gender_erasure","random_42","random_43","random_44"]
    values = [100*next(r for r in effects if r["scenario"]=="merit" and r["condition"]==c)["merit_preferred_count"]/16 for c in controls]
    original = [r for r in rows.values() if r["scenario"]=="merit"]
    baseline_rate = 100*np.mean([baseline[r["id"]]["preferred_slot"]==r["expected_merit_slot"] for r in original])
    axes[1,1].bar(range(5),[baseline_rate,*values],color=["#245675","#bf6835","#aaa9a6","#aaa9a6","#aaa9a6"])
    axes[1,1].set(xticks=range(5),xticklabels=["Baseline","Erase","Random 42","Random 43","Random 44"],ylabel="Qualified candidate preferred (%)",ylim=(0,105),title="Actual childcare qualification control (n=16)")
    # Show the failure to transfer to free answers in the same figure as the
    # positive diagnostic, so the visual cannot imply a general bias repair.
    generations = read_jsonl(run / "generations.jsonl")
    parsed = json.loads((out / "generation_decisions.json").read_text())
    forced_base = [r for r in baseline.values() if r["split"]=="test" and r["scenario"]=="childcare"]
    forced_patched = next(r for r in effects if r["scenario"]=="childcare" and r["condition"]=="gender_erasure")
    before = [100*sum((r["margin"]>0)==bool(r["female_a"]) for r in forced_base)/16,
              100*sum(r["headline_decision"]=="T" for r in parsed if r["condition"]=="baseline")/16]
    after = [100*forced_patched["female_preferred_count"]/16,
             100*sum(r["headline_decision"]=="T" for r in parsed if r["condition"]=="gender_erasure")/16]
    x = np.arange(2)
    axes[2,0].bar(x-.18,before,.36,color="#245675",label="Baseline")
    axes[2,0].bar(x+.18,after,.36,color="#bf6835",label="Erasure")
    axes[2,0].set(xticks=x,xticklabels=["A/B diagnostic","Name + justification"],ylim=(0,110),ylabel="Female candidate selected (%)",title="Format boundary: original-style choices unchanged")
    for i,(a,b) in enumerate(zip(before,after)):
        axes[2,0].text(i-.18,a+2,f"{round(a*16/100)}/16",ha="center",fontsize=8)
        axes[2,0].text(i+.18,b+2,f"{round(b*16/100)}/16",ha="center",fontsize=8)
    axes[2,0].legend(fontsize=8,loc="lower right")
    transfer = read_jsonl(run / "transfer.jsonl")
    cells = [(lang,cue) for lang in ["en","fr","ar"] for cue in ["name","explicit","embedded"]]
    before,after,labels = [],[],[]
    for lang,cue in cells:
        selected = [r for r in transfer if r["lang"]==lang and r["cue"]==cue]
        before.append(100*sum((baseline[r["id"]]["margin"]>0)==bool(r["female_a"]) for r in selected)/len(selected))
        after.append(100*sum((r["margin"]>0)==bool(r["female_a"]) for r in selected)/len(selected))
        labels.append(lang.upper()+"\n"+{"name":"name","explicit":"gender","embedded":"parent"}[cue])
    x=np.arange(len(cells))
    axes[2,1].bar(x-.18,before,.36,color="#245675")
    axes[2,1].bar(x+.18,after,.36,color="#bf6835")
    axes[2,1].set(xticks=x,xticklabels=labels,ylim=(0,110),ylabel="Female-coded candidate preferred (%)",title="Original prompt transfer: no consistent reduction")
    axes[2,1].tick_params(axis="x",labelsize=8)
    fig.suptitle("Public Apertus v1.5 70B · layer probes, activation patches and transfer checks",fontsize=12)
    fig.savefig(out / "whitebox_overview.png",dpi=180)
    fig.savefig(out / "whitebox_overview.pdf")
    plt.close(fig)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run",type=Path)
    analyze(parser.parse_args().run.resolve())
