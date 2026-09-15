#!/usr/bin/env python3
"""Compare two candidate TSV dumps produced by evaluate_contrast_sets.lua."""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from pathlib import Path


def top_rows(path: Path) -> dict[int, dict[str, str]]:
    result: dict[int, dict[str, str]] = {}
    with path.open(encoding="utf-8", newline="") as stream:
        for row in csv.DictReader(stream, delimiter="\t"):
            case = int(row["case"])
            if case not in result or int(row["rank"]) < int(result[case]["rank"]):
                result[case] = row
    if not result:
        raise ValueError(f"no candidate rows in {path}")
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("baseline", type=Path)
    parser.add_argument("candidate", type=Path)
    parser.add_argument("--examples", type=int, default=10)
    args = parser.parse_args()

    baseline = top_rows(args.baseline)
    candidate = top_rows(args.candidate)
    if baseline.keys() != candidate.keys():
        raise SystemExit("candidate dumps do not contain the same case identifiers")

    totals: Counter[str] = Counter()
    domains: dict[str, Counter[str]] = {}
    examples: dict[str, list[dict[str, str]]] = {"rescued": [], "regressed": []}
    for case in sorted(baseline):
        old, new = baseline[case], candidate[case]
        if old["target"] != new["target"]:
            raise SystemExit(f"target mismatch for case {case}")
        old_correct = old["text"] == old["target"]
        new_correct = new["text"] == new["target"]
        if old_correct and new_correct:
            outcome = "retained_correct"
        elif not old_correct and new_correct:
            outcome = "rescued"
        elif old_correct and not new_correct:
            outcome = "regressed"
        elif old["text"] != new["text"]:
            outcome = "changed_wrong"
        else:
            outcome = "unchanged_wrong"
        totals[outcome] += 1
        domain = new.get("domain") or old.get("domain") or "unknown"
        domains.setdefault(domain, Counter())[outcome] += 1
        if outcome in examples and len(examples[outcome]) < args.examples:
            examples[outcome].append({
                "case": str(case),
                "domain": domain,
                "target": new["target"],
                "baseline": old["text"],
                "candidate": new["text"],
            })

    payload = {
        "cases": len(baseline),
        "baseline_correct": totals["retained_correct"] + totals["regressed"],
        "candidate_correct": totals["retained_correct"] + totals["rescued"],
        "rescued": totals["rescued"],
        "regressed": totals["regressed"],
        "changed_wrong": totals["changed_wrong"],
        "unchanged_wrong": totals["unchanged_wrong"],
        "domains": {name: dict(values) for name, values in sorted(domains.items())},
        "examples": examples,
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
