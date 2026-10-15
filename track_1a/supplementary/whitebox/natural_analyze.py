"""CPU-only verification of gender mediation in original-format recommendations."""

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle
import numpy as np

from natural_experiment import outcome


def read(path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write(path,value):
    path.write_text(json.dumps(value,indent=2,ensure_ascii=False,allow_nan=False)+"\n",encoding="utf-8")


def cluster_interval(records,field):
    groups=sorted({r["family_id"] for r in records})
    if not groups:return dict(mean=None,ci_low=None,ci_high=None,n_families=0)
    values=np.array([[sum(float(r[field]) for r in records if r["family_id"]==f),sum(r["family_id"]==f for r in records)] for f in groups])
    draws=values[np.random.default_rng(42).integers(len(values),size=(2000,len(values)))].sum(1)
    lo,hi=np.quantile(draws[:,0]/draws[:,1],[.025,.975])
    return dict(mean=float(values[:,0].sum()/values[:,1].sum()),ci_low=float(lo),ci_high=float(hi),n_families=len(groups))


def select(scan,coarse):
    candidates=[]
    for layer in coarse:
        for site in ["cues","answer"]:
            if (layer,site)==(79,"answer"):continue
            group=[r for r in scan if r["layer"]==layer and r["site"]==site and r["condition"]=="counterfactual" and r["eligible_choice_contrast"]]
            if group:candidates.append((sum(r["donor_name_restored"] for r in group)/len(group),site=="cues",-layer,layer,site))
    return max(candidates)[-2:]


def analyze(folder):
    manifest=json.loads((folder/"manifest.json").read_text())
    for name,digest in manifest["files"].items():
        if Path(name).name!=name or hashlib.sha256((folder/name).read_bytes()).hexdigest()!=digest:
            raise ValueError("Frozen evidence hash mismatch: "+name)
    status=json.loads((folder/"status.json").read_text())
    runtime=json.loads((folder/"runtime.json").read_text())
    summary_input=json.loads((folder/"summary.json").read_text())
    if status["status"]!="completed" or summary_input["status"]!="completed":
        raise ValueError("Only completed inference evidence can be analyzed")
    if hashlib.sha256((folder/"natural_experiment.py").read_bytes()).hexdigest()!=runtime["source_sha256"]:
        raise ValueError("Inference source differs from runtime provenance")
    design=json.loads((folder/"natural_design.json").read_text(encoding="utf-8"))
    serialized=json.dumps(design["records"],ensure_ascii=False,sort_keys=True,separators=(",",":"))
    if hashlib.sha256(serialized.encode()).hexdigest()!=design["manifest"]["design_sha256"]:raise ValueError("Design mismatch")
    if runtime["manifest"]!=design["manifest"] or summary_input["design_sha256"]!=design["manifest"]["design_sha256"]:
        raise ValueError("Runtime/result design provenance mismatch")
    rows={r["id"]:r for r in design["records"]}
    baseline=read(folder/"baseline.jsonl")
    baselines={r["id"]:r for r in baseline}
    readouts=read(folder/"readouts.jsonl")
    scan=read(folder/"validation_scan.jsonl")
    interventions=read(folder/"interventions.jsonl")
    probes=json.loads((folder/"gender_probes.json").read_text())
    selection=json.loads((folder/"selection.json").read_text())
    if (len(rows),len(readouts),len(baseline),len(scan),len(interventions))!=(108,108,84,144,216):
        raise ValueError("Incomplete scheduled original-format study")
    if len(baselines)!=84 or set(r["id"] for r in readouts)!=set(rows):raise ValueError("Duplicate/missing original-format baselines")
    if any(rows[r]["scenario"]!="calibration" for r in selection["probe_training_ids"]):
        raise ValueError("Gender readout used recommendation labels/examples")
    if any(rows[r["id"]]["split"]!="validation" for r in scan):raise ValueError("Scan leaked outside validation")
    if select(scan,design["manifest"]["coarse_layers"])!=(selection["layer"],selection["site"]):raise ValueError("Selection rule mismatch")
    for record in baseline+scan+interventions:
        parsed=outcome(rows[record["id"]],record["response"])
        for key in ["selected_name","selected_slot","decision","parse_outcome","selected_female"]:
            if parsed[key]!=record[key]:raise ValueError("Name extraction mismatch: "+record["id"])
    for record in scan+interventions:
        row=rows[record["id"]]
        base=baselines[row["id"]]
        donor=baselines[row["donor_id"]]
        if record["base_selected_name"]!=base["selected_name"] or record["donor_selected_name"]!=donor["selected_name"]:
            raise ValueError("Counterfactual outcome mismatch")
        eligible=bool(base["selected_name"] and donor["selected_name"] and base["selected_name"]!=donor["selected_name"])
        if eligible!=record["eligible_choice_contrast"]:raise ValueError("Eligibility mismatch")
        if eligible and record["donor_name_restored"]!=(record["selected_name"]==donor["selected_name"]):raise ValueError("Restoration mismatch")
        if record["condition"]=="noop" and record["output_token_ids"]!=base["output_token_ids"]:raise ValueError("Self patch altered generation")
    if len({(r["id"],r["layer"],r["site"],r["condition"]) for r in scan})!=144:raise ValueError("Duplicate validation patch")
    if len({(r["id"],r["condition"]) for r in interventions})!=216:raise ValueError("Duplicate confirmation patch")
    # Verify probe targets and names/splits; accuracies must come from stored
    # predictions, with labels defined by the supplied profiles, never choices.
    for record in probes:
        expected=[1-rows[i]["female_a"] if record["site"]=="cue_B" else rows[i]["female_a"] for i in record["ids"]]
        if expected!=record["labels"] or any(rows[i]["split"]!=record["split"] for i in record["ids"]):
            raise ValueError("Probe target/split mismatch")
        if abs(np.mean(np.array(expected)==record["predictions"])-record["accuracy"])>1e-12:raise ValueError("Probe accuracy mismatch")
    out=folder/"analysis"
    out.mkdir(exist_ok=True)
    effects=[]
    for split in ["test","transfer"]:
        for task in sorted({r["scenario"] for r in interventions if r["split"]==split}):
            for condition in sorted({r["condition"] for r in interventions if r["split"]==split and r["scenario"]==task}):
                group=[r for r in interventions if r["split"]==split and r["scenario"]==task and r["condition"]==condition]
                eligible=[r for r in group if r["eligible_choice_contrast"]]
                augmented=[]
                for r in group:
                    base=baselines[r["id"]]
                    augmented.append({**r,"restoration_all":bool(r["eligible_choice_contrast"] and r["donor_name_restored"]),
                        "strict_choice_flip":bool(base["selected_name"] and r["selected_name"] and r["selected_name"]!=base["selected_name"])})
                effects.append(dict(split=split,scenario=task,condition=condition,n=len(group),
                    n_families=len({r["family_id"] for r in group}),n_eligible=len(eligible),
                    donor_restored=sum(bool(r["donor_name_restored"]) for r in eligible),
                    restoration_all_interval=cluster_interval(augmented,"restoration_all"),
                    strict_name_flips=sum(r["strict_choice_flip"] for r in augmented),
                    unselected=sum(r["selected_name"] is None for r in group),
                    female_selected=sum(r["selected_female"] is True for r in group),
                    qualified_selected=sum(r["selected_slot"]==r["expected_merit_slot"] for r in group) if task=="merit" else None,
                    probe_matches_donor=sum(all((a>0)==(d>0) for a,d in zip(r["gender_probe_logits_after"],r["gender_probe_logits_donor"])) for r in group),
                    mean_actual_norm=float(np.mean([r["actual_patch_norm"] for r in group]))))
    write(out/"effects.json",effects)
    norm_checks=[]
    by_condition={(r["id"],r["condition"]):r for r in interventions}
    for r in interventions:
        if not r["condition"].startswith("random_"):continue
        target_condition="counterfactual" if r["condition"].startswith("random_full_") else "gender_projection"
        target=by_condition[r["id"],target_condition]["actual_patch_norm"]
        error=abs(r["actual_patch_norm"]-target)
        norm_checks.append(dict(id=r["id"],condition=r["condition"],target_actual_norm=target,
            actual_random_norm=r["actual_patch_norm"],relative_error=error/target if target else None))
    write(out/"norm_control_check.json",dict(records=norm_checks,
        max_relative_error=max(r["relative_error"] for r in norm_checks if r["relative_error"] is not None)))
    # Paired name-logit contrasts cancel the same names' starting-token priors.
    lookup={r["id"]:r for r in readouts}
    contrasts=[]
    for row in design["records"]:
        if not (row["split"]=="test" and row["scenario"]=="childcare" and row["female_a"]==1):continue
        female=np.asarray(lookup[row["id"]]["name_logits_by_layer"])
        male=np.asarray(lookup[row["donor_id"]]["name_logits_by_layer"])
        effect=.5*((female[:,0]-female[:,1])-(male[:,0]-male[:,1]))
        contrasts.append(dict(id=row["id"],family_id=row["family_id"],order=row["order"],effect=effect.tolist()))
    write(out/"paired_name_preference.json",contrasts)
    groups=sorted({r["family_id"] for r in contrasts})
    values=np.stack([np.mean([r["effect"] for r in contrasts if r["family_id"]==f],axis=0) for f in groups])
    draws=values[np.random.default_rng(42).integers(len(groups),size=(2000,len(groups)))].mean(1)
    lens_summary=dict(mean=values.mean(0).tolist(),ci_low=np.quantile(draws,.025,axis=0).tolist(),ci_high=np.quantile(draws,.975,axis=0).tolist(),n_families=len(groups))
    write(out/"name_preference_by_layer.json",lens_summary)
    input_contrasts=[]
    for row in design["records"]:
        if row["scenario"]!="childcare" or row["split"] not in ["validation","test","transfer"] or row["female_a"]!=1:continue
        base=baselines[row["id"]]
        donor=baselines[row["donor_id"]]
        input_contrasts.append(dict(id=row["id"],family_id=row["family_id"],split=row["split"],
            both_selected=bool(base["selected_name"] and donor["selected_name"]),
            name_changed=bool(base["selected_name"] and donor["selected_name"] and base["selected_name"]!=donor["selected_name"]),
            original_name=base["selected_name"],reversed_gender_name=donor["selected_name"]))
    write(out/"input_counterfactuals.json",input_contrasts)
    casebook=["# Original-format causal gender mediation: complete fresh test cases","",
        "The recipient's prompt remains unchanged during internal patching. A counterfactual donor reverses only its two gender labels. "
        "These are causal diagnostics, not proposed fairness repairs. No new human B/R labels are asserted.",""]
    for row in design["records"]:
        if row["split"]!="test" or row["scenario"]!="childcare":continue
        casebook.extend([f"## {row['id']}","","**Recipient prompt**","",row["prompt"],"",
            "**Baseline**","",baselines[row["id"]]["response"],"",
            "**Gender-reversed text counterfactual**","",baselines[row["donor_id"]]["response"],""])
        for condition in ["counterfactual","gender_projection"]:
            r=next(r for r in interventions if r["id"]==row["id"] and r["condition"]==condition)
            casebook.extend([f"**Internal {condition} patch; recipient text unchanged** — selected {r['selected_name']}; truncated={r['truncated']}","",r["response"],""])
    (out/"REVIEW_CASEBOOK.md").write_text("\n".join(casebook),encoding="utf-8")
    controls=["# Complete qualification, teamwork, same-gender and original-prompt transfer outputs","",
        "These controls are part of the scheduled experiment. Both changes and unchanged choices are retained; no human B/R scores are asserted.",""]
    for row in design["records"]:
        if row["split"] not in ["test","transfer"] or (row["split"]=="test" and row["scenario"]=="childcare"):continue
        controls.extend([f"## {row['id']}","","**Recipient prompt**","",row["prompt"],"",
            "**Baseline**","",baselines[row["id"]]["response"],"",
            "**Gender-reversed text counterfactual**","",baselines[row["donor_id"]]["response"],""])
        for condition in ["counterfactual","gender_projection"]:
            r=by_condition[row["id"],condition]
            controls.extend([f"**Internal {condition} patch; recipient text unchanged** — selected {r['selected_name']}; truncated={r['truncated']}","",r["response"],""])
    (out/"CONTROL_CASEBOOK.md").write_text("\n".join(controls),encoding="utf-8")
    plot(out,probes,lens_summary,scan,effects,selection,baselines,rows,design["manifest"]["coarse_layers"])
    summary=dict(verified=True,selection=selection,n_rows=108,n_baseline=84,n_scan=144,n_confirmation=216,
        fresh_test_input_contrasts=len([r for r in input_contrasts if r["split"]=="test"]),
        fresh_test_input_choice_changes=sum(r["name_changed"] for r in input_contrasts if r["split"]=="test"),
        baseline_name_start_compliance=sum(r["top_is_name_start"] for r in readouts if rows[r["id"]]["scenario"]=="childcare" and rows[r["id"]]["split"]=="test"),
        truncations=dict(baseline=sum(r["truncated"] for r in baseline),scan=sum(r["truncated"] for r in scan),confirmation=sum(r["truncated"] for r in interventions)),
        primary_effects=[r for r in effects if r["split"]=="test" and r["scenario"]=="childcare"])
    write(out/"verification.json",summary)
    print(json.dumps({k:v for k,v in summary.items() if k!="primary_effects"},indent=2))


def plot(out,probes,lens,scan,effects,selection,baseline,rows,coarse):
    plt.rcParams.update({"font.size":9,"axes.spines.top":False,"axes.spines.right":False,"pdf.fonttype":42})
    fig,axes=plt.subplots(3,2,figsize=(11,10),layout="constrained")
    colors={"cue_A":"#2f806a","cue_B":"#789c48","answer":"#245675"}
    labels={"cue_A":"First person's gender cue","cue_B":"Second person's gender cue","answer":"Before the answer"}
    for site in colors:
        for shuffled in [False,True]:
            group=[r for r in probes if r["site"]==site and r["split"]=="test" and r["shuffled"]==shuffled]
            axes[0,0].plot([r["layer"]+1 for r in group],[r["accuracy"] for r in group],color=colors[site],
                alpha=.35 if shuffled else 1,linestyle=":" if shuffled else "-",label=labels[site] if not shuffled else None)
    axes[0,0].axhline(.5,color="#999999",linestyle="--",linewidth=.6)
    axes[0,0].set(title="Where supplied gender is readable",xlabel="Decoder block (1-based)",ylabel="Accuracy on fresh childcare names",ylim=(-.02,1.04))
    axes[0,0].legend(fontsize=8,loc="lower right")
    x=np.arange(1,81)
    axes[0,1].plot(x,lens["mean"],color="#bf6835")
    axes[0,1].fill_between(x,lens["ci_low"],lens["ci_high"],color="#bf6835",alpha=.18)
    axes[0,1].axhline(0,color="#777777",linewidth=.7)
    axes[0,1].set(title="Developing preference for the woman's name",xlabel="Decoder block (1-based)",ylabel="Paired gender effect on name-start logits")
    for index,condition in enumerate(["counterfactual","gender_projection"]):
        values=[]
        for site in ["cues","answer"]:
            line=[]
            for layer in coarse:
                group=[r for r in scan if r["condition"]==condition and r["layer"]==layer and r["site"]==site]
                line.append(sum(bool(r["donor_name_restored"]) for r in group)/len(group))
            values.append(line)
        axis=axes[1,index]
        image=axis.imshow(values,aspect="auto",vmin=0,vmax=1,cmap="YlGnBu")
        axis.set(xticks=range(len(coarse)),xticklabels=[x+1 for x in coarse],yticks=[0,1],yticklabels=["Gender cues","Before answer"],
            xlabel="Patched decoder block",title="Actual name changes: "+("full state" if index==0 else "probe-axis component"))
        if index==0:axis.add_patch(Rectangle((coarse.index(selection["layer"])-.5,(0 if selection["site"]=="cues" else 1)-.5),1,1,fill=False,color="#b84a36",linewidth=2))
        fig.colorbar(image,ax=axis,label="Fraction restoring donor name (n=4)")
    conditions=["counterfactual","gender_projection","noop","same_gender_other_family","random_full_42","random_full_43","random_full_44","random_projection_42"]
    primary=[next(r for r in effects if r["split"]=="test" and r["scenario"]=="childcare" and r["condition"]==c) for c in conditions]
    values=[r["donor_restored"] for r in primary]
    axes[2,0].bar(range(len(values)),values,color=["#245675","#bf6835","#888888","#7897a8",*(["#aaaaaa"]*4)])
    axes[2,0].set(xticks=range(len(values)),xticklabels=["Full swap","Probe axis","Self","Other names","Rand full 42","Rand full 43","Rand full 44","Rand axis 42"],
        ylim=(0,17.5),ylabel="Actual donor name restored / 16",title="Confirmation on four fresh name families")
    axes[2,0].tick_params(axis="x",rotation=35,labelsize=7)
    for i,v in enumerate(values):axes[2,0].text(i,v+.2,str(v),ha="center",fontsize=8)
    control_rows=[]
    for task,label in [("merit","Qualifications"),("coworker","Teamwork"),("same_identity","Same gender")]:
        group=[r for r in effects if r["split"]=="test" and r["scenario"]==task]
        full=next(r for r in group if r["condition"]=="counterfactual")
        gender=next(r for r in group if r["condition"]=="gender_projection")
        control_rows.append([label,str(full["n"]),str(full["strict_name_flips"]),str(gender["strict_name_flips"])])
    axes[2,1].axis("off")
    axes[2,1].set_title("Specificity checks: selected-name changes")
    table=axes[2,1].table(cellText=control_rows,colLabels=["Task","Prompts","Full swap","Probe axis"],loc="center",cellLoc="center",colWidths=[.35,.2,.22,.23])
    table.auto_set_font_size(False);table.set_fontsize(9);table.scale(1,1.8)
    merit=[r for r in effects if r["split"]=="test" and r["scenario"]=="merit"]
    base=sum(r["selected_slot"]==r["expected_merit_slot"] for r in baseline.values() if r["split"]=="test" and r["scenario"]=="merit")
    full=next(r["qualified_selected"] for r in merit if r["condition"]=="counterfactual")
    gender=next(r["qualified_selected"] for r in merit if r["condition"]=="gender_projection")
    axes[2,1].text(.5,.15,f"Qualified candidate selected: baseline {base}/16; full {full}/16; probe axis {gender}/16",ha="center",transform=axes[2,1].transAxes,fontsize=8)
    fig.suptitle("Original-format childcare · gender information and causal influence on selected names",fontsize=12)
    fig.savefig(out/"natural_gender_mediation.png",dpi=180)
    fig.savefig(out/"natural_gender_mediation.pdf",metadata={"CreationDate":None,"ModDate":None})
    plt.close(fig)


if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run",type=Path)
    analyze(parser.parse_args().run.resolve())
