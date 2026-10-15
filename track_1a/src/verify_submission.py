"""Validate the final Track 1A deliverable contract after evidence reproduction."""

import hashlib
import json
from pathlib import Path
import re

from pypdf import PdfReader
from jsonschema import Draft202012Validator,FormatChecker

ROOT=Path(__file__).resolve().parents[1]


def main():
    required=["README.md","Makefile","Dockerfile","technical_report.md","findings/findings.schema",
              "ApertusChoiceAudit_Report.pdf","docs/REPRODUCIBILITY.md","docs/FINAL_VALIDATION.md"]
    for name in required:
        if not (ROOT/name).is_file():raise ValueError("Missing required deliverable: "+name)
    raw=(ROOT/"docs/audit/upstream_20261015/findings.schema").read_text(encoding="utf-8")
    schema=json.loads((ROOT/"findings/findings.schema").read_text(encoding="utf-8"))
    if schema!=json.loads(raw,strict=False):raise ValueError("Schema rules differ from organizer template")
    validator=Draft202012Validator(schema,format_checker=FormatChecker())
    files=sorted((ROOT/"findings").glob("*.json"))
    if len(files)!=4:raise ValueError("The submitted findings directory must contain only four real issues")
    conversations=0
    for path in files:
        value=json.loads(path.read_text(encoding="utf-8"));validator.validate(value)
        conversations+=len(value["apertus_response_walkthroughs"])
    if conversations!=18:raise ValueError("Expected 16 historical plus two public baseline walkthroughs")
    report=(ROOT/"technical_report.md").read_text(encoding="utf-8")
    expected=["Problem","Red Teaming Method","Findings Dataset","Lessons Learnt and Recommendations","Reproducibility","License","References"]
    if re.findall(r"^## (.+)$",report,re.M)!=expected:raise ValueError("Official report sections/order changed")
    pdf=ROOT/"ApertusChoiceAudit_Report.pdf"
    reader=PdfReader(pdf)
    text=[page.extract_text() or "" for page in reader.pages]
    refs=[i for i,t in enumerate(text) if re.search(r"(?m)^References\s*$",t)]
    if len(text)>6 or len(refs)!=1:raise ValueError("Report exceeds six total pages including references, or references are not identifiable")
    ref_heading=re.search(r"(?m)^References\s*$",text[refs[0]])
    shared_reference_page=bool(text[refs[0]][:ref_heading.start()].strip())
    full="\n".join(text)
    for phrase in ["White-box supplement","16/16","0/16","2/16","6/8","License","Reproducibility"]:
        if phrase not in full:raise ValueError("Integrated report is missing supported result/limit: "+phrase)
    upstream=json.loads((ROOT/"docs/audit/upstream_20261015/manifest.json").read_text())
    for original,entry in upstream["files"].items():
        source=ROOT/"docs/audit/upstream_20261015"/entry["local"]
        if hashlib.sha256(source.read_bytes()).hexdigest()!=entry["sha256"]:raise ValueError("Upstream reference changed: "+original)
    summary=dict(verified=True,issues=4,walkthroughs=conversations,organizer_schema_rules_unchanged=True,
                 official_report_structure=True,report_total_pages=len(text),
                 report_content_pages=refs[0]+int(shared_reference_page),report_reference_pages=len(text)-refs[0],
                 references_share_last_content_page=shared_reference_page,
                 report_sha256=hashlib.sha256(pdf.read_bytes()).hexdigest(),
                 historical_and_supplementary_sources_kept_distinct=True,
                 offline_replay="Frozen evidence and recorded measurements; no live inference or probe retraining")
    (ROOT/"output/final_submission_contract.json").write_text(json.dumps(summary,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(summary,indent=2))


if __name__=="__main__":main()
