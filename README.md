# house-style-linter

Reidify's copy rules as a linter: 25 deterministic checks for em dashes, stock phrases, unsourced numbers and other things a machine can decide, in Python's standard library only.

![License: MIT](https://img.shields.io/badge/license-MIT-blue)
![Python 3.9+](https://img.shields.io/badge/python-3.9%2B-blue)
![Dependencies: none](https://img.shields.io/badge/dependencies-none-brightgreen)
[![Tests](https://github.com/reidifydesign/house-style-linter/actions/workflows/test.yml/badge.svg)](https://github.com/reidifydesign/house-style-linter/actions/workflows/test.yml)

```text
$ python -m house_style_linter examples/before.md
examples/before.md
  1:3  error  agency-mush            Name what changes for the reader instead.
        > Elevate your brand
  1:27  error  banned-phrase          Cut this stock brand claim. Say what the work does.
        > seamless solutions
  3:1  warn   filler-opener          Start at the claim.
        > In today's
  3:30  error  banned-phrase          Cut this stock brand claim. Say what the work does.
        > we are passionate about
  3:54  error  agency-mush            Name what changes for the reader instead.
        > bespoke digital experiences
  3:82  error  em-dash                Use a period, comma or colon instead.
        > em dash (U+2014)
  3:99  error  curly-quote            Type a straight quote or apostrophe.
        > right single quote or curly apostrophe (U+2019)
  3:111  warn   unsourced-number       Give the number a source, or remove it.
        > 3x
  5:1  error  unsourced-attribution  Cite it or delete the sentence.
        > Studies show
  5:57  error  banned-phrase          Cut this stock brand claim. Say what the work does.
        > take your business to the next level
  7:19  error  exclamation            End the sentence with a period.
        > today!

9 errors, 2 warnings in 1 of 1 file

$ python -m house_style_linter examples/after.md
1 file checked, no findings
```

## Run it

Bash (macOS, Linux, Git Bash):

```bash
git clone https://github.com/reidifydesign/house-style-linter && cd house-style-linter && python -m house_style_linter examples/before.md
```

PowerShell (Windows):

```powershell
git clone https://github.com/reidifydesign/house-style-linter; cd house-style-linter; python -m house_style_linter examples/before.md
```

There is nothing to install. Use `python3` if `python` is not on your path. Point it at a file, a folder of `.md`, `.markdown` and `.txt` files, or `-` to read standard input.

## Why it exists

Reidify is a design studio, and our copy standard is strict. No em dashes, no curly quotes, no stock brand claims, no number without a source. Most of that can be decided by a program, so we wrote it as one and keep the human read for what a program cannot judge.

We built it to check our own copy, and this README passes it. Run over 20 of our published LinkedIn posts from spring and summer 2026, it found 2 em dashes, 11 curly quote characters and 4 filler words and phrases that had already shipped. Four approved pieces of our own site copy produced no findings.

It makes no model calls and needs no network. Checking the 26 fixture files (1,792 words) takes about 40 ms on a Windows laptop with Python 3.12.

## The rules

Errors always fail the run. Warnings are heuristics that need a human decision, and fail the run only with `--strict`. Run `python -m house_style_linter --list-rules` for the same list.

**Mechanics**

| Rule | Level | Flags |
|---|---|---|
| `em-dash` | error | The em dash character (U+2014). |
| `en-dash` | error | The en dash character (U+2013). |
| `curly-quote` | error | Curly quotes and apostrophes. |
| `exclamation` | error | Exclamation marks in prose. |
| `emoji` | warn | Emoji and pictographs. |
| `double-space` | warn | Two spaces after a sentence. |

**Language**

| Rule | Level | Flags |
|---|---|---|
| `banned-phrase` | error | Stock brand claims, AI buzzword phrases, agency filler and stuffed keyword strings, such as `cutting edge`, `best in class` and `harness the power of AI`. |
| `agency-mush` | error | Abstract value language any studio could send, such as `elevate your brand` and `deliver meaningful results`. |
| `filler-word` | warn | Words that stand in for a fact, such as `delve` and `utilize`. |
| `hype-claim` | warn | Superlatives with no proof, such as `groundbreaking` and `second to none`. |
| `abstract-outcome` | warn | An improvement with no size attached, such as `improves efficiency`. A figure in the same sentence clears it. |
| `rationed-word` | warn | A rationed word used more than once in a piece. Defaults: `journey`, `discover`, `invisible`. |
| `filler-opener` | warn | A paragraph that opens with a stock line before the claim. |
| `stock-connective` | warn | A sentence that opens with a connective doing the work of logic, such as `Moreover,`. |
| `summary-closing` | warn | A last paragraph that opens by restating the piece, such as `In conclusion,`. |

**Claims**

| Rule | Level | Flags |
|---|---|---|
| `unsourced-attribution` | error | `Studies show` and similar, with no link, year or named source in the sentence. |
| `income-hook` | error | Income figures used as a hook, such as `six-figure`, or `$5k per month`. |
| `urgency-hook` | error | Manufactured urgency, such as `only 3 spots left`. |
| `unsourced-number` | warn | A percentage or multiplier in a piece that has no source cue at all. Discounts such as `20% off` are ignored. |
| `hedged-choice` | warn | Options presented with no recommendation, such as `it depends on your priorities`. |
| `hedge-density` | warn | Hedging words on nearly every claim: at least 4 of them, and at least 4 per 100 words, in a piece of 40 words or more. |

**Shape**

| Rule | Level | Flags |
|---|---|---|
| `flat-rhythm` | warn | Eight or more sentences of near-equal length. |
| `triple-habit` | warn | Three or more lists of exactly three single words in one piece. |
| `next-step` | warn, opt-in | Client-facing copy whose last two paragraphs hold no request, date or link. |
| `length-limit` | warn, opt-in | A piece over `--max-words`. |

When two language rules hit the same words, the first one in the table above is reported.

## Options

| Flag | Effect |
|---|---|
| `--strict` | Exit 1 on warnings as well as errors. |
| `--require-next-step` | Turn on `next-step` for every file in the run. |
| `--max-words N` | Turn on `length-limit`. |
| `--disable a,b` | Skip rules by id. |
| `--config FILE` | Read a JSON config. `./.house-style.json` is picked up on its own. |
| `--format json` | Machine-readable output. |
| `--include-code` | Check code blocks and inline code too. |

Exit codes: 0 clean, 1 findings at the failing level, 2 usage or config error.

**Scoping the next-step check.** It is off by default because a closing request only belongs in client-facing copy. Turn it on for one file by putting `house-style: client-facing` anywhere in the first few lines, for example inside an HTML comment. Turn a rule off for one file with `house-style: disable=emoji,double-space`.

**Config file.** Every key is optional:

```json
{
  "banned_phrases": ["secret sauce"],
  "rationed_words": ["journey", "bold"],
  "disable": ["emoji"],
  "protected_lines": ["Your tagline, checked nowhere."],
  "require_next_step": false,
  "max_words": 220
}
```

`protected_lines` are masked before any rule runs, for brand lines that break the rules on purpose.

**Markdown.** Front matter, HTML comments, fenced code and inline code are skipped, and so are URLs. That is how this README lists banned phrases without failing itself.

## How the numbers were measured

The 25 rules were checked against 26 synthetic files in `fixtures/`, written for this repo. They hold no real client text and no unpublished drafts. Each file was labeled by hand with the violations a reviewer would flag, in `fixtures/labels.json`. Ten files are clean on purpose and include near-misses such as a percentage with a link beside it, code that quotes a banned word, and a finance sentence that uses `leverage` as a noun.

```bash
python -m house_style_linter.evaluate fixtures/labels.json --show
```

Measured on the fixtures as shipped:

| Set | Files | Findings | Correct | Precision | Recall |
|---|---|---|---|---|---|
| dev (used to tune the rules) | 14 | 39 | 39 | 100.0% | 97.5% |
| holdout (written after the rules were frozen) | 12 | 27 | 26 | 96.3% | 100.0% |
| all | 26 | 66 | 65 | 98.5% | 98.5% |

Every error-level finding on the fixtures was correct: 27 of 27.

The first run on the holdout set scored 92.9%, with 2 wrong findings out of 28. One was a real bug, a source check that ignored a capital letter, and it is fixed. The other is the `leverage` near-miss, which stays.

Read these numbers as a regression floor, not as a general accuracy claim. The same people wrote the rules and the fixtures, the set is small, and real copy will surface cases these files do not.

## Limits

- It decides mechanics and patterns. It cannot tell whether a claim is true, whether a line would work for any other company, or whether copy sounds like a person. Those stay with a human.
- `unsourced-number` only checks that the piece holds some source cue: a link, the word `source`, `according to`, `measured on`, `benchmark` or a numbered reference. It does not check that the source supports that number. One cited figure clears every percentage in the file.
- `filler-word` matches every use of a word, so `leverage` in a finance sentence and `elevated` for a shelf are flagged. It is a warning for that reason. Disable it in a config if your subject needs those words.
- `flat-rhythm`, `hedge-density` and `triple-habit` are statistical. They flag a shape, not a fault, and they need enough text to mean anything.
- A spaced hyphen used as a dash is not caught. Neither is sentence case.
- The rules read English. Sentence splitting is a regex, not a parser, so unusual abbreviations can split early.
- The default `rationed-word` list and the banned phrases are Reidify's own. Replace them through the config for another house style.
- It is not on PyPI. Clone the repo and run the module.

## Tests

The same command runs on Bash and PowerShell:

```bash
python -m unittest discover -s tests -v
```

The suite covers each rule with positive and negative cases, the command line, and the fixture precision floors. It also lints this README with the linter itself.

## License

MIT. See `LICENSE`.

Built by @rishsadh at Reidify (reidify.design)
