"""Run the rules over a piece of copy and return findings."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import List, Optional

from .options import Options
from .rules import RULES
from .text import Doc

# Rules that judge the same words. When two of them hit overlapping text, only the
# first one (in RULES order) is reported.
_LANGUAGE_FAMILY = {"banned-phrase", "agency-mush", "hype-claim", "abstract-outcome", "filler-word"}


@dataclass(frozen=True)
class Finding:
    rule: str
    severity: str
    line: int
    col: int
    message: str
    snippet: str

    def as_dict(self) -> dict:
        return asdict(self)


def lint_text(text: str, options: Optional[Options] = None) -> List[Finding]:
    opts = options or Options()
    doc = Doc(text, include_code=opts.include_code, protected=opts.protected_lines)
    _, file_disabled = doc.directives
    disabled = set(opts.disable) | set(file_disabled)

    raw = []
    for order, rule in enumerate(RULES):
        if rule.id in disabled:
            continue
        for hit in rule.check(doc, opts):
            raw.append((hit.start, order, rule, hit))

    raw.sort(key=lambda t: (t[0], t[1]))
    taken = []  # spans already claimed by a language-family rule
    findings: List[Finding] = []
    for start, _, rule, hit in raw:
        if rule.id in _LANGUAGE_FAMILY:
            if any(s < hit.end and start < e for s, e in taken):
                continue
            taken.append((start, hit.end))
        line, col = doc.line_col(start)
        findings.append(
            Finding(
                rule=rule.id,
                severity=rule.severity,
                line=line,
                col=col,
                message=hit.message or rule.message,
                snippet=(hit.snippet or "")[:80],
            )
        )
    findings.sort(key=lambda f: (f.line, f.col, f.rule))
    return findings
