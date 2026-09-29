"""The rules.

Each rule is a small function that reads a `Doc` and yields hits. Rules are grouped by
what they protect: mechanics (characters), language (words and phrases), claims (what a
sentence asserts), and shape (how a piece is built). Severity is `error` for things that
are always wrong in house copy and `warn` for heuristics that need a human decision.
"""
from __future__ import annotations

import re
import statistics
from dataclasses import dataclass
from typing import Callable, Iterable, List, NamedTuple, Optional, Tuple

from .options import Options
from .text import Doc, count_words


class Hit(NamedTuple):
    start: int
    end: int
    message: Optional[str] = None
    snippet: Optional[str] = None


@dataclass(frozen=True)
class Rule:
    id: str
    severity: str  # "error" or "warn"
    group: str
    summary: str
    message: str
    check: Callable[[Doc, Options], Iterable[Hit]]
    opt_in: bool = False


def _flex(phrase: str) -> str:
    """Let a space in a phrase match spaces or hyphens."""
    return re.sub(r" +", r"[\\s-]+", phrase)


def _alt(phrases: Iterable[str]) -> "re.Pattern[str]":
    return re.compile(r"\b(?:%s)\b" % "|".join(_flex(p) for p in phrases), re.I)


def _all(pattern: "re.Pattern[str]", text: str) -> Iterable[Hit]:
    for m in pattern.finditer(text):
        yield Hit(m.start(), m.end(), None, m.group(0).strip())


# ---------------------------------------------------------------------------
# Mechanics
# ---------------------------------------------------------------------------
_CURLY = {
    "\u2018": "left single quote",
    "\u2019": "right single quote or curly apostrophe",
    "\u201c": "left double quote",
    "\u201d": "right double quote",
}


def check_em_dash(doc: Doc, opts: Options):
    for m in re.finditer("\u2014", doc.body):
        yield Hit(m.start(), m.end(), None, "em dash (U+2014)")


def check_en_dash(doc: Doc, opts: Options):
    for m in re.finditer("\u2013", doc.body):
        yield Hit(m.start(), m.end(), None, "en dash (U+2013)")


def check_curly_quote(doc: Doc, opts: Options):
    for m in re.finditer("[\u2018\u2019\u201c\u201d]", doc.body):
        yield Hit(m.start(), m.end(), None, "%s (U+%04X)" % (_CURLY[m.group(0)], ord(m.group(0))))


_EXCLAIM = re.compile(r"!(?![\[=])")


def check_exclamation(doc: Doc, opts: Options):
    for m in _EXCLAIM.finditer(doc.prose):
        a = doc.prose.rfind(" ", max(0, m.start() - 30), m.start()) + 1
        yield Hit(m.start(), m.end(), None, doc.prose[a:m.end()].strip())


_EMOJI = re.compile("[\U0001F000-\U0001FAFF\u2600-\u27bf\u2b50\u2b55\u2b1b\u2b1c\ufe0f]")


def check_emoji(doc: Doc, opts: Options):
    for m in _EMOJI.finditer(doc.body):
        yield Hit(m.start(), m.end(), None, "emoji (U+%04X)" % ord(m.group(0)))


_DOUBLE_SPACE = re.compile(r"(?<=[.!?]) {2,}(?=\S)")


def check_double_space(doc: Doc, opts: Options):
    for m in _DOUBLE_SPACE.finditer(doc.prose):
        # Masked code and URLs are blanked to spaces, so confirm the spaces are real.
        if doc.text[m.start():m.end()].strip(" ") == "":
            yield Hit(m.start(), m.end(), None, "%d spaces after a sentence" % len(m.group(0)))


