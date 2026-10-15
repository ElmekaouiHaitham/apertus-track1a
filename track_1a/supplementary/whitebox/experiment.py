"""Small inference-only study using native PyTorch hooks, never weight updates.

Decoder block indices are zero based; vectors are post-block, pre-final-norm.
Only train data fit probes/directions; validation chooses the intervention
layer. Test and original transfer cases never choose a layer or direction.
"""

from contextlib import contextmanager
import hashlib
import importlib.metadata
import json
from pathlib import Path
import time

import numpy as np

ATTENTION = {"text_config":"sdpa", "vision_tokenizer_config":"eager", "audio_tokenizer_config":"eager"}


def write_json(path, value):
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False)+"\n", encoding="utf-8")


def append(path, record):
    with path.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(record, ensure_ascii=False, allow_nan=False)+"\n")


def erase_direction(h, direction, center):
    """Raw-coordinate, centered, rank-one removal. Arrays are float32."""
    return h - np.dot(h-center, direction) * direction


def gender_direction(features, labels):
    positive = features[np.asarray(labels) == 1].mean(0)
    negative = features[np.asarray(labels) == 0].mean(0)
    difference = positive-negative
    norm = np.linalg.norm(difference)
    if not np.isfinite(norm) or norm < 1e-8:
        raise ValueError("No finite gender-assignment direction at this site")
    return difference/norm, (positive+negative)/2


def transport_metrics(base, donor, patched):
    gap = donor-base
    delta = patched-base
    return dict(base_margin=base, donor_margin=donor, patched_margin=patched,
                delta_margin=delta, donor_gap=gap,
                signed_transport=delta*float(np.sign(gap)),
                normalized_transport=delta/gap if abs(gap) >= 0.25 else None,
                preferred_slot_flip=bool((base > 0) != (patched > 0)))


def bootstrap_by_family(rows, field, seed=42, replicates=2000):
    families = sorted({r["family_id"] for r in rows})
    if not families:
        return {"n_families": 0, "mean": None, "ci_low": None, "ci_high": None}
    values = np.asarray([[sum(r[field] for r in rows if r["family_id"] == f),
                          sum(r["family_id"] == f for r in rows)] for f in families])
    rng = np.random.default_rng(seed)
    sampled = values[rng.integers(len(values), size=(replicates, len(values)))].sum(1)
    low, high = np.quantile(sampled[:,0]/sampled[:,1], [0.025,0.975])
    return dict(n_families=len(families), mean=float(values[:,0].sum()/values[:,1].sum()),
                ci_low=float(low), ci_high=float(high))


