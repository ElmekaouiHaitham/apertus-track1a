"""Modal launcher; no live jobs on import. Run --stage preflight before --stage study.

Uses the existing read-only 70B weight volume and HF secret. Does not upload
the workspace, private .env, original response corpus, or human-review data.
"""

import json
from pathlib import Path

import modal

HERE = Path(__file__).resolve().parent
MODEL_REVISION = "94888dd0db53f674b4c5304c1b726a7783d21393"
TRANSFORMERS_COMMIT = "3797303dda74844e3d1f8977ff5518bb91f818b4"
app = modal.App("apertus-gender-childcare-whitebox")
weights = modal.Volume.from_name("apertus-v1-5-70b-weights")
results = modal.Volume.from_name("apertus-gender-whitebox-results", create_if_missing=True)
secret = modal.Secret.from_name("apertus-hf")
base = (modal.Image.debian_slim(python_version="3.11")
        .apt_install("git")
        .pip_install("huggingface-hub==0.36.0", "numpy==2.2.6", "scikit-learn==1.7.2", "matplotlib==3.10.3")
        .env({"PYTHONUNBUFFERED": "1", "HF_HUB_DISABLE_PROGRESS_BARS": "1"}))
inference = (base.pip_install("torch==2.9.0", "torchvision==0.24.0", "torchaudio==2.9.0", "accelerate==1.10.1")
             .pip_install(f"transformers[vision,audio] @ git+https://github.com/swiss-ai/transformers.git@{TRANSFORMERS_COMMIT}")
             .add_local_file(HERE / "design.json", "/study/design.json")
             .add_local_file(HERE / "experiment.py", "/study/experiment.py"))
natural_image=(inference.add_local_file(HERE/"natural_design.json","/study/natural_design.json")
    .add_local_file(HERE/"natural_experiment.py","/study/natural_experiment.py")
    .add_local_file(HERE.parents[1]/"src/choice_parser.py" if len(HERE.parents)>1 else Path("/study/choice_parser.py"),"/study/choice_parser.py"))


@app.function(image=base, secrets=[secret], cpu=2, memory=4096,
              volumes={"/weights": weights.with_mount_options(read_only=True), "/results": results},
              timeout=1800, retries=0, max_containers=1, scaledown_window=2)
def preflight():
    """Hash every cached weight shard on CPU against pinned HF LFS metadata."""
    import hashlib
    import os
    import time
    from huggingface_hub import HfApi, hf_hub_download
    root = Path("/weights/apertus-v1.5-70b")
    token = os.environ.get("HF_TOKEN") or os.environ.get("HUGGING_FACE_HUB_TOKEN")
    info = HfApi(token=token).model_info("swiss-ai/Apertus-v1.5-70B", revision=MODEL_REVISION, files_metadata=True)
    report = {"model_revision": info.sha, "files": {}, "all_verified": False}
    for name in ["config.json", "model.safetensors.index.json", "tokenizer.json", "tokenizer_config.json", "chat_template.jinja"]:
        official = Path(hf_hub_download(info.id, name, revision=MODEL_REVISION, token=token))
        local = root / name
        digest = hashlib.sha256(local.read_bytes()).hexdigest()
        if digest != hashlib.sha256(official.read_bytes()).hexdigest():
            raise ValueError("Cached metadata/tokenizer differs from pinned checkpoint: " + name)
        report["files"][name] = {"sha256": digest, "verified": True}
    index = json.loads((root / "model.safetensors.index.json").read_text())
    siblings = {x.rfilename: x for x in info.siblings}
    for name in sorted(set(index["weight_map"].values())):
        started = time.monotonic()
        expected = siblings[name].lfs.sha256
        hasher = hashlib.sha256()
        with (root / name).open("rb") as stream:
            while chunk := stream.read(16 * 1024**2):
                hasher.update(chunk)
        digest = hasher.hexdigest()
        if digest != expected:
            raise ValueError("Weight hash mismatch: " + name)
        report["files"][name] = {"sha256": digest, "verified": True, "seconds": time.monotonic()-started}
        print("Verified", name, flush=True)
    report["all_verified"] = True
    destination = Path("/results/preflight.json")
    destination.write_text(json.dumps(report, indent=2)+"\n")
    results.commit()
    return report