# ---------------------------------------------------------------------------
# Language
# ---------------------------------------------------------------------------
# Phrases the studio has decided never to write. Spaces match spaces or hyphens.
_BANNED_GROUPS = (
    (
        "stock brand claim",
        (
            "pushing the boundaries",
            "take (?:it|your brand|your business) to the next level",
            "cutting edge",
            "game chang(?:er|ers|ing)",
            "synerg(?:y|ies)",
            "seamless solutions",
            "best in class",
            "we(?: are|['\u2019]re) passionate about",
        ),
    ),
    (
        "AI buzzword phrase",
        (
            "harness(?:es|ed|ing)? the power of (?:ai|artificial intelligence)",
            "ai driven (?:solutions|design|insights|strategy)",
            "revolutionary ai",
            "next gen(?:eration)? ai",
        ),
    ),
    (
        "agency filler",
        (
            "we design and develop",
            "your one stop shop",
            "brings? your vision to life",
            "results driven",
        ),
    ),
    (
        "stuffed keyword string",
        (
            "ai optimi[sz]ed website design",
            "conversion focused website design",
            "high visibility website design",
        ),
    ),
)
_BANNED = [(label, _alt(phrases)) for label, phrases in _BANNED_GROUPS]


def check_banned_phrase(doc: Doc, opts: Options):
    for label, rx in _BANNED:
        for m in rx.finditer(doc.prose):
            yield Hit(m.start(), m.end(), "Cut this %s. Say what the work does." % label, m.group(0))
    if opts.extra_banned:
        words = [r"[\s-]+".join(re.escape(w) for w in p.split()) for p in opts.extra_banned if p.strip()]
        if words:
            extra = re.compile(r"\b(?:%s)\b" % "|".join(words), re.I)
            for m in extra.finditer(doc.prose):
                yield Hit(m.start(), m.end(), "This phrase is on your banned list.", m.group(0))


_MUSH = (
    re.compile(
        r"\b(?:elevat|transform|unlock|unleash|supercharg|redefin|reimagin|revolutioni[sz]|maximi[sz]|amplif)"
        r"(?:e|es|ed|ing)\s+(?:your|the|their|our)\s+(?:(?:online|digital|brand|business|overall)\s+)*"
        r"(?:brand|business|presence|potential|growth|future|identity|visibility)\b",
        re.I,
    ),
    re.compile(
        r"\b(?:drive|drives|driving|deliver|delivers|delivering|create|creates|creating|ensure|ensures)"
        r"\s+meaningful\s+\w+",
        re.I,
    ),
    re.compile(
        r"\b(?:bespoke|tailored|custom|end-to-end|holistic|innovative|scalable)\s+(?:digital\s+)?"
        r"(?:solutions|experiences)\b",
        re.I,
    ),
)


def check_agency_mush(doc: Doc, opts: Options):
    for rx in _MUSH:
        yield from _all(rx, doc.prose)


_FILLER_WORDS = re.compile(
    r"\b(?:bespoke|delve[sd]?|delving|elevat(?:e|es|ed|ing)|foster(?:s|ed|ing)?|holistic(?:ally)?|"
    r"innovative|leverag(?:e|es|ed|ing)|seamless(?:ly)?|streamlin(?:e|es|ed|ing)|tapestry|"
    r"unleash(?:es|ed|ing)?|utili[sz](?:e|es|ed|ing))\b",
    re.I,
)


def check_filler_word(doc: Doc, opts: Options):
    yield from _all(_FILLER_WORDS, doc.prose)


_HYPE = _alt(
    (
        "groundbreaking",
        "industry leading",
        "life changing",
        "mind blowing",
        "next generation",
        "revolutionary",
        "second to none",
        "state of the art",
        "unbeatable",
        "unmatched",
        "unparalleled",
        "unrivall?ed",
        "world class",
        "guaranteed results",
    )
)


def check_hype_claim(doc: Doc, opts: Options):
    yield from _all(_HYPE, doc.prose)


_ABSTRACT = re.compile(
    r"\b(?:improv|enhanc|boost|optimi[sz]|streamlin|maximi[sz])(?:e|es|ed|ing)\s+"
    r"(?:the\s+|your\s+|our\s+|overall\s+)*(?:\w+\s+)?"
    r"(?:efficiency|productivity|operations|experience|performance|workflows?|engagement|outcomes|processes)\b",
    re.I,
)


