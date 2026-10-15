"""Optional fresh Apertus requests. Offline reproduction never calls this file.

Use LLM_NAME, LLM_BASE_URL and LLM_API_KEY. Responses may differ from the
historical collection: temperature=.7, hosted checkpoint revision unreported.
No automatic bias labeling: fresh outputs require review using docs/rubric.md.
"""

import argparse
import json
import os
from pathlib import Path
import time
import urllib.request

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--finding", default="all")
    parser.add_argument("--limit", type=int, default=3)
    args = parser.parse_args()
    key = os.environ.get("LLM_API_KEY")
    if not key:
        raise SystemExit(
            "Set LLM_API_KEY for optional live replay. Offline: python src/reproduce.py"
        )
    base = os.environ.get("LLM_BASE_URL", "https://hackapertus.livemap.sh/v1").rstrip(
        "/"
    )
    model = os.environ.get("LLM_NAME", "apertus-v1.5-70b")
    cases = json.loads((ROOT / "data/exemplars.json").read_text(encoding="utf-8"))
    selected = [
        r for r in cases if args.finding == "all" or r["finding"] == args.finding
    ][: args.limit]
    out = ROOT / "output"
    out.mkdir(exist_ok=True)
    destination = out / f"live_replay_{time.time_ns()}.jsonl"
    for case in selected:
        payload = {
            "model": model,
            "temperature": 0.7,
            "max_tokens": 1024,
            "messages": [{"role": "user", "content": case["prompt"]}],
        }
        request = urllib.request.Request(
            base + "/chat/completions",
            data=json.dumps(payload).encode(),
            headers={
                "Authorization": "Bearer " + key,
                "Content-Type": "application/json",
            },
        )
        with urllib.request.urlopen(request, timeout=180) as response:
            result = json.load(response)
        record = {
            "case_id": case["case_id"],
            "finding": case["finding"],
            "request": payload,
            "response": result,
            "endpoint": base,
        }
        with destination.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(record, ensure_ascii=False) + "\n")
        print("Saved fresh response for", case["case_id"])
    print(destination)


if __name__ == "__main__":
    main()