@app.function(image=inference, cpu=2, memory=8192,
              volumes={"/weights": weights.with_mount_options(read_only=True), "/results": results},
              timeout=300, retries=0, max_containers=1, scaledown_window=2)
def prepare():
    """Validate processor/model support and every continuation without a GPU."""
    import importlib.util
    from types import SimpleNamespace
    import torch
    from transformers import AutoConfig, AutoModelForMultimodalLM, AutoProcessor
    root = Path("/weights/apertus-v1.5-70b")
    config = AutoConfig.from_pretrained(root,local_files_only=True)
    model_class = AutoModelForMultimodalLM._model_mapping[type(config)]
    processor = AutoProcessor.from_pretrained(root,local_files_only=True)
    spec = importlib.util.spec_from_file_location("whitebox_experiment", "/study/experiment.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    from accelerate import init_empty_weights
    # Validate the actual composite architecture without allocating 70B weights.
    with init_empty_weights():
        model = AutoModelForMultimodalLM.from_config(config,attn_implementation=module.ATTENTION)
    if len(model.model.language_model.layers) != 80:
        raise RuntimeError("Unexpected decoder architecture")
    del model
    frozen = json.loads(Path("/study/design.json").read_text())
    stub = SimpleNamespace(model=SimpleNamespace(language_model=SimpleNamespace(layers=[None]*80)),
                           get_input_embeddings=lambda:SimpleNamespace(weight=torch.empty(1)))
    instrument = module.Instrument(stub,processor,frozen["records"],frozen["manifest"]["coarse_layers"])
    encodings = [{"id":ident,"mode":mode,"input_ids":value["input_ids"],
                  "positions":value["positions"],"candidate_ids":value["candidates"],
                  "prompt_tokens":value["prompt_tokens"]} for (ident,mode),value in instrument.encoded.items()]
    report = dict(model_class=model_class.__name__,processor_class=type(processor).__name__,construction_checked=True,
                  design_sha256=frozen["manifest"]["design_sha256"],encodings=encodings,passed=True)
    Path("/results/prepare.json").write_text(json.dumps(report,indent=2)+"\n")
    results.commit()
    return report


@app.function(image=inference, cpu=4, memory=(32768, 131072), gpu="A100-80GB:2",
              volumes={"/weights": weights.with_mount_options(read_only=True), "/results": results},
              timeout=5400, retries=0, max_containers=1, scaledown_window=2)
def study(run_id: str, smoke: bool = False):
    import importlib.util
    if not run_id.replace("-", "").replace("_", "").isalnum():
        raise ValueError("Invalid run ID")
    proof = json.loads(Path("/results/preflight.json").read_text())
    if not proof["all_verified"] or proof["model_revision"] != MODEL_REVISION:
        raise RuntimeError("Run CPU preflight first")
    preparation = json.loads(Path("/results/prepare.json").read_text())
    frozen = json.loads(Path("/study/design.json").read_text())
    if not preparation["passed"] or preparation["design_sha256"] != frozen["manifest"]["design_sha256"]:
        raise RuntimeError("Run CPU prepare after freezing the design")
    spec = importlib.util.spec_from_file_location("whitebox_experiment", "/study/experiment.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    destination = Path("/results") / run_id
    if destination.exists():
        raise RuntimeError("Use a fresh run ID; existing study evidence is never overwritten")
    try:
        return module.run(Path("/weights/apertus-v1.5-70b"), destination,
                          Path("/study/design.json"), smoke=smoke, commit=results.commit)
    finally:
        results.commit()


@app.local_entrypoint()
def main(stage: str = "preflight", run_id: str = "gender-20261015-v1", smoke: bool = False):
    if stage == "preflight":
        report = preflight.remote()
        destination = HERE / "evidence/preflight.json"
    elif stage == "prepare":
        report = prepare.remote()
        destination = HERE / "evidence/prepare.json"
    elif stage == "study":
        report = study.remote(run_id, smoke)
        destination = HERE / f"evidence/{run_id}/summary.json"
    elif stage == "natural-prepare":
        report=natural_prepare.remote()
        destination=HERE/"evidence/natural_prepare.json"
    elif stage == "natural-study":
        # Recheck the exact mounted implementation and native tokenization on
        # CPU before allocating GPUs; stale prepare files cannot authorize a run.
        natural_prepare.remote()
        report=natural_study.remote(run_id)
        destination=HERE/f"evidence/{run_id}/summary.json"
    else:
        raise ValueError("stage must be preflight, prepare, study, natural-prepare or natural-study")
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(report, indent=2, ensure_ascii=False)+"\n", encoding="utf-8")
    print("Saved", destination)


@app.function(image=natural_image,cpu=2,memory=8192,
    volumes={"/weights":weights.with_mount_options(read_only=True),"/results":results},
    timeout=300,retries=0,max_containers=1,scaledown_window=2)
def natural_prepare():
    import hashlib
    import sys
    from types import SimpleNamespace
    import torch
    from transformers import AutoProcessor
    sys.path.insert(0,"/study")
    from natural_experiment import NaturalInstrument
    processor=AutoProcessor.from_pretrained("/weights/apertus-v1.5-70b",local_files_only=True)
    frozen=json.loads(Path("/study/natural_design.json").read_text())
    stub=SimpleNamespace(model=SimpleNamespace(language_model=SimpleNamespace(layers=[None]*80)),
        get_input_embeddings=lambda:SimpleNamespace(weight=torch.empty(1)))
    instrument=NaturalInstrument(stub,processor,frozen["records"])
    report=dict(passed=True,design_sha256=frozen["manifest"]["design_sha256"],
        source_sha256=hashlib.sha256(Path("/study/natural_experiment.py").read_bytes()).hexdigest(),
        n_encodings=len(instrument.encoded),distinct_name_starts=sum(v["distinct_name_starts"] for v in instrument.encoded.values()),
        encodings=[dict(id=ident,input_ids=v["input_ids"],positions=v["positions"],name_ids=v["name_ids"],prompt_tokens=v["prompt_tokens"])
                   for ident,v in instrument.encoded.items()])
    Path("/results/natural_prepare.json").write_text(json.dumps(report,indent=2)+"\n")
    results.commit()
    return report


@app.function(image=natural_image,cpu=4,memory=(32768,131072),gpu="A100-80GB:2",
    volumes={"/weights":weights.with_mount_options(read_only=True),"/results":results},
    timeout=5400,retries=0,max_containers=1,scaledown_window=2)
def natural_study(run_id: str):
    import hashlib
    import sys
    if not run_id.replace("-","").replace("_","").isalnum():raise ValueError("Invalid run ID")
    proof=json.loads(Path("/results/preflight.json").read_text())
    prepared=json.loads(Path("/results/natural_prepare.json").read_text())
    design=json.loads(Path("/study/natural_design.json").read_text())
    if not proof["all_verified"] or proof["model_revision"]!=MODEL_REVISION:raise RuntimeError("Missing weight proof")
    if not prepared["passed"] or prepared["design_sha256"]!=design["manifest"]["design_sha256"]:
        raise RuntimeError("Run natural-prepare first")
    if prepared["source_sha256"]!=hashlib.sha256(Path("/study/natural_experiment.py").read_bytes()).hexdigest():
        raise RuntimeError("Implementation changed after CPU prepare")
    destination=Path("/results")/run_id
    if destination.exists():raise RuntimeError("Use a fresh run ID")
    sys.path.insert(0,"/study")
    from natural_experiment import run
    try:return run(Path("/weights/apertus-v1.5-70b"),destination,Path("/study/natural_design.json"),commit=results.commit)
    finally:results.commit()