def check_abstract_outcome(doc: Doc, opts: Options):
    for m in _ABSTRACT.finditer(doc.prose):
        if re.search(r"\d", doc.prose[m.end(): m.end() + 40].split(".")[0]):
            continue  # a figure follows, so the sentence names the size of the change
        yield Hit(m.start(), m.end(), None, m.group(0))


def _ration_rx(word: str) -> "re.Pattern[str]":
    w = re.escape(word.strip().lower())
    return re.compile(r"\b%s(?:s|es|ed|d|ing|y|ies)?\b" % w, re.I)


def check_rationed_word(doc: Doc, opts: Options):
    for word in opts.rationed_words:
        seen = 0
        for m in _ration_rx(word).finditer(doc.prose):
            seen += 1
            if seen > 1:
                yield Hit(
                    m.start(),
                    m.end(),
                    "'%s' is already used once in this piece. Swap in a plainer word." % word,
                    m.group(0),
                )


_OPENERS = tuple(
    re.compile(p, re.I)
    for p in (
        r"(?:in|as)\s+today(?:'s|\u2019s)\b",
        r"(?:in|as)\s+(?:an?\s+)?(?:\w+\s+)?(?:increasingly|ever[- ]\w+|rapidly\s+\w+|fast[- ]paced)\b",
        r"in\s+(?:the|this)\s+(?:modern|digital|current|fast[- ]paced|ever[- ]\w+)\s+"
        r"(?:age|era|landscape|world|economy|marketplace)\b",
        r"in\s+(?:a|an)\s+(?:world|age|era|time)\s+(?:where|when|of)\b",
        r"(?:have\s+you\s+ever\s+wondered|imagine\s+a\s+world|picture\s+this|welcome\s+to)\b",
        r"it(?:'s|\u2019s|\s+is)\s+no\s+secret\s+that\b",
        r"whether\s+you(?:'re|\u2019re|\s+are)\s+an?\b[^.]{0,80}\bor\s+an?\b",
        r"(?:let's|let\u2019s|let\s+us)\s+(?:dive|take\s+a\s+(?:closer\s+)?look|explore|unpack)\b",
    )
)


def check_filler_opener(doc: Doc, opts: Options):
    for start, block in doc.blocks:
        for rx in _OPENERS:
            m = rx.match(block)
            if m:
                yield Hit(start, start + m.end(), None, m.group(0))
                break


_CONNECTIVE = re.compile(
    r"(?:moreover|furthermore|additionally|in\s+addition|that\s+said|having\s+said\s+that|"
    r"with\s+that\s+in\s+mind|as\s+such|consequently|what(?:'s|\u2019s)\s+more)\s*,",
    re.I,
)


def check_stock_connective(doc: Doc, opts: Options):
    for start, sentence in doc.sentences:
        m = _CONNECTIVE.match(sentence.lstrip("\"'\u201c\u2018("))
        if m:
            yield Hit(start, start + m.end(), None, m.group(0))


_CLOSERS = re.compile(
    r"(?:in\s+(?:conclusion|summary|short|closing)|all\s+in\s+all|overall|ultimately|"
    r"to\s+(?:sum\s+up|summari[sz]e|conclude|wrap\s+(?:things\s+)?up)|the\s+bottom\s+line)\s*[,:]?",
    re.I,
)


def check_summary_closing(doc: Doc, opts: Options):
    if not doc.blocks:
        return
    start, block = doc.blocks[-1]
    m = _CLOSERS.match(block)
    if not m:
        return
    lead = m.group(0).strip().lower()
    # "Overall performance improved" is a sentence. "Overall, ..." is a wrap-up.
    if lead.startswith(("overall", "ultimately")) and not lead.endswith((",", ":")):
        return
    yield Hit(start, start + m.end(), None, m.group(0).strip())