class Instrument:
    def __init__(self, model, processor, rows, coarse):
        import torch
        self.torch = torch
        self.model, self.processor, self.tokenizer = model, processor, processor.tokenizer
        self.layers = model.model.language_model.layers
        self.coarse = coarse
        self.device = model.get_input_embeddings().weight.device
        self.encoded = {}
        for row in rows:
            for mode in ["diagnostic", "original"]:
                prompt = row["diagnostic_prompt"] if mode == "diagnostic" else row["prompt"]
                rendered = processor.apply_chat_template([{"role":"user", "content":prompt}],
                                                       tokenize=False, add_generation_prompt=True, enable_thinking=False)
                enc = self.tokenizer(rendered, add_special_tokens=False, return_offsets_mapping=True,
                                     return_tensors="pt")
                offsets = enc.pop("offset_mapping")[0].tolist()
                ids = enc["input_ids"][0].tolist()
                if len(ids) > 1024:
                    raise ValueError("Unexpectedly long prompt; truncation is prohibited")
                # Check continuation tokenization at the actual native boundary.
                candidates = []
                for answer in "AB":
                    full = self.tokenizer.encode(rendered+answer, add_special_tokens=False)
                    if full[:-1] != ids or len(full) != len(ids)+1:
                        raise ValueError("A/B is not a one-token continuation at the native answer boundary")
                    candidates.append(full[-1])
                positions = {"answer": [len(ids)-1]}
                if row.get("cue_spans"):
                    origin = rendered.index(prompt)
                    positions["cues"] = []
                    for start, end in row["cue_spans"]:
                        overlap = [i for i,(a,b) in enumerate(offsets) if b > a and a < origin+end and b > origin+start]
                        if not overlap:
                            raise ValueError("Could not align demographic cue with tokenizer offsets")
                        positions["cues"].append(overlap[-1])
                self.encoded[row["id"],mode] = dict(inputs={k:v.to(self.device) for k,v in enc.items()},
                                                    positions=positions, candidates=candidates, rendered=rendered,
                                                    prompt_tokens=len(ids), input_ids=ids)

    @contextmanager
    def patch(self, encoded, layer, site, replacements):
        torch = self.torch
        used = [False]
        def hook(module, args, output):
            # Intervene once on prefill; generate's subsequent token calls use
            # the cache produced by the patched forward. Never reuse a clean cache.
            if used[0]:
                return output
            used[0] = True
            if output.ndim != 3 or output.shape[1] != encoded["prompt_tokens"]:
                raise RuntimeError("Expected complete prefill at the intervention site")
            result = output.clone()
            for pos, vector in zip(encoded["positions"][site], replacements):
                result[0,pos] = torch.as_tensor(vector, device=output.device, dtype=output.dtype)
            return result
        handle = self.layers[layer].register_forward_hook(hook)
        try:
            yield
            if not used[0]:
                raise RuntimeError("Patch hook was never invoked")
        finally:
            handle.remove()

    def forward(self, ident, mode="diagnostic", capture=False, intervention=None):
        torch = self.torch
        encoded = self.encoded[ident,mode]
        cache = {}
        handles = []
        if capture:
            for index, layer in enumerate(self.layers):
                def hook(module, args, output, i=index):
                    # Hooks see post-block residuals, not output_hidden_states'
                    # normalized final state. Keep only prespecified token sites.
                    cache[i,"answer"] = output[0,encoded["positions"]["answer"]].detach().float().cpu().numpy()
                    if i in self.coarse and "cues" in encoded["positions"]:
                        cache[i,"cues"] = output[0,encoded["positions"]["cues"]].detach().float().cpu().numpy()
                handles.append(layer.register_forward_hook(hook))
        try:
            with torch.inference_mode():
                if intervention:
                    with self.patch(encoded, *intervention):
                        output = self.model(**encoded["inputs"], use_cache=False, logits_to_keep=1)
                else:
                    output = self.model(**encoded["inputs"], use_cache=False, logits_to_keep=1)
                logits = output.logits[0,-1].float()
                if not torch.isfinite(logits).all():
                    raise FloatingPointError("Non-finite logits")
                a,b = encoded["candidates"]
                probabilities = logits.softmax(-1)
                top = int(logits.argmax())
                stats = dict(margin=float(logits[a]-logits[b]),
                             p_a=float(probabilities[a]), p_b=float(probabilities[b]),
                             ab_mass=float(probabilities[a]+probabilities[b]),
                             top_token_id=top, top_token=self.tokenizer.decode([top]),
                             top_is_ab=top in [a,b], preferred_slot="A" if logits[a]>logits[b] else "B",
                             prompt_tokens=encoded["prompt_tokens"])
                del output
        finally:
            for handle in handles:
                handle.remove()
        if capture and any(not np.isfinite(value).all() for value in cache.values()):
            raise FloatingPointError("Non-finite residual vector")
        return stats, cache

    def generate(self, ident, intervention=None, max_new_tokens=96):
        torch = self.torch
        encoded = self.encoded[ident,"original"]
        kwargs = dict(**encoded["inputs"], do_sample=False, max_new_tokens=max_new_tokens, use_cache=True)
        with torch.inference_mode():
            if intervention:
                with self.patch(encoded, *intervention):
                    generated = self.model.generate(**kwargs)
            else:
                generated = self.model.generate(**kwargs)
        new = generated[0,encoded["prompt_tokens"]:]
        eos = self.model.generation_config.eos_token_id
        eos = eos if isinstance(eos,list) else [eos]
        return dict(response=self.tokenizer.decode(new,skip_special_tokens=True),
                    output_token_ids=new.tolist(), output_tokens=len(new),
                    truncated=bool(len(new)==max_new_tokens and int(new[-1]) not in eos))


