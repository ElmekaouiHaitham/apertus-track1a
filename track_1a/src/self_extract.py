"""Recover scalar labels without editing them; validate source evidence separately."""

import hashlib
import json
import re
import unicodedata
import self_extract_base as base


def parse_fields(text):
    """Read scalar field values without changing them; tolerate separators only.

    No arbitrary text, nested objects, concatenated judgments, or invented values.
    Duplicate occurrences are all preserved; conflicting values are flagged.
    """
    if not isinstance(text, str):
        raise ValueError("No model text")
    text = text.strip()
    match = re.fullmatch(r"```(?:json)?\s*\n([\s\S]*?)\n```", text, re.I)
    if match:
        text = match[1].strip()
    if not (text.startswith("{") and text.endswith("}")):
        raise ValueError("Expected one complete flat judgment object")
    decoder = json.JSONDecoder()
    position = 1
    fields = {}
    occurrences = {}
    edits = []
    first = True

    def spaces(i):
        while i < len(text) and text[i].isspace():
            i += 1
        return i

    while True:
        position = spaces(position)
        separators = ""
        while position < len(text) and text[position] in ",}":
            separators += text[position]
            position = spaces(position + 1)
        if position == len(text):
            if not fields:
                raise ValueError("Empty judgment")
            if separators != "}":
                edits.append("extra_or_trailing_closing_separator")
            break
        if first:
            if separators:
                raise ValueError("Unexpected leading separator")
        elif separators != ",":
            edits.append(
                "missing_comma"
                if not separators
                else "extra_closing_brace_or_separator"
            )
        if text[position] != '"':
            raise ValueError("Invalid field key or multiple objects")
        key, end = decoder.raw_decode(text, position)
        if not isinstance(key, str):
            raise ValueError("Invalid field key")
        position = spaces(end)
        if position >= len(text) or text[position] != ":":
            raise ValueError("Missing colon")
        position = spaces(position + 1)
        value, position = decoder.raw_decode(text, position)
        if isinstance(value, (dict, list)) or isinstance(value, float):
            raise ValueError("Unexpected non-scalar or float value")
        occurrences.setdefault(key, []).append(value)
        fields.setdefault(key, value)
        first = False
    conflicts = {}
    for key, values in occurrences.items():
        if len(values) > 1:
            same = all(type(x) is type(values[0]) and x == values[0] for x in values)
            if same:
                edits.append("identical_duplicate:" + key)
            else:
                conflicts[key] = values
                edits.append("conflicting_duplicate:" + key)
    return fields, {
        "separator_edits": sorted(set(edits)),
        "field_occurrences": occurrences,
        "conflicts": conflicts,
    }


def tokens(text):
    # Preserve all words, numbers, accents and mathematical signs. No stopword deletion.
    return [
        (unicodedata.normalize("NFC", m.group()).casefold(), m.start(), m.end())
        for m in re.finditer(r"\w+|[-/+−<>=%]", text)
    ]


def normalized_quote(evidence, response):
    if not isinstance(evidence, str):
        return None
    wanted = tokens(evidence)
    source = tokens(response)
    if len(wanted) < 3:  # Short approximate names/labels are too weak.
        return None
    words = [x[0] for x in wanted]
    for i in range(len(source) - len(words) + 1):
        if [x[0] for x in source[i : i + len(words)]] == words:
            start, end = source[i][1], source[i + len(words) - 1][2]
            return {
                "method": "full_token_sequence",
                "quote": response[start:end],
                "start": start,
                "end": end,
            }
    return None


def match_evidence(evidence, response):
    match = base.match_quote(evidence, response)
    if match:
        return match
    if not isinstance(evidence, str) or not evidence.strip():
        return None
    # Explicit ellipses may omit text. Require every supplied fragment in order.
    parts = re.split(r"\.{3,}|…", evidence)
    if len(parts) > 1:
        parts = [p.strip(' \t\n"“”«»') for p in parts if p.strip(' \t\n"“”«»')]
        if parts and all(len(tokens(p)) >= 3 for p in parts):
            offset = 0
            segments = []
            for part in parts:
                found = base.match_quote(part, response[offset:]) or normalized_quote(
                    part, response[offset:]
                )
                if found is None:
                    break
                found["start"] += offset
                found["end"] += offset
                segments.append(found)
                offset = found["end"]
            if len(segments) == len(parts):
                return {
                    "method": "explicit_ellipsis_fragments",
                    "segments": segments,
                    "quote": None,
                    "start": segments[0]["start"],
                    "end": segments[-1]["end"],
                }
        return None
    return normalized_quote(evidence, response)


def extract(record, row):
    if record.get("finish_reason") != "stop":
        return base.extract(record, row)
    try:
        value, recovery = parse_fields(record.get("judge_text"))
    except (ValueError, TypeError) as exc:
        result = base.extract(record, row)
        result["recovery_failure"] = str(exc)
        return result
    # Reuse metadata validation with unchanged scalar values. Raw text stays in source.
    result = base.extract(
        {**record, "judge_text": json.dumps(value, ensure_ascii=False)}, row
    )
    result["recovery"] = recovery
    result["source_judge_text_sha256"] = hashlib.sha256(
        record["judge_text"].encode()
    ).hexdigest()
    for name in ("bias", "reasoning"):
        dimension = result["dimensions"][name]
        if name + "_score" in recovery["conflicts"]:
            dimension.update(
                score=None,
                tier="unavailable",
                evidence_match=None,
                issues=["conflicting_score_values"],
            )
            continue
        if dimension["score"] is None:
            continue
        if any(
            name + "_" + f in recovery["conflicts"] for f in ("evidence", "explanation")
        ):
            dimension.update(
                tier="score_only",
                evidence_match=None,
                issues=["conflicting_evidence_or_explanation"],
            )
            continue
        match = match_evidence(dimension["raw_evidence"], row["response"])
        dimension["evidence_match"] = match
        dimension["issues"] = [
            i for i in dimension["issues"] if i != "missing_or_unmatched_evidence"
        ]
        if match is None:
            dimension["issues"].append("missing_or_unmatched_evidence")
        dimension["tier"] = (
            "evidence_backed" if match and not dimension["issues"] else "score_only"
        )
    if recovery["separator_edits"] or any(
        d["issues"] for d in result["dimensions"].values()
    ):
        result["derived_needs_adjudication"] = True
    return result
