"""Original name-and-justification task: gender readability and causal use.

There is no A/B answer-format manipulation and no learned decision probe.
Gender probes learn only from non-choice profile-summary calibration prompts.
The primary intervention outcome is the name selected in an actual generation.
"""

from contextlib import contextmanager
import hashlib
import importlib.metadata
import json
from pathlib import Path
import sys
import time

import numpy as np

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
if len(HERE.parents)>1 and (HERE.parents[1]/"src").exists():
    sys.path.insert(0,str(HERE.parents[1]/"src"))

from experiment import ATTENTION, append, write_json
from choice_parser import parse_row


class NaturalInstrument:
    def __init__(self,model,processor,rows):
        import torch
        self.torch,self.model,self.processor=torch,model,processor
        self.tokenizer=processor.tokenizer
        self.layers=model.model.language_model.layers
        self.device=model.get_input_embeddings().weight.device
        self.encoded={}
        for row in rows:
            rendered=processor.apply_chat_template([{"role":"user","content":row["prompt"]}],
                tokenize=False,add_generation_prompt=True,enable_thinking=False)
            enc=self.tokenizer(rendered,add_special_tokens=False,return_offsets_mapping=True,return_tensors="pt")
            offsets=enc.pop("offset_mapping")[0].tolist()
            ids=enc["input_ids"][0].tolist()
            if len(ids)>1024: raise ValueError("No prompt truncation allowed")
            origin=rendered.index(row["prompt"])
            cues=[]
            for a,b in row["cue_spans"]:
                positions=[i for i,(s,e) in enumerate(offsets) if e>s and s<origin+b and e>origin+a]
                if not positions: raise ValueError("Could not align a gender cue")
                cues.append(positions[-1])
            if len(cues)!=2: raise ValueError("Expected two gender-cue endpoints")
            name_ids=[]
            for name in row["names"]:
                full=self.tokenizer.encode(rendered+name,add_special_tokens=False)
                if full[:len(ids)]!=ids or len(full)<=len(ids):
                    raise ValueError("Native boundary/name tokenization changed")
                name_ids.append(full[len(ids)])
            self.encoded[row["id"]]=dict(inputs={k:v.to(self.device) for k,v in enc.items()},
                positions={"cues":cues,"answer":[len(ids)-1]},input_ids=ids,prompt_tokens=len(ids),name_ids=name_ids,
                distinct_name_starts=name_ids[0]!=name_ids[1])

    @contextmanager
    def patch(self,encoded,layer,site,replacements):
        torch=self.torch
        used=[False]
        if len(replacements)!=len(encoded["positions"][site]): raise ValueError("Replacement/site shape mismatch")
        def hook(module,args,output):
            if used[0]: return output
            used[0]=True
            if output.shape[1]!=encoded["prompt_tokens"]: raise RuntimeError("Expected fresh complete prefill")
            patched=output.clone()
            for position,vector in zip(encoded["positions"][site],replacements):
                patched[0,position]=torch.as_tensor(vector,device=output.device,dtype=output.dtype)
            return patched
        handle=self.layers[layer].register_forward_hook(hook)
        try:
            yield
            if not used[0]: raise RuntimeError("Hook was not invoked")
        finally:
            handle.remove()

    def capture(self,ident):
        torch=self.torch
        encoded=self.encoded[ident]
        vectors={}
        handles=[]
        for layer,module in enumerate(self.layers):
            def hook(module,args,output,i=layer):
                positions=[*encoded["positions"]["cues"],encoded["positions"]["answer"][0]]
                vectors[i]=output[0,positions].detach().float().cpu().numpy()
            handles.append(module.register_forward_hook(hook))
        try:
            with torch.inference_mode():
                result=self.model(**encoded["inputs"],use_cache=False,logits_to_keep=1)
                logits=result.logits[0,-1].float()
                a,b=encoded["name_ids"]
                stats=dict(name_margin=float(logits[a]-logits[b]),top_token_id=int(logits.argmax()),
                    top_token=self.tokenizer.decode([int(logits.argmax())]),
                    top_is_name_start=bool(int(logits.argmax()) in [a,b]),name_ids=encoded["name_ids"],
                    distinct_name_starts=encoded["distinct_name_starts"],prompt_tokens=encoded["prompt_tokens"])
                if not torch.isfinite(logits).all(): raise FloatingPointError("Nonfinite logits")
                del result
        finally:
            for h in handles:h.remove()
        array=np.stack([vectors[layer] for layer in range(len(self.layers))])
        if not np.isfinite(array).all(): raise FloatingPointError("Nonfinite residuals")
        # An untuned logit lens uses the existing output head, not a trained
        # classifier. It is descriptive, not a proof of a commitment layer.
        with torch.inference_mode():
            device=self.model.lm_head.weight.device
            hidden=torch.as_tensor(array[:,2],device=device,dtype=self.model.lm_head.weight.dtype)
            normalized=self.model.model.language_model.norm(hidden)
            lens=self.model.lm_head(normalized)[:,encoded["name_ids"]].float().cpu().numpy()
        return array,stats,lens

    def generate(self,ident,intervention=None,max_new_tokens=96):
        torch=self.torch
        encoded=self.encoded[ident]
        kwargs=dict(**encoded["inputs"],do_sample=False,max_new_tokens=max_new_tokens,use_cache=True)
        with torch.inference_mode():
            if intervention is None:
                result=self.model.generate(**kwargs)
            else:
                with self.patch(encoded,*intervention):result=self.model.generate(**kwargs)
        new=result[0,encoded["prompt_tokens"]:]
        eos=self.model.generation_config.eos_token_id
        eos=eos if isinstance(eos,list) else [eos]
        return dict(response=self.tokenizer.decode(new,skip_special_tokens=True),output_token_ids=new.tolist(),
            output_tokens=len(new),truncated=bool(len(new)==max_new_tokens and int(new[-1]) not in eos))


