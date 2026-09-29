"""Measure precision and recall of the rules against a hand-labeled set of files.

    python -m house_style_linter.evaluate fixtures/labels.json

`labels.json` maps a file path (relative to the labels file) to a list of
`[line, rule]` pairs that a human reviewer marked as violations. Line 0 means "anywhere
in the piece" and is used for rules that judge the whole piece. A finding is a true
positive when a label exists for the same file, line and rule. Duplicates on one line
collapse to one.
"""
from __future__ import annotations

import argparse
import io
import json
import os
import sys
from typing import Dict, List, Set, Tuple

from .core import lint_text
from .options import Options
from .rules import RULES_BY_ID

PIECE_RULES = {"next-step", "flat-rhythm", "hedge-density", "triple-habit", "length-limit"}
Key = Tuple[str, int, str]


def _norm(path: str, line: int, rule: str) -> Key:
    return (path, 0 if rule in PIECE_RULES else line, rule)


def _stats(found: Set[Key], labels: Set[Key]) -> Dict[str, object]:
    tp = found & labels
    fp = found - labels
    fn = labels - found
    p = len(tp) / len(found) if found else 1.0
    r = len(tp) / len(labels) if labels else 1.0
    return {
        "findings": len(found),
        "labels": len(labels),
        "true_positives": len(tp),
        "false_positives": sorted(fp),
        "misses": sorted(fn),
        "precision": p,
        "recall": r,
    }


def evaluate(labels_path: str, options: Options = None) -> Dict[str, object]:
    root = os.path.dirname(os.path.abspath(labels_path))
    with io.open(labels_path, encoding="utf-8") as fh:
        raw = json.load(fh)
    unknown = sorted({rule for pairs in raw.values() for _, rule in pairs} - set(RULES_BY_ID))
    if unknown:
        raise ValueError("labels use unknown rules: %s" % ", ".join(unknown))

    found_by_set: Dict[str, Set[Key]] = {}
    labels_by_set: Dict[str, Set[Key]] = {}
    error_found: Set[Key] = set()
    for rel, pairs in sorted(raw.items()):
        subset = rel.split("/", 1)[0]
        with io.open(os.path.join(root, rel), encoding="utf-8") as fh:
            text = fh.read()
        for f in lint_text(text, options):
            key = _norm(rel, f.line, f.rule)
            found_by_set.setdefault(subset, set()).add(key)
            if f.severity == "error":
                error_found.add(key)
        for line, rule in pairs:
            labels_by_set.setdefault(subset, set()).add(_norm(rel, line, rule))

    out: Dict[str, object] = {}
    for subset in sorted(set(found_by_set) | set(labels_by_set)):
        out[subset] = _stats(found_by_set.get(subset, set()), labels_by_set.get(subset, set()))
    all_found = set().union(*found_by_set.values()) if found_by_set else set()
    all_labels = set().union(*labels_by_set.values()) if labels_by_set else set()
    out["all"] = _stats(all_found, all_labels)
    out["errors_only"] = _stats(
        error_found, {k for k in all_labels if RULES_BY_ID[k[2]].severity == "error"}
    )
    out["files"] = len(raw)
    out["clean_files"] = sum(1 for pairs in raw.values() if not pairs)
    return out


def main(argv: List[str] = None) -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass
    ap = argparse.ArgumentParser(prog="house_style_linter.evaluate", description=__doc__.split("\n")[0])
    ap.add_argument("labels", help="path to labels.json")
    ap.add_argument("--show", action="store_true", help="list every false positive and miss")
    args = ap.parse_args(argv)
    res = evaluate(args.labels)
    print("files: %d (%d with no labeled violations)" % (res["files"], res["clean_files"]))
    print("%-12s %9s %7s %6s %6s %10s %8s" % ("set", "findings", "labels", "TP", "FP", "precision", "recall"))
    for name in [k for k in res if k not in ("files", "clean_files")]:
        s = res[name]
        print("%-12s %9d %7d %6d %6d %9.1f%% %7.1f%%" % (
            name, s["findings"], s["labels"], s["true_positives"], len(s["false_positives"]),
            100 * s["precision"], 100 * s["recall"]))
    if args.show:
        s = res["all"]
        print("\nfalse positives:")
        for k in s["false_positives"]:
            print("  %s line %d  %s" % k)
        print("misses:")
        for k in s["misses"]:
            print("  %s line %d  %s" % k)
    return 0


if __name__ == "__main__":
    sys.exit(main())