def fit_probes(rows, cache, baseline, destination):
    """Predict assignment and A/B margin sign; neither is a stereotype label."""
    from sklearn.linear_model import LogisticRegression
    from sklearn.metrics import accuracy_score, balanced_accuracy_score
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import StandardScaler
    main = [r for r in rows if r["scenario"] == "childcare" and r["split"] in ["train","validation","test"]]
    train = [r for r in main if r["split"] == "train"]
    results = []
    for layer in range(80):
        x_train = np.stack([cache[r["id"]][layer,"answer"][0] for r in train])
        for label in ["female_in_A", "ab_margin_sign"]:
            def target(r):
                return r["female_a"] if label == "female_in_A" else int(baseline[r["id"]]["margin"]>0)
            y_train = np.asarray([target(r) for r in train])
            for shuffled in [False,True]:
                labels = y_train.copy()
                if shuffled:
                    # Whole-family gender polarity flips keep paired labels
                    # coherent. Decision-label null uses a family-block permutation.
                    rng = np.random.default_rng(42)
                    groups = sorted({r["family_id"] for r in train})
                    if label == "female_in_A":
                        flips = dict(zip(groups,rng.integers(0,2,len(groups))))
                        labels = np.asarray([target(r)^flips[r["family_id"]] for r in train])
                    else:
                        permutation = dict(zip(groups,rng.permutation(groups)))
                        lookup = {(r["family_id"],r["order"],r["female_a"]):target(r) for r in train}
                        labels = np.asarray([lookup[permutation[r["family_id"]],r["order"],r["female_a"]] for r in train])
                if len(set(labels)) < 2:
                    results.append(dict(layer=layer,label=label,shuffled=shuffled,status="one_training_class"))
                    continue
                estimator = make_pipeline(StandardScaler(),LogisticRegression(C=0.1,solver="liblinear",random_state=42,max_iter=1000))
                estimator.fit(x_train,labels)
                for split in ["validation","test"]:
                    selected = [r for r in main if r["split"] == split]
                    target_values = np.asarray([target(r) for r in selected])
                    prediction = estimator.predict(np.stack([cache[r["id"]][layer,"answer"][0] for r in selected]))
                    majority = int(y_train.mean() >= .5)
                    row = dict(layer=layer,label=label,shuffled=shuffled,split=split,status="scored",
                               n=len(selected),n_families=len({r["family_id"] for r in selected}),
                               accuracy=float(accuracy_score(target_values,prediction)),
                               balanced_accuracy=float(balanced_accuracy_score(target_values,prediction)) if len(set(target_values))==2 else None,
                               majority_accuracy=float(np.mean(target_values==majority)),
                               labels=target_values.tolist(),predictions=prediction.tolist(),ids=[r["id"] for r in selected])
                    results.append(row)
    write_json(destination / "probes.json",results)
    return results