def outcome(row,response):
    target_slot="A" if row["female_a"] in [1,None] else "B"
    target_index=0 if target_slot=="A" else 1
    parsed=parse_row(dict(task="choice",status="success",lang=row["lang"],prompt=row["prompt"],response=response,
        target_name=row["names"][target_index],reference_name=row["names"][1-target_index],target_slot=target_slot))
    return dict(selected_name=parsed["picked_name"] or None,selected_slot=parsed["picked_slot"] or None,
        decision=parsed["headline_decision"],parse_outcome=parsed["parse_outcome"],parse_method=parsed["parse_method"],
        choice_evidence=parsed["decision_evidence"],selected_female=(parsed["headline_decision"]=="T") if row["female_a"] is not None and parsed["headline_decision"] in ["T","R"] else None)


def fit_gender_probes(rows,features,folder):
    from sklearn.linear_model import LogisticRegression
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import StandardScaler
    train=[r for r in rows if r["scenario"]=="calibration"]
    test=[r for r in rows if r["scenario"]=="childcare" and r["split"] in ["validation","test"]]
    families=sorted({r["family_id"] for r in train})
    flips=dict(zip(families,np.random.default_rng(42).integers(0,2,len(families))))
    coefficients={}
    records=[]
    for layer in range(80):
        for site_index,site in enumerate(["cue_A","cue_B","answer"]):
            x=np.stack([features[r["id"]][layer,site_index] for r in train])
            def label(r):return 1-r["female_a"] if site=="cue_B" else r["female_a"]
            y=np.asarray([label(r) for r in train])
            for shuffled in [False,True]:
                target=np.asarray([label(r)^flips[r["family_id"]] for r in train]) if shuffled else y
                estimator=make_pipeline(StandardScaler(),LogisticRegression(C=.1,solver="liblinear",random_state=42,max_iter=1000))
                estimator.fit(x,target)
                if not shuffled:
                    scaler,linear=estimator.steps[0][1],estimator.steps[1][1]
                    raw=linear.coef_[0]/scaler.scale_
                    direction=(raw/np.linalg.norm(raw)).astype(np.float32)
                    intercept=float(linear.intercept_[0]-np.dot(raw,scaler.mean_))
                    coefficients[layer,site_index]=dict(direction=direction,raw_coefficient=raw.astype(np.float32),intercept=intercept)
                for split in ["validation","test"]:
                    group=[r for r in test if r["split"]==split]
                    expected=np.asarray([label(r) for r in group])
                    predicted=estimator.predict(np.stack([features[r["id"]][layer,site_index] for r in group]))
                    records.append(dict(layer=layer,site=site,split=split,shuffled=shuffled,n=len(group),
                        n_families=len({r["family_id"] for r in group}),accuracy=float(np.mean(predicted==expected)),
                        ids=[r["id"] for r in group],labels=expected.tolist(),predictions=predicted.tolist()))
    write_json(folder/"gender_probes.json",records)
    np.savez_compressed(folder/"gender_directions.npz",**{f"layer_{layer}_site_{site}":value["direction"] for (layer,site),value in coefficients.items()})
    return coefficients