# ---------------------------------------------------------------------------
# Claims
# ---------------------------------------------------------------------------
_ATTRIBUTION = re.compile(
    r"\b(?:(?:studies|research|surveys?|reports?|analysts|experts|scientists|researchers|"
    r"industry\s+(?:experts|reports|leaders|analysts)|"
    r"(?:many|most)\s+(?:experts|people|businesses|users|companies|founders|agencies))\s+"
    r"(?:show|shows|showed|suggest|suggests|suggested|indicate|indicates|indicated|agree|agrees|"
    r"say|says|believe|believes|confirm|confirms|prove|proves|argue|argues)"
    r"|it\s+is\s+(?:widely|generally|commonly|well)\s+(?:known|believed|accepted|understood|recogni[sz]ed)"
    r"|it(?:'s|\u2019s)\s+(?:widely|generally|commonly|well)\s+(?:known|believed|accepted|understood|recogni[sz]ed)"
    r"|according\s+to\s+(?:some|many|several|most)\s+(?:experts|studies|sources|reports|analysts))\b",
    re.I,
)
_CITED = re.compile(r"(?i:https?://|\[\d+\]|\(\d{4}\)|\bsource:)|\b[Aa]ccording\s+to\s+[A-Z]")


def check_unsourced_attribution(doc: Doc, opts: Options):
    for m in _ATTRIBUTION.finditer(doc.prose):
        s_start, _ = doc.sentence_at(m.start())
        # look at the original body of the sentence, which still holds any link
        stop = doc.body.find(".", m.end())
        stop = len(doc.body) if stop == -1 else stop + 1
        if _CITED.search(doc.body[s_start:stop]):
            continue
        yield Hit(m.start(), m.end(), None, m.group(0))


_INCOME = re.compile(
    r"\b(?:six|seven|eight|[678])[- ]figures?\b"
    r"|\$\s?\d[\d,.]*\s?(?:k|m|million|thousand)\b[^.\n]{0,50}\b(?:in|per|a|each|every)\s+(?:\d+\s+)?"
    r"(?:days?|weeks?|months?|hours?)\b"
    r"|\b(?:passive|side)\s+income\b|\bmake\s+money\s+(?:online|while\s+you\s+sleep)\b",
    re.I,
)


def check_income_hook(doc: Doc, opts: Options):
    yield from _all(_INCOME, doc.prose)


_URGENCY = _alt(
    (
        "limited spots",
        "only \\d+ (?:spots?|places?|seats?|slots?) (?:left|remaining|available)",
        "act now",
        "last chance",
        "don't miss out",
        "don\u2019t miss out",
        "before it(?:'s|\u2019s) too late",
        "spots (?:are )?filling up",
        "offer ends (?:soon|today|tonight)",
        "hurry",
    )
)


def check_urgency_hook(doc: Doc, opts: Options):
    yield from _all(_URGENCY, doc.prose)


_NUMBER_CLAIM = re.compile(
    r"\b\d+(?:[.,]\d+)?\s?(?:%|percent\b)(?!\s+(?:off|discount|deposit|vat|tax|interest|apr)\b)|\b\d+(?:\.\d+)?x\b"
    r"|\b\d+(?:\.\d+)?\s+times\s+(?:more|faster|as|higher|better|greater|less|fewer)\b",
    re.I,
)
_SOURCE_CUE = re.compile(
    r"(?i:https?://|\[\d+\]|\bsources?\b|\baccording\s+to\b|\bmeasured\s+(?:on|from|across|over|by)\b|"
    r"\bbenchmarks?\b)|"
    r"\b(?:via|per)\s+[A-Z]",
)


def check_unsourced_number(doc: Doc, opts: Options):
    if _SOURCE_CUE.search(doc.body):
        return
    for m in _NUMBER_CLAIM.finditer(doc.prose):
        yield Hit(m.start(), m.end(), None, m.group(0))


