"""Command line entry point."""
from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import replace
from typing import Iterable, List, Optional, Tuple

from . import __version__
from .core import Finding, lint_text
from .options import ConfigError, Options, load_config
from .rules import RULES, RULES_BY_ID

EXTENSIONS = (".md", ".markdown", ".txt")
SKIP_DIRS = {".git", "node_modules", "__pycache__", ".venv", "venv", "dist", "build"}
CONFIG_NAME = ".house-style.json"


def _collect(paths: Iterable[str]) -> List[str]:
    files: List[str] = []
    for p in paths:
        if p == "-":
            files.append(p)
        elif os.path.isdir(p):
            for root, dirs, names in os.walk(p):
                dirs[:] = sorted(d for d in dirs if d not in SKIP_DIRS and not d.startswith("."))
                for n in sorted(names):
                    if n.lower().endswith(EXTENSIONS):
                        files.append(os.path.join(root, n))
        else:
            files.append(p)
    return files


def _read(path: str) -> str:
    if path == "-":
        return sys.stdin.read()
    with open(path, encoding="utf-8-sig") as fh:
        return fh.read()


def _build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(
        prog="house_style_linter",
        description="Check copy against house-style rules. Standard library only.",
    )
    ap.add_argument("paths", nargs="*", help="files or folders to check, or - for standard input")
    ap.add_argument("--format", choices=("text", "json"), default="text", help="output format")
    ap.add_argument("--strict", action="store_true", help="exit 1 on warnings as well as errors")
    ap.add_argument("--require-next-step", action="store_true",
                    help="require a closing request, date or link (for client-facing copy)")
    ap.add_argument("--max-words", type=int, metavar="N", help="flag pieces longer than N words")
    ap.add_argument("--disable", metavar="RULES", help="comma-separated rule ids to skip")
    ap.add_argument("--config", metavar="FILE", help="JSON config file (default: ./%s if present)" % CONFIG_NAME)
    ap.add_argument("--no-config", action="store_true", help="ignore any config file")
    ap.add_argument("--include-code", action="store_true", help="also check code blocks and inline code")
    ap.add_argument("--list-rules", action="store_true", help="print every rule and exit")
    ap.add_argument("--version", action="version", version="house-style-linter " + __version__)
    return ap


def _list_rules() -> None:
    width = max(len(r.id) for r in RULES)
    for group in ("mechanics", "language", "claims", "shape"):
        print(group)
        for r in RULES:
            if r.group == group:
                tag = r.severity + (", opt-in" if r.opt_in else "")
                print("  %-*s  %-14s %s" % (width, r.id, tag, r.summary))


def _resolve_options(args) -> Options:
    opts = Options()
    cfg = args.config
    if not args.no_config:
        if cfg:
            opts = load_config(cfg, opts)
        elif os.path.isfile(CONFIG_NAME):
            opts = load_config(CONFIG_NAME, opts)
    changes = {}
    if args.require_next_step:
        changes["require_next_step"] = True
    if args.max_words is not None:
        if args.max_words < 1:
            raise ConfigError("--max-words must be at least 1")
        changes["max_words"] = args.max_words
    if args.include_code:
        changes["include_code"] = True
    if args.disable:
        ids = tuple(x.strip() for x in args.disable.split(",") if x.strip())
        unknown = [i for i in ids if i not in RULES_BY_ID]
        if unknown:
            raise ConfigError("unknown rule id: %s (see --list-rules)" % ", ".join(unknown))
        changes["disable"] = tuple(opts.disable) + ids
    return replace(opts, **changes) if changes else opts


def _print_text(results: List[Tuple[str, List[Finding]]], checked: int) -> None:
    errors = warns = 0
    dirty = 0
    for path, findings in results:
        if not findings:
            continue
        dirty += 1
        print(path)
        for f in findings:
            print("  %d:%d  %-5s  %-22s %s" % (f.line, f.col, f.severity, f.rule, f.message))
            if f.snippet:
                print("        > %s" % f.snippet)
            errors += f.severity == "error"
            warns += f.severity == "warn"
    if not dirty:
        print("%d file%s checked, no findings" % (checked, "" if checked == 1 else "s"))
        return
    print()
    print("%d error%s, %d warning%s in %d of %d file%s"
          % (errors, "" if errors == 1 else "s", warns, "" if warns == 1 else "s",
             dirty, checked, "" if checked == 1 else "s"))


def main(argv: Optional[List[str]] = None) -> int:
    for stream in (sys.stdin, sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass
    args = _build_parser().parse_args(argv)
    if args.list_rules:
        _list_rules()
        return 0
    if not args.paths:
        print("error: give at least one file or folder (or - for standard input)", file=sys.stderr)
        return 2
    try:
        opts = _resolve_options(args)
    except ConfigError as exc:
        print("error: %s" % exc, file=sys.stderr)
        return 2

    files = _collect(args.paths)
    if not files:
        print("error: no .md, .markdown or .txt files found", file=sys.stderr)
        return 2
    results: List[Tuple[str, List[Finding]]] = []
    for path in files:
        try:
            text = _read(path)
        except (OSError, UnicodeDecodeError) as exc:
            print("error: cannot read %s: %s" % (path, exc), file=sys.stderr)
            return 2
        results.append(("<stdin>" if path == "-" else path, lint_text(text, opts)))

    if args.format == "json":
        errors = sum(f.severity == "error" for _, fs in results for f in fs)
        warns = sum(f.severity == "warn" for _, fs in results for f in fs)
        payload = {
            "files": [{"path": p, "findings": [f.as_dict() for f in fs]} for p, fs in results],
            "summary": {"files": len(results), "errors": errors, "warnings": warns},
        }
        print(json.dumps(payload, indent=2, ensure_ascii=False))
    else:
        _print_text(results, len(results))

    has_error = any(f.severity == "error" for _, fs in results for f in fs)
    has_warn = any(f.severity == "warn" for _, fs in results for f in fs)
    return 1 if has_error or (args.strict and has_warn) else 0