def projection(recipient,donor,directions):
    return recipient+np.stack([u*np.dot(u,d-h) for h,d,u in zip(recipient,donor,directions)])


def rounded(torch,values):
    return torch.as_tensor(values,dtype=torch.bfloat16).float().numpy()


def random_matched(torch,recipient,target_norm,seed):
    if target_norm==0:return recipient.copy()
    vector=np.random.default_rng(seed).normal(size=recipient.shape).astype(np.float32)
    vector/=np.linalg.norm(vector)
    scale=target_norm
    best=None
    for _ in range(8):
        candidate=rounded(torch,recipient+scale*vector)
        actual=np.linalg.norm(candidate-recipient)
        error=abs(actual-target_norm)
        if best is None or error<best[0]:best=(error,candidate)
        if error<=.02*target_norm:break
        scale=scale*target_norm/actual if actual>0 else scale*2
    return best[1]


def run(weights,destination,design_path,commit=lambda:None):
    import torch
    from transformers import AutoModelForMultimodalLM,AutoProcessor
    started=time.monotonic()
    destination.mkdir(parents=True)
    design=json.loads(design_path.read_text(encoding="utf-8"))
    rows=design["records"]
    lookup={r["id"]:r for r in rows}
    write_json(destination/"natural_design.json",design)
    source=Path(__file__).read_bytes()
    (destination/"natural_experiment.py").write_bytes(source)
    metadata=dict(manifest=design["manifest"],source_sha256=hashlib.sha256(source).hexdigest(),
        gpu=[torch.cuda.get_device_name(i) for i in range(torch.cuda.device_count())],
        packages={p:importlib.metadata.version(p) for p in ["torch","transformers","accelerate","numpy","scikit-learn"]},
        attention_implementation=ATTENTION,probe_training="non-choice calibration prompts only",
        primary_outcome="actual generated selected name",system_message=None,thinking=False)
    write_json(destination/"runtime.json",metadata)
    status="running"
    def budget():
        if time.monotonic()-started>5100:raise TimeoutError("Internal 85-minute stop reached")
    try:
        torch.manual_seed(42)
        torch.set_num_threads(4)
        print("Loading pinned 70B for the unchanged name-and-justification task",flush=True)
        processor=AutoProcessor.from_pretrained(weights,local_files_only=True)
        model=AutoModelForMultimodalLM.from_pretrained(weights,dtype=torch.bfloat16,device_map="balanced",
            max_memory={0:"73GiB",1:"73GiB","cpu":"48GiB"},attn_implementation=ATTENTION,local_files_only=True).eval()
        if any(str(v) in ["cpu","disk"] for v in model.hf_device_map.values()):raise RuntimeError("Unexpected weight offload")
        metadata["load_seconds"]=time.monotonic()-started
        metadata["device_map"]={k:str(v) for k,v in model.hf_device_map.items()}
        write_json(destination/"runtime.json",metadata)
        instrument=NaturalInstrument(model,processor,rows)
        features,baseline={},{}
        feature_dir=destination/"activations"
        feature_dir.mkdir()
        for i,row in enumerate(rows):
            budget()
            array,stats,lens=instrument.capture(row["id"])
            features[row["id"]]=array
            np.savez_compressed(feature_dir/(row["id"]+".npz"),residuals=array)
            append(destination/"readouts.jsonl",dict(id=row["id"],family_id=row["family_id"],split=row["split"],
                scenario=row["scenario"],female_a=row["female_a"],name_logits_by_layer=lens.tolist(),**stats))
            if row["scenario"]!="calibration":
                result=instrument.generate(row["id"])
                record=dict(id=row["id"],family_id=row["family_id"],split=row["split"],scenario=row["scenario"],
                    female_a=row["female_a"],expected_merit_slot=row["expected_merit_slot"],condition="baseline",**result)
                record.update(outcome(row,result["response"]))
                baseline[row["id"]]=record
                append(destination/"baseline.jsonl",record)
            if i%8==0:
                print("Original-format baseline/features",i+1,"/",len(rows),flush=True)
                commit()
        print("Fitting gender-only probes learned on non-choice profiles",flush=True)
        coefficients=fit_gender_probes(rows,features,destination)
        def states(ident,layer,site):
            return features[ident][layer,[0,1] if site=="cues" else [2]]
        def directions(layer,site):
            return [coefficients[layer,index]["direction"] for index in ([0,1] if site=="cues" else [2])]
        def measure(row,layer,site,condition,vector,cap):
            budget()
            result=instrument.generate(row["id"],intervention=(layer,site,vector),max_new_tokens=cap)
            record=dict(id=row["id"],family_id=row["family_id"],split=row["split"],scenario=row["scenario"],
                female_a=row["female_a"],expected_merit_slot=row["expected_merit_slot"],layer=layer,site=site,condition=condition,**result)
            record.update(outcome(row,result["response"]))
            base=baseline[row["id"]]
            donor=baseline[row["donor_id"]]
            eligible=bool(base["selected_name"] and donor["selected_name"] and base["selected_name"]!=donor["selected_name"])
            record.update(base_selected_name=base["selected_name"],donor_selected_name=donor["selected_name"],
                eligible_choice_contrast=eligible,selected_name_changed=record["selected_name"]!=base["selected_name"],
                donor_name_restored=(record["selected_name"]==donor["selected_name"]) if eligible else None,
                intended_patch_norm=float(np.linalg.norm(vector-states(row["id"],layer,site))),
                actual_patch_norm=float(np.linalg.norm(rounded(torch,vector)-states(row["id"],layer,site))))
            indices=[0,1] if site=="cues" else [2]
            def probe_logits(values):
                return [float(np.dot(coefficients[layer,index]["raw_coefficient"],h)+coefficients[layer,index]["intercept"])
                        for index,h in zip(indices,values)]
            record["gender_probe_logits_before"]=probe_logits(states(row["id"],layer,site))
            record["gender_probe_logits_after"]=probe_logits(rounded(torch,vector))
            record["gender_probe_logits_donor"]=probe_logits(states(row["donor_id"],layer,site))
            return record
        # Check exact token identity under a self patch before the scan.
        pilot=next(r for r in rows if r["scenario"]=="childcare" and r["split"]=="validation")
        sham=measure(pilot,39,"answer","noop",states(pilot["id"],39,"answer"),96)
        if sham["output_token_ids"]!=baseline[pilot["id"]]["output_token_ids"]:raise RuntimeError("Self patch changed generation")
        write_json(destination/"hook_validation.json",dict(self_patch_tokens_identical=True,id=pilot["id"]))
        scan=[]
        validation=[r for r in rows if r["scenario"]=="childcare" and r["split"]=="validation" and r["order"]==0]
        for layer in design["manifest"]["coarse_layers"]:
            for site in ["cues","answer"]:
                for row in validation:
                    h=states(row["id"],layer,site)
                    donor=states(row["donor_id"],layer,site)
                    for condition,vector in [("counterfactual",donor),("gender_projection",projection(h,donor,directions(layer,site)))]:
                        record=measure(row,layer,site,condition,vector,48)
                        scan.append(record)
                        append(destination/"validation_scan.jsonl",record)
            print("Original-format causal scan: completed block",layer+1,flush=True)
            commit()
        candidates=[]
        for layer in design["manifest"]["coarse_layers"]:
            for site in ["cues","answer"]:
                if (layer,site)==(79,"answer"):continue
                group=[r for r in scan if r["layer"]==layer and r["site"]==site and r["condition"]=="counterfactual"]
                eligible=[r for r in group if r["eligible_choice_contrast"]]
                if eligible:candidates.append((sum(r["donor_name_restored"] for r in eligible)/len(eligible),site=="cues",-layer,layer,site))
        if not candidates:raise RuntimeError("No selected-name contrast on validation; causal selection unavailable")
        score,_,_,layer,site=max(candidates)
        selection=dict(layer=layer,site=site,validation_restoration=score,selected_on="validation only",
            criterion=design["manifest"]["selection"],probe_training_ids=[r["id"] for r in rows if r["scenario"]=="calibration"])
        write_json(destination/"selection.json",selection)
        commit()
        print("Frozen original-format intervention: block",layer+1,"site",site,flush=True)
        confirmation=[]
        for row in rows:
            if not (row["split"] in ["test","transfer"]):continue
            h=states(row["id"],layer,site)
            donor=states(row["donor_id"],layer,site)
            gender=projection(h,donor,directions(layer,site))
            replacements={"counterfactual":donor,"gender_projection":gender}
            if row["scenario"]=="childcare" and row["split"]=="test":
                replacements["noop"]=h
                other=next(r for r in rows if r["split"]=="test" and r["scenario"]=="childcare" and
                    r["family_id"]!=row["family_id"] and r["order"]==row["order"] and r["female_a"]==row["female_a"])
                replacements["same_gender_other_family"]=states(other["id"],layer,site)
                full_norm=np.linalg.norm(rounded(torch,donor)-h)
                projection_norm=np.linalg.norm(rounded(torch,gender)-h)
                for seed in [42,43,44]:replacements[f"random_full_{seed}"]=random_matched(torch,h,full_norm,seed)
                replacements["random_projection_42"]=random_matched(torch,h,projection_norm,42)
            for condition,vector in replacements.items():
                record=measure(row,layer,site,condition,vector,96)
                if condition=="noop" and record["output_token_ids"]!=baseline[row["id"]]["output_token_ids"]:
                    raise RuntimeError("Held-out self patch changed generation")
                confirmation.append(record)
                append(destination/"interventions.jsonl",record)
            print("Original-format test/control",row["id"],flush=True)
            commit()
        summary=dict(status="completed",design_version=design["manifest"]["design_version"],design_sha256=design["manifest"]["design_sha256"],
            elapsed_seconds=time.monotonic()-started,selection=selection,n_rows=len(rows),n_baseline_generations=len(baseline),
            n_validation_generations=len(scan),n_confirmation_generations=len(confirmation),
            primary_outcome="Actual name selected in original-format generations",no_learned_decision_probe=True)
        write_json(destination/"summary.json",summary)
        status="completed"
        return summary
    except Exception as exc:
        status="failed"
        write_json(destination/"failure.json",dict(type=type(exc).__name__,message=str(exc),elapsed_seconds=time.monotonic()-started))
        raise
    finally:
        write_json(destination/"status.json",dict(status=status,elapsed_seconds=time.monotonic()-started))
        commit()
