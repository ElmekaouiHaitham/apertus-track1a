"""Download compact evidence from an existing run, excluding activations.

This reads an existing Modal volume; it never launches inference.
"""

import argparse
import hashlib
import json
from pathlib import Path


def collect(run_id):
    import modal
    if not run_id.replace("-","").replace("_","").isalnum():
        raise ValueError("Invalid run ID")
    volume = modal.Volume.from_name("apertus-gender-whitebox-results")
    destination = Path(__file__).resolve().parent / "evidence" / run_id
    destination.mkdir(parents=True,exist_ok=True)
    hashes = {}
    for entry in volume.iterdir("/"+run_id,recursive=False):
        name = Path(entry.path).name
        if name in ["activations","analysis"]:
            continue
        if Path(name).suffix not in [".json",".jsonl",".npz",".py"]:
            continue
        data = b"".join(volume.read_file(entry.path))
        path = destination / name
        if path.exists() and path.read_bytes()!=data:
            # The Windows launcher writes CRLF while the remote source uses LF.
            # Preserve the launcher copy and accept only semantic JSON identity.
            if name=="summary.json" and json.loads(path.read_bytes())==json.loads(data):
                backup = destination / "summary.launcher.json"
                if not backup.exists():
                    backup.write_bytes(path.read_bytes())
            else:
                raise RuntimeError("Local evidence differs; preserve it before recollecting: "+str(path))
        path.write_bytes(data)
        hashes[name] = hashlib.sha256(data).hexdigest()
    (destination / "manifest.json").write_text(json.dumps(dict(files=hashes,
        source_volume="apertus-gender-whitebox-results",run_id=run_id,
        activations="Retained in the remote volume; not needed for CPU result verification"),indent=2)+"\n",encoding="utf-8")
    print(destination)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run_id")
    collect(parser.parse_args().run_id)