def run(weights, destination, design_path, smoke=False, commit=lambda:None):
    import torch
    from transformers import AutoModelForMultimodalLM, AutoProcessor
    started = time.monotonic()
    destination.mkdir(parents=True)
    frozen = json.loads(design_path.read_text(encoding="utf-8"))
    rows = frozen["records"]
    if smoke:
        ids = ["new-en-06-o0-f0-childcare", "new-en-06-o0-f1-childcare"]
        rows = [r for r in rows if r["id"] in ids]
    write_json(destination / "design.json",frozen)
    model = None
    status = "running"
    def budget():
        if time.monotonic()-started > 5100:
            raise TimeoutError("Prespecified 85-minute internal stop reached")
    metadata = dict(manifest=frozen["manifest"],smoke=smoke,
                    packages={p:importlib.metadata.version(p) for p in ["torch","transformers","accelerate","numpy","scikit-learn"]},
                    gpu=[torch.cuda.get_device_name(i) for i in range(torch.cuda.device_count())],
                    hooks="model.model.language_model.layers[i]; post-block residual, before final RMSNorm",
                    system_message=None,thinking=False,seed=42,attention_implementation=ATTENTION)
    source = Path(__file__).read_bytes()
    (destination / "experiment.py").write_bytes(source)
    metadata["experiment_sha256"] = hashlib.sha256(source).hexdigest()
    write_json(destination / "runtime.json",metadata)
    commit()
    try:
        torch.manual_seed(42)
        torch.set_num_threads(4)
        processor = AutoProcessor.from_pretrained(weights,local_files_only=True)
        print("Loading cached 70B in BF16 on two GPUs",flush=True)
        model = AutoModelForMultimodalLM.from_pretrained(weights, dtype=torch.bfloat16, device_map="balanced",
                 max_memory={0:"73GiB",1:"73GiB","cpu":"48GiB"}, attn_implementation=ATTENTION,local_files_only=True).eval()
        if any(str(value) in ["cpu","disk"] for value in model.hf_device_map.values()):
            raise RuntimeError("CPU/disk weight offload would exceed today's runtime; stop")
        metadata["device_map"] = {k:str(v) for k,v in model.hf_device_map.items()}
        metadata["load_seconds"] = time.monotonic()-started
        write_json(destination / "runtime.json",metadata)
        instrument = Instrument(model,processor,rows,frozen["manifest"]["coarse_layers"])
        lookup = {r["id"]:r for r in rows}
        # Fail fast on hook integrity before extracting the full set.
        pilot = next(r for r in rows if r.get("donor_id") in lookup)
        pilot_base,pilot_cache = instrument.forward(pilot["id"],capture=True)
        pilot_donor,pilot_donor_cache = instrument.forward(pilot["donor_id"],capture=True)
        pilot_self,_ = instrument.forward(pilot["id"],intervention=(39,"answer",pilot_cache[39,"answer"]))
        pilot_copy,_ = instrument.forward(pilot["id"],intervention=(79,"answer",pilot_donor_cache[79,"answer"]))
        if abs(pilot_self["margin"]-pilot_base["margin"]) > 1e-5 or abs(pilot_copy["margin"]-pilot_donor["margin"]) > .02:
            raise RuntimeError("Early self/terminal-patch instrumentation check failed")
        write_json(destination / "pilot.json",dict(id=pilot["id"],base=pilot_base,donor=pilot_donor,
                   self_patch=pilot_self,terminal_donor_patch=pilot_copy,passed=True))
        commit()
        cache, baseline = {}, {}
        feature_dir = destination / "activations"
        feature_dir.mkdir()
        for index,row in enumerate(rows):
            budget()
            stats, vectors = instrument.forward(row["id"],capture=True)
            cache[row["id"]],baseline[row["id"]] = vectors,stats
            append(destination / "baseline.jsonl",dict(id=row["id"],family_id=row["family_id"],split=row["split"],
                   scenario=row["scenario"],lang=row["lang"],cue=row["cue"],female_a=row["female_a"],**stats))
            np.savez_compressed(feature_dir / (row["id"]+".npz"),**{f"layer_{l}_{site}":v for (l,site),v in vectors.items()})
            if index%12 == 0:
                print("Baseline",index+1,"/",len(rows),flush=True)
                commit()
        # Instrumentation identity: a self patch must preserve A/B logits/probabilities.
        check_row = next(r for r in rows if r.get("donor_id") in lookup)
        check_layer = 39
        sham,_ = instrument.forward(check_row["id"],intervention=(check_layer,"answer",cache[check_row["id"]][check_layer,"answer"]))
        difference = max(abs(sham[k]-baseline[check_row["id"]][k]) for k in ["margin","p_a","p_b"])
        if difference > 1e-5:
            raise RuntimeError(f"Self-patch changed baseline: {difference}")
        write_json(destination / "hook_validation.json",dict(self_patch_max_difference=difference,passed=True))
        if smoke:
            donor = check_row["donor_id"]
            patched,_ = instrument.forward(check_row["id"],intervention=(79,"answer",cache[donor][79,"answer"]))
            if abs(patched["margin"]-baseline[donor]["margin"]) > .02:
                raise RuntimeError("Terminal residual replacement did not reproduce donor A/B margin")
            summary = dict(status="smoke_passed",smoke=True,elapsed_seconds=time.monotonic()-started,
                           baseline=baseline,terminal_patch=patched,hook_validation_difference=difference)
            write_json(destination / "summary.json",summary)
            status = "smoke_passed"
            return summary
        probes = fit_probes(rows,cache,baseline,destination)
        print("Probes fitted; starting validation-only patch scan",flush=True)
        scan = []
        for row in rows:
            if row["split"] != "validation" or row["scenario"] != "childcare":
                continue
            for layer in frozen["manifest"]["coarse_layers"]:
                for site in ["cues","answer"]:
                    budget()
                    donor = row["donor_id"]
                    stats,_ = instrument.forward(row["id"],intervention=(layer,site,cache[donor][layer,site]))
                    record = dict(id=row["id"],family_id=row["family_id"],layer=layer,site=site,
                                  **transport_metrics(baseline[row["id"]]["margin"],baseline[donor]["margin"],stats["margin"]))
                    scan.append(record)
                    append(destination / "validation_scan.jsonl",record)
        # Final-token layer selected on validation only, excluding the terminal
        # block: transplanting its whole answer state is a trivial output-copy control.
        candidates = [(np.mean([r["signed_transport"] for r in scan if r["layer"]==l and r["site"]=="answer"]),l)
                      for l in frozen["manifest"]["coarse_layers"] if l != 79]
        _,layer = max(candidates,key=lambda x:(x[0],-x[1]))
        train = [r for r in rows if r["split"] == "train" and r["scenario"] == "childcare"]
        direction,center = gender_direction(np.stack([cache[r["id"]][layer,"answer"][0] for r in train]),[r["female_a"] for r in train])
        selection = dict(layer=layer,site="answer",validation_scores=[dict(layer=l,mean_signed_transport=float(s)) for s,l in candidates],
                         selected_before_test=True,direction_fit_ids=[r["id"] for r in train],
                         selection_rule="maximum mean signed donor transport on validation; exclude terminal block 79",
                         ablation="h - u * dot(h - train_center, u)",alpha=1)
        write_json(destination / "selection.json",selection)
        np.savez(destination / "direction.npz",direction=direction,center=center)
        commit()
        print("Frozen intervention layer",layer,"; starting test and controls",flush=True)
        interventions = []
        test_rows = [r for r in rows if r["split"] == "test"]
        randoms = [np.random.default_rng(seed).normal(size=direction.shape).astype(np.float32) for seed in [42,43,44]]
        randoms = [v/np.linalg.norm(v) for v in randoms]
        for row in test_rows:
            budget()
            ident = row["id"]
            base = baseline[ident]
            h = cache[ident][layer,"answer"][0]
            removed = erase_direction(h,direction,center)
            delta = removed-h
            replacements = {"noop":h, "gender_erasure":removed}
            for seed,v in zip([42,43,44],randoms):
                replacements[f"random_{seed}"] = h+v*np.linalg.norm(delta)
            if row.get("donor_id"):
                replacements["counterfactual"] = cache[row["donor_id"]][layer,"answer"][0]
                # Other-family, same task/order/assignment donor can transfer
                # names/preferences without flipping the gender contrast.
                other = next(r for r in test_rows if r["family_id"] != row["family_id"] and
                             r["scenario"]==row["scenario"] and r["order"]==row["order"] and r["female_a"]==row["female_a"])
                replacements["same_gender_other_family"] = cache[other["id"]][layer,"answer"][0]
            for condition,vector in replacements.items():
                budget()
                stats,_ = instrument.forward(ident,intervention=(layer,"answer",[vector]))
                record = dict(id=ident,family_id=row["family_id"],scenario=row["scenario"],condition=condition,
                              female_a=row["female_a"],expected_merit_slot=row["expected_merit_slot"],
                              base_margin=base["margin"],delta_margin=stats["margin"]-base["margin"],
                              intervention_norm=float(np.linalg.norm(vector-h)),
                              preferred_slot_flip=base["preferred_slot"] != stats["preferred_slot"],**stats)
                if row.get("donor_id"):
                    record.update(transport_metrics(base["margin"],baseline[row["donor_id"]]["margin"],stats["margin"]))
                interventions.append(record)
                append(destination / "interventions.jsonl",record)
            print("Test/control",ident,flush=True)
            commit()
        # Original corpus transfer: final-token direction learned on English
        # explicit diagnostic prompts, no refitting by language/cue.
        for row in rows:
            if row["split"] != "transfer":
                continue
            budget()
            h = cache[row["id"]][layer,"answer"][0]
            stats,_ = instrument.forward(row["id"],intervention=(layer,"answer",[erase_direction(h,direction,center)]))
            append(destination / "transfer.jsonl",dict(id=row["id"],family_id=row["family_id"],lang=row["lang"],cue=row["cue"],
                   female_a=row["female_a"],base_margin=baseline[row["id"]]["margin"],condition="gender_erasure",**stats))
        print("Generating original-style held-out childcare answers",flush=True)
        for row in test_rows:
            if row["scenario"] != "childcare":
                continue
            budget()
            # Recompute the original-style prefill; diagnostic caches are not
            # transplanted into a differently formatted prompt.
            original_stats,original_vectors = instrument.forward(row["id"],mode="original",capture=True)
            h = original_vectors[layer,"answer"][0]
            for condition,intervention in [("baseline",None),("gender_erasure",(layer,"answer",[erase_direction(h,direction,center)]))]:
                budget()
                generated = instrument.generate(row["id"],intervention=intervention)
                append(destination / "generations.jsonl",dict(id=row["id"],family_id=row["family_id"],condition=condition,
                       female_a=row["female_a"],names=row["names"],prompt=row["prompt"],requires_rubric_review=True,**generated))
            commit()
        baseline_summary = []
        for split in ["train","validation","test","transfer"]:
            for task in sorted({r["scenario"] for r in rows if r["split"]==split}):
                for lang in sorted({r["lang"] for r in rows if r["split"]==split and r["scenario"]==task}):
                    selected = [r for r in rows if r["split"]==split and r["scenario"]==task and r["lang"]==lang]
                    values = [baseline[r["id"]] for r in selected]
                    baseline_summary.append(dict(split=split,scenario=task,lang=lang,n=len(selected),
                        top_is_ab_count=sum(v["top_is_ab"] for v in values),mean_ab_mass=float(np.mean([v["ab_mass"] for v in values])),
                        female_preferred_count=sum((v["margin"]>0)==bool(r["female_a"]) for r,v in zip(selected,values)) if task!="same_identity" else None,
                        merit_preferred_count=sum(v["preferred_slot"]==r["expected_merit_slot"] for r,v in zip(selected,values)) if task=="merit" else None))
        treatment_summary = []
        for task in sorted({r["scenario"] for r in interventions}):
            for condition in sorted({r["condition"] for r in interventions if r["scenario"]==task}):
                selected = [r for r in interventions if r["scenario"]==task and r["condition"]==condition]
                treatment_summary.append(dict(scenario=task,condition=condition,n=len(selected),
                    delta_margin=bootstrap_by_family(selected,"delta_margin"),
                    preferred_slot_flips=sum(r["preferred_slot_flip"] for r in selected),
                    female_preferred_count=sum((r["margin"]>0)==bool(r["female_a"]) for r in selected) if task!="same_identity" else None,
                    merit_preferred_count=sum(r["preferred_slot"]==r["expected_merit_slot"] for r in selected) if task=="merit" else None,
                    top_is_ab_count=sum(r["top_is_ab"] for r in selected),mean_ab_mass=float(np.mean([r["ab_mass"] for r in selected]))))
        summary = dict(status="completed",smoke=False,elapsed_seconds=time.monotonic()-started,
                       design_sha256=frozen["manifest"]["design_sha256"],selection=selection,
                       baseline=baseline_summary,interventions=treatment_summary,
                       generation_review_status="pending: do not infer stereotype repair from A/B margin",
                       limitation="12 English name families, one shared profile template; multilingual transfer is exploratory; public checkpoint differs from unverifiable hosted revision")
        write_json(destination / "summary.json",summary)
        status = "completed"
        return summary
    except Exception as exc:
        status = "failed"
        write_json(destination / "failure.json",dict(type=type(exc).__name__,message=str(exc),elapsed_seconds=time.monotonic()-started))
        raise
    finally:
        write_json(destination / "status.json",dict(status=status,elapsed_seconds=time.monotonic()-started))
        commit()