_HEDGES = re.compile(
    r"\b(?:can\s+help|may|might|could|often|typically|generally|tends?\s+to|arguably|perhaps|possibly|"
    r"potentially|somewhat|in\s+some\s+cases|to\s+some\s+extent|in\s+many\s+cases|usually|sometimes)\b",
    re.I,
)
_CHOICE_HEDGES = tuple(
    re.compile(p, re.I)
    for p in (
        r"\bboth\s+(?:approaches|options|paths|routes|choices|ways|have|are)\b[^.]{0,40}"
        r"\b(?:merit|valid|reasonable|fine|good)",
        r"\bit\s+depends\s+on\s+(?:your|the|what)\s+(?:priorities|needs|goals|situation|preferences|budget)",
        r"\bpros\s+and\s+cons\b",
        r"\byou\s+(?:could|can|might)\s+(?:go|choose|pick|opt)\s+(?:with\s+)?either\b",
        r"\beither\s+(?:approach|option|way|path|route)\s+(?:works|is\s+fine|could\s+work|would\s+work|is\s+reasonable)",
    )
)


def check_hedged_choice(doc: Doc, opts: Options):
    for rx in _CHOICE_HEDGES:
        yield from _all(rx, doc.prose)


def check_hedge_density(doc: Doc, opts: Options):
    if doc.word_count < 40:
        return
    hits = list(_HEDGES.finditer(doc.prose))
    if len(hits) >= 4 and len(hits) / doc.word_count >= 0.04:
        first = hits[0]
        yield Hit(
            first.start(),
            first.end(),
            "%d hedging words in %d words. Keep doubt where it is real and state the rest flatly."
            % (len(hits), doc.word_count),
            "%s ..." % first.group(0),
        )


# ---------------------------------------------------------------------------
# Shape
# ---------------------------------------------------------------------------
def check_flat_rhythm(doc: Doc, opts: Options):
    sentences = [(o, s) for o, s in doc.sentences if count_words(s) >= 3]
    if len(sentences) < 8:
        return
    lengths = [count_words(s) for _, s in sentences]
    mean = statistics.mean(lengths)
    cv = statistics.pstdev(lengths) / mean if mean else 1.0
    if mean >= 8 and cv < 0.25:
        o, s = sentences[0]
        yield Hit(
            o,
            o + len(s),
            "%d sentences of near-equal length (average %.0f words, spread %.2f). Let the important one run long."
            % (len(sentences), mean, cv),
            s[:40],
        )


_TRIPLE = re.compile(r"\b[A-Za-z][A-Za-z-]*, [A-Za-z][A-Za-z-]*,? (?:and|or) [A-Za-z][A-Za-z-]*\b")


def check_triple_habit(doc: Doc, opts: Options):
    found = list(_TRIPLE.finditer(doc.prose))
    if len(found) >= 3:
        m = found[2]
        yield Hit(
            m.start(),
            m.end(),
            "%d three-item lists in one piece. Use two when you have two." % len(found),
            m.group(0),
        )


_NEXT_STEP = re.compile(
    r"\b(?:reply|respond|reach\s+out|get\s+in\s+touch|contact|book|schedule|call|email|message|dm|"
    r"comment|sign\s+up|join|send|tell\s+me|let\s+me\s+know|request|download|try|visit|see|start|"
    r"check|review|approve|confirm|share|pick|choose|open|read|talk|write|ask|apply|register|"
    r"subscribe|follow|save|order|buy)\b|\?|\u2192|->|https?://|\bby\s+(?:mon|tue|wed|thu|fri|sat|sun|\d)",
    re.I,
)


def check_next_step(doc: Doc, opts: Options):
    client_facing, _ = doc.directives
    if not (opts.require_next_step or client_facing):
        return
    if not doc.blocks:
        return
    # A thank-you or sign-off line often follows the ask, so read the last two blocks.
    tail = doc.blocks[-2:]
    window = " ".join(doc.body[start:start + len(block)] for start, block in tail)
    if not _NEXT_STEP.search(window):
        start, block = doc.blocks[-1]
        yield Hit(start, start + len(block), None, block[:50])


