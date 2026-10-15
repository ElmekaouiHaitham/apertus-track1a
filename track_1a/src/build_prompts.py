"""Regenerate and verify the choice prompts while preserving historical IDs.

The archived generator constructs its historical full grid before filtering.
That ordering is necessary to reproduce original IDs, tiers and pair IDs.
Only active choice rows are exported or evaluated in this submission.
"""

import csv
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    spec = importlib.util.spec_from_file_location(
        "original_builder", ROOT / "docs/audit/original_dataset_builder.py"
    )
    builder = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(builder)
    units = builder.build(["neutral"], include_controls=True, include_excluded=True)
    tiers = builder.assign_tiers(units)
    rows = []
    index = 0
    for _, key, members in units:
        for row in members:
            row.update(id=f"{index:05d}", pair_id=key, tier=tiers[key])
            index += 1
            row["ideal_behavior"] = (
                builder.IDEAL["social"]
                if row["domain"] == "social"
                else builder.IDEAL[row["task"]]
            )
            if row["task"] == "choice" and not builder.excluded_from_active_scope(row):
                rows.append(row)
    with (ROOT / "data/prompts.csv").open(encoding="utf-8", newline="") as stream:
        reader = csv.DictReader(stream)
        fields = reader.fieldnames
        recorded = list(reader)
    assert len(rows) == len(recorded) == 2582
    for left, right in zip(rows, recorded):
        for field in fields:
            if str(left[field]) != right[field]:
                raise ValueError(f'Prompt generation mismatch {right["id"]}: {field}')
    destination = ROOT / "output/prompts.regenerated.csv"
    destination.parent.mkdir(exist_ok=True)
    with destination.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    print("Verified all 2,582 choice prompts and original IDs:", destination)


if __name__ == "__main__":
    main()
