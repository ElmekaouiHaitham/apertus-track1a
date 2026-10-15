"""Optional fresh judge inference on a few examples; never part of make run.

Self mode requires LLM_API_KEY. Clef mode downloads pinned 27B weights and
requires a CUDA GPU with at least 75 GiB memory. Both require --execute.
"""

import argparse
import importlib
import json
import os
from pathlib import Path
import sys
import time
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
REVISION = "0b331204bb13fbd2ca93a64df1956f5b55478ce5"


def self_judge(example, condition):
    bundle = json.loads(
        (ROOT / "docs/self_prompt_bundle.json").read_text(encoding="utf-8")
    )
    evidence = {
        "original_prompt": example["prompt"],
        "response_to_evaluate": example["response"],
        "generation_incomplete": False,
    }
    messages = [
        {"role": "system", "content": bundle["system"]},
        {
            "role": "user",
            "content": bundle["authorship_sentences"][condition]
            + bundle["evidence_separator"]
            + json.dumps(evidence, ensure_ascii=False),
        },
    ]
    payload = {
        "model": os.environ.get("LLM_NAME", "apertus-v1.5-70b"),
        "temperature": 0,
        "max_tokens": 1536,
        "messages": messages,
    }
    key = os.environ.get("LLM_API_KEY")
    if not key:
        raise SystemExit("Set LLM_API_KEY before fresh self-evaluation")
    url = (
        os.environ.get("LLM_BASE_URL", "https://hackapertus.livemap.sh/v1").rstrip("/")
        + "/chat/completions"
    )
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode(),
        headers={"Authorization": "Bearer " + key, "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=180) as stream:
        return {"request": payload, "response": json.load(stream)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=["self", "clef"], required=True)
    parser.add_argument("--case", default="H103")
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()
    if not args.execute:
        raise SystemExit(
            "No inference performed. Add --execute to request paid/API or GPU inference."
        )
    examples = json.loads((ROOT / "data/exemplars.json").read_text(encoding="utf-8"))
    example = next((r for r in examples if r["case_id"] == args.case), None)
    if not example:
        raise SystemExit("Case not present in data/exemplars.json")
    if args.mode == "self":
        result = {
            condition: self_judge(example, condition)
            for condition in ["apertus_blind", "apertus_self"]
        }
    else:
        # Optional dependencies intentionally excluded from the small offline image.
        import torch
        from huggingface_hub import snapshot_download

        if (
            not torch.cuda.is_available()
            or torch.cuda.get_device_properties(0).total_memory < 75 * 1024**3
        ):
            raise SystemExit(
                "Clef BF16 requires a CUDA GPU with at least 75 GiB; weights not downloaded"
            )
        path = snapshot_download("Cloudflare/clef", revision=REVISION)
        sys.path.insert(0, path)
        module = importlib.import_module("joint_schema_model")
        model, processor = module.load_release_model(path, device="cuda")
        questions = json.loads(
            (ROOT / "docs/clef_questions.json").read_text(encoding="utf-8")
        )
        payload = {
            "state": {
                "original_prompt": example["prompt"],
                "response_to_evaluate": example["response"],
                "generation_incomplete": False,
            },
            "model": "Cloudflare/clef",
            "questions": questions,
        }
        encoded = module.encode_record(
            processor.tokenizer, payload, max_length=1_000_000_000, processor=processor
        )
        if len(encoded.input_ids) > 16384:
            raise ValueError(
                "Input exceeds original 16,384-token limit; no truncation performed"
            )
        with torch.inference_mode():
            logits = model(
                module.collate_records(
                    [encoded],
                    processor.tokenizer.pad_token_id,
                    next(model.parameters()).device,
                )
            )[0]
        answers = {}
        for question, values in zip(encoded.questions, logits):
            probabilities = dict(
                zip(question.option_ids, values.float().softmax(-1).tolist())
            )
            answers[question.question_id] = (
                {"type": "noul", "noul": probabilities["true"]}
                if question.question_type == 0
                else {
                    "type": "choice",
                    "choice": max(probabilities, key=probabilities.get),
                    "probabilities": probabilities,
                }
            )
        result = {"request": payload, "model_revision": REVISION, "answers": answers}
    out = ROOT / "output"
    out.mkdir(exist_ok=True)
    destination = out / f"fresh_{args.mode}_{args.case}_{time.time_ns()}.json"
    destination.write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(destination)


if __name__ == "__main__":
    main()