def check_length_limit(doc: Doc, opts: Options):
    if opts.max_words and doc.word_count > opts.max_words:
        yield Hit(0, 0, "%d words against a limit of %d. Cut what does not change the reader's decision."
                  % (doc.word_count, opts.max_words), "%d words" % doc.word_count)


RULES: Tuple[Rule, ...] = (
    # mechanics
    Rule("em-dash", "error", "mechanics", "No em dashes.",
         "Use a period, comma or colon instead.", check_em_dash),
    Rule("en-dash", "error", "mechanics", "No en dashes.",
         "Write ranges with 'to' and pauses with a comma.", check_en_dash),
    Rule("curly-quote", "error", "mechanics", "Straight quotes and apostrophes only.",
         "Type a straight quote or apostrophe.", check_curly_quote),
    Rule("exclamation", "error", "mechanics", "No exclamation marks.",
         "End the sentence with a period.", check_exclamation),
    Rule("emoji", "warn", "mechanics", "No emoji in client-facing copy.",
         "Remove it unless the owner asked for it.", check_emoji),
    Rule("double-space", "warn", "mechanics", "One space after a period.",
         "Use a single space.", check_double_space),
    # language
    Rule("banned-phrase", "error", "language", "Phrases the studio never writes.",
         "Cut this phrase.", check_banned_phrase),
    Rule("agency-mush", "error", "language", "Abstract value language any studio could send.",
         "Name what changes for the reader instead.", check_agency_mush),
    Rule("filler-word", "warn", "language", "Words that stand in for a fact.",
         "Use the plain verb or name the thing.", check_filler_word),
    Rule("hype-claim", "warn", "language", "Superlatives without proof.",
         "Give the result. The reader can size it up.", check_hype_claim),
    Rule("abstract-outcome", "warn", "language", "An improvement with no size attached.",
         "Say what changed and by how much, or cut it.", check_abstract_outcome),
    Rule("rationed-word", "warn", "language", "Words allowed once per piece.",
         "Swap in a plainer word.", check_rationed_word),
    Rule("filler-opener", "warn", "language", "Stock openers that delay the point.",
         "Start at the claim.", check_filler_opener),
    Rule("stock-connective", "warn", "language", "Connectives doing the work of logic.",
         "If the link is real the sentences show it. Cut the connective.", check_stock_connective),
    Rule("summary-closing", "warn", "language", "A last paragraph that repeats the body.",
         "Stop after the last real point.", check_summary_closing),
    # claims
    Rule("unsourced-attribution", "error", "claims", "Attribution with no named source.",
         "Cite it or delete the sentence.", check_unsourced_attribution),
    Rule("income-hook", "error", "claims", "Income figures used as a hook.",
         "Describe what actually changed for a real person or business.", check_income_hook),
    Rule("urgency-hook", "error", "claims", "Manufactured urgency.",
         "State a real deadline or say nothing.", check_urgency_hook),
    Rule("unsourced-number", "warn", "claims", "A percentage or multiplier with no source in the piece.",
         "Give the number a source, or remove it.", check_unsourced_number),
    Rule("hedged-choice", "warn", "claims", "Options presented with no recommendation.",
         "Pick one and say why.", check_hedged_choice),
    Rule("hedge-density", "warn", "claims", "Hedging on nearly every claim.",
         "Keep doubt where it is real and state the rest flatly.", check_hedge_density),
    # shape
    Rule("flat-rhythm", "warn", "shape", "Sentences of near-equal length.",
         "Vary the length on purpose.", check_flat_rhythm),
    Rule("triple-habit", "warn", "shape", "Three-item lists used by reflex.",
         "Use two when you have two.", check_triple_habit),
    Rule("next-step", "warn", "shape", "Client-facing copy needs a next step (opt in).",
         "End with a request, a date or a link.", check_next_step, opt_in=True),
    Rule("length-limit", "warn", "shape", "Piece is over the word limit (opt in with --max-words).",
         "Cut what does not change the reader's decision.", check_length_limit, opt_in=True),
)

RULES_BY_ID = {r.id: r for r in RULES}
