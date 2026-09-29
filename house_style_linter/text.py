"""Turn a piece of copy into the views the rules read: masked prose, blocks, sentences.

Every view keeps the same length as the original text, so an offset found in a view is
also the offset in the file. Masked characters become spaces and newlines stay.
"""
from __future__ import annotations

import bisect
import re
from functools import cached_property
from typing import List, Tuple

_INLINE_CODE = re.compile(r"`[^`\n]*`")
_HTML_COMMENT = re.compile(r"<!--.*?-->", re.S)
_URL = re.compile(r"https?://[^\s<>)\]]+")
_LIST_MARK = re.compile(r"^\s*(?:[-*+]|\d{1,3}[.)])\s+")
_WORD = re.compile(r"[A-Za-z0-9][A-Za-z0-9'\u2019-]*")
_ABBREV = {"e.g", "i.e", "vs", "etc", "mr", "mrs", "ms", "dr", "st", "no", "approx", "inc", "ltd"}
_DIRECTIVE = re.compile(r"house-style:\s*([A-Za-z0-9=,_ \-]+)", re.I)
_RULE_LINE = re.compile(r"[-*_=\s]{3,}")


def blank(s: str) -> str:
    """Replace every character except newlines with a space."""
    return re.sub(r"[^\n]", " ", s)


def _blank_matches(text: str, pattern: "re.Pattern[str]") -> str:
    return pattern.sub(lambda m: blank(m.group(0)), text)


def count_words(s: str) -> int:
    return len(_WORD.findall(s))


class Doc:
    """One piece of copy plus the masked views the rules need."""

    def __init__(self, text: str, include_code: bool = False, protected: Tuple[str, ...] = ()):
        self.text = text.replace("\r\n", "\n").replace("\r", "\n")
        self.include_code = include_code
        self._protected = tuple(p for p in protected if p)

    # -- directives ---------------------------------------------------------
    @cached_property
    def directives(self) -> Tuple[bool, Tuple[str, ...]]:
        """(client_facing, disabled_rules) read from a `house-style:` line near the top."""
        client_facing = False
        disabled: List[str] = []
        for m in _DIRECTIVE.finditer(self.text[:600]):
            for token in m.group(1).split():
                if token.lower() == "client-facing":
                    client_facing = True
                elif token.lower().startswith("disable="):
                    disabled += [r for r in token.split("=", 1)[1].split(",") if r]
        return client_facing, tuple(disabled)

    # -- masked views -------------------------------------------------------
    @cached_property
    def body(self) -> str:
        """Text with front matter, code, comments and protected lines blanked."""
        t = self.text
        if t.startswith("---\n"):
            end = t.find("\n---", 4)
            if end != -1:
                stop = end + 4
                t = blank(t[:stop]) + t[stop:]
        t = _blank_matches(t, _HTML_COMMENT)
        if not self.include_code:
            t = self._blank_fences(t)
            t = _blank_matches(t, _INLINE_CODE)
        for p in self._protected:
            t = re.sub(re.escape(p), lambda m: blank(m.group(0)), t, flags=re.I)
        return t

    @staticmethod
    def _blank_fences(t: str) -> str:
        out: List[str] = []
        fence = None
        for line in t.split("\n"):
            stripped = line.lstrip()
            marker = stripped[:3] if stripped[:3] in ("```", "~~~") else None
            if fence is None and marker and len(line) - len(stripped) <= 3:
                fence = marker
                out.append(blank(line))
            elif fence is not None:
                if marker == fence:
                    fence = None
                out.append(blank(line))
            else:
                out.append(line)
        return "\n".join(out)

    @cached_property
    def prose(self) -> str:
        """`body` with URLs blanked as well."""
        return _blank_matches(self.body, _URL)

    # -- structure ----------------------------------------------------------
    @cached_property
    def blocks(self) -> List[Tuple[int, str]]:
        """Prose blocks as (offset, text): paragraphs and list items.

        Headings, table rows and rules are left out. Soft-wrapped lines stay in one
        block, with newlines turned into spaces so lengths do not change.
        """
        prose = self.prose
        spans: List[Tuple[int, int]] = []
        cur_start = None
        cur_end = 0
        pos = 0

        def flush():
            nonlocal cur_start
            if cur_start is not None:
                spans.append((cur_start, cur_end))
            cur_start = None

        for line in prose.split("\n"):
            start = pos
            pos += len(line) + 1
            s = line.strip()
            if not s:
                flush()
                continue
            if s.startswith(("#", "|")) or _RULE_LINE.fullmatch(s):
                flush()
                continue
            m = _LIST_MARK.match(line)
            if m:
                flush()
                cur_start = start + m.end()
            elif cur_start is None:
                cur_start = start + (len(line) - len(line.lstrip()))
            cur_end = start + len(line.rstrip())
        flush()
        return [(a, prose[a:b].replace("\n", " ")) for a, b in spans]

    @cached_property
    def sentences(self) -> List[Tuple[int, str]]:
        """Sentences as (offset, text) taken from the prose blocks."""
        out: List[Tuple[int, str]] = []
        for offset, block in self.blocks:
            start = 0
            for m in re.finditer(r"[.!?]+[\"')\]\u201d\u2019]*(?=\s|$)", block):
                end = m.end()
                token = block[start:end].rstrip(".!?\"')]\u201d\u2019 ").split(" ")[-1].lower()
                if token in _ABBREV:
                    continue
                self._add(out, offset, block, start, end)
                start = end
            self._add(out, offset, block, start, len(block))
        return out

    @staticmethod
    def _add(out, offset, block, start, end):
        chunk = block[start:end]
        lead = len(chunk) - len(chunk.lstrip())
        chunk = chunk.strip()
        if chunk:
            out.append((offset + start + lead, chunk))

    @cached_property
    def word_count(self) -> int:
        return count_words(self.prose)

    # -- positions ----------------------------------------------------------
    @cached_property
    def _line_starts(self) -> List[int]:
        starts = [0]
        for m in re.finditer(r"\n", self.text):
            starts.append(m.end())
        return starts

    def line_col(self, offset: int) -> Tuple[int, int]:
        i = bisect.bisect_right(self._line_starts, offset) - 1
        return i + 1, offset - self._line_starts[i] + 1

    def sentence_at(self, offset: int) -> Tuple[int, str]:
        for start, s in self.sentences:
            if start <= offset < start + len(s):
                return start, s
        return offset, ""
