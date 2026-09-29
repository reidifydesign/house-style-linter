import unittest

from house_style_linter import Options, lint_text
from house_style_linter.text import Doc


def hits(text, **opts):
    """Rule ids reported for `text`."""
    return [f.rule for f in lint_text(text, Options(**opts))]


class Mechanics(unittest.TestCase):
    def test_em_dash(self):
        self.assertIn("em-dash", hits("One idea \u2014 then another."))
        self.assertNotIn("em-dash", hits("One idea - then another."))

    def test_en_dash(self):
        self.assertIn("en-dash", hits("Weeks 4\u20136 are build weeks."))
        self.assertNotIn("en-dash", hits("Weeks 4 to 6 are build weeks."))

    def test_curly_quotes_each_kind(self):
        for ch in "\u2018\u2019\u201c\u201d":
            self.assertIn("curly-quote", hits("It%sworks." % ch), ch)
        self.assertNotIn("curly-quote", hits("It's \"fine\"."))

    def test_exclamation(self):
        self.assertIn("exclamation", hits("We shipped it!"))
        self.assertNotIn("exclamation", hits("a != b in prose"))
        self.assertNotIn("exclamation", hits("![diagram](x.png)"))

    def test_emoji_but_not_arrows_or_marks(self):
        self.assertIn("emoji", hits("Launch day \U0001F680"))
        self.assertNotIn("emoji", hits("Next \u2192 step \u2122"))

    def test_double_space_after_sentence_only(self):
        self.assertIn("double-space", hits("One.  Two."))
        self.assertNotIn("double-space", hits("One. Two."))
        self.assertNotIn("double-space", hits("Read the config. `./.house-style.json` is picked up."))
        self.assertNotIn("double-space", hits("Read the docs. https://example.com/a/b is the link."))
        self.assertNotIn("double-space", hits("Line ends with two spaces  \nnext line"))


class Language(unittest.TestCase):
    def test_banned_phrase_ignores_hyphen_and_case(self):
        self.assertIn("banned-phrase", hits("A Cutting-Edge studio."))
        self.assertIn("banned-phrase", hits("We are passionate about this."))
        self.assertIn("banned-phrase", hits("We're passionate about this."))
        self.assertNotIn("banned-phrase", hits("The edge of the table is cut."))

    def test_extra_banned_from_options(self):
        self.assertIn("banned-phrase", hits("Our secret sauce.", extra_banned=("secret sauce",)))
        self.assertNotIn("banned-phrase", hits("Our secret sauce."))

    def test_agency_mush(self):
        self.assertIn("agency-mush", hits("We elevate your brand."))
        self.assertIn("agency-mush", hits("It will deliver meaningful results."))
        self.assertIn("agency-mush", hits("Bespoke digital experiences for you."))
        self.assertNotIn("agency-mush", hits("The script transforms the data into rows."))

    def test_filler_word(self):
        self.assertIn("filler-word", hits("Let us delve into it."))
        self.assertIn("filler-word", hits("We utilise a queue."))
        self.assertNotIn("filler-word", hits("We use a queue."))

    def test_hype_claim(self):
        self.assertIn("hype-claim", hits("A groundbreaking tool."))
        self.assertIn("hype-claim", hits("A state-of-the-art tool."))
        self.assertNotIn("hype-claim", hits("A tool that loads in 1.2 seconds."))

    def test_abstract_outcome_needs_no_figure(self):
        self.assertIn("abstract-outcome", hits("This improves efficiency."))
        self.assertIn("abstract-outcome", hits("It enhances the developer experience."))
        self.assertNotIn("abstract-outcome", hits("This improves efficiency by 40 minutes a week."))
        self.assertNotIn("abstract-outcome", hits("Load time improved from 4 seconds to 2."))

    def test_overlapping_language_rules_report_once(self):
        found = [f for f in lint_text("We sell seamless solutions.")]
        self.assertEqual(["banned-phrase"], [f.rule for f in found])

    def test_rationed_word_flags_second_use_only(self):
        self.assertEqual([], [r for r in hits("One journey only.") if r == "rationed-word"])
        found = [f for f in lint_text("The journey starts. The journey ends.") if f.rule == "rationed-word"]
        self.assertEqual(1, len(found))
        self.assertEqual(1, found[0].line)
        self.assertGreater(found[0].col, 20)

    def test_rationed_words_are_configurable(self):
        text = "It is a bold move. Another bold move."
        self.assertNotIn("rationed-word", hits(text))
        self.assertIn("rationed-word", hits(text, rationed_words=("bold",)))

    def test_filler_opener_only_at_paragraph_start(self):
        self.assertIn("filler-opener", hits("In today's world, sites matter."))
        self.assertIn("filler-opener", hits("As businesses increasingly move online, sites matter."))
        self.assertNotIn("filler-opener", hits("Sites matter in today's world."))

    def test_stock_connective(self):
        self.assertIn("stock-connective", hits("We build. Moreover, we test."))
        self.assertNotIn("stock-connective", hits("We build and moreover we test."))

    def test_summary_closing_last_paragraph_only(self):
        self.assertIn("summary-closing", hits("Body text.\n\nIn conclusion, we built it."))
        self.assertNotIn("summary-closing", hits("In conclusion, we built it.\n\nNext step: ship."))
        self.assertNotIn("summary-closing", hits("Body text.\n\nOverall performance improved."))
        self.assertIn("summary-closing", hits("Body text.\n\nOverall, it worked."))


class Claims(unittest.TestCase):
    def test_unsourced_attribution(self):
        self.assertIn("unsourced-attribution", hits("Studies show that speed matters."))
        self.assertIn("unsourced-attribution", hits("According to some experts, it works."))
        self.assertNotIn("unsourced-attribution",
                         hits("Studies show that speed matters (https://example.com/study)."))
        self.assertNotIn("unsourced-attribution", hits("According to Acme Corp, studies show it works."))

    def test_income_hook(self):
        self.assertIn("income-hook", hits("A six-figure practice."))
        self.assertIn("income-hook", hits("We add $5k per month."))
        self.assertNotIn("income-hook", hits("The invoice was $5k."))

    def test_urgency_hook(self):
        self.assertIn("urgency-hook", hits("Act now, only 3 spots left."))
        self.assertNotIn("urgency-hook", hits("Bookings open on 3 November."))

    def test_unsourced_number(self):
        self.assertIn("unsourced-number", hits("It cut costs 40%."))
        self.assertIn("unsourced-number", hits("It is 3x faster."))
        self.assertNotIn("unsourced-number", hits("It cut costs 40% (source: audit sheet)."))
        self.assertNotIn("unsourced-number", hits("According to our logs, it cut costs 40%."))
        self.assertNotIn("unsourced-number", hits("Members get 20% off."))
        self.assertNotIn("unsourced-number", hits("It cut costs 40%, see https://example.com/x."))

    def test_hedged_choice(self):
        self.assertIn("hedged-choice", hits("Both approaches have merit."))
        self.assertIn("hedged-choice", hits("It depends on your priorities."))
        self.assertNotIn("hedged-choice", hits("Pick the retainer."))

    def test_hedge_density(self):
        text = ("It may help. It could work, and it might scale. Often it is fine. "
                "Typically it holds up, and perhaps it lasts. " + "Plain filler words here. " * 6)
        self.assertIn("hedge-density", hits(text))
        self.assertNotIn("hedge-density", hits("It may help."))
        self.assertNotIn("hedge-density", hits("We shipped the fix on Monday. " * 12))


class Shape(unittest.TestCase):
    def test_flat_rhythm(self):
        flat = " ".join("The team ships a small change every single day of the week." for _ in range(9))
        self.assertIn("flat-rhythm", hits(flat))
        varied = ("We ship. Every change goes through review, then staging, then a canary group, and only "
                  "after that does it reach the rest of our customers. Small. Some weeks nothing ships at all, "
                  "because the review found something worth fixing first. That is fine. We would rather wait. "
                  "Speed was never the goal. The goal was a site nobody has to think about on launch day.")
        self.assertNotIn("flat-rhythm", hits(varied))

    def test_flat_rhythm_needs_enough_sentences(self):
        self.assertNotIn("flat-rhythm", hits("The team ships a small change every day. " * 3))

    def test_triple_habit_needs_three(self):
        two = "We plan, build, and test. We write, edit, and cut."
        three = two + " We ask, listen, and answer."
        self.assertNotIn("triple-habit", hits(two))
        self.assertIn("triple-habit", hits(three))

    def test_next_step_is_off_by_default(self):
        self.assertNotIn("next-step", hits("A note about the weather."))

    def test_next_step_opt_in_flag(self):
        self.assertIn("next-step", hits("A note about the weather.", require_next_step=True))
        self.assertNotIn("next-step", hits("A note.\n\nReply by Friday with a yes.", require_next_step=True))

    def test_next_step_scoped_by_directive(self):
        text = "<!-- house-style: client-facing -->\n\nA note about the weather."
        self.assertIn("next-step", hits(text))
        self.assertNotIn("next-step", hits(text + "\n\nBook a call."))

    def test_next_step_reads_last_two_paragraphs(self):
        text = "Body.\n\nCould you send the files by Friday?\n\nThank you for the trust."
        self.assertNotIn("next-step", hits(text, require_next_step=True))

    def test_length_limit_is_opt_in(self):
        text = "word " * 50
        self.assertNotIn("length-limit", hits(text))
        self.assertIn("length-limit", hits(text, max_words=20))
        self.assertNotIn("length-limit", hits(text, max_words=60))


class Masking(unittest.TestCase):
    BAD = "seamless solutions \u2014 wow!"

    def test_fenced_and_inline_code_are_skipped(self):
        self.assertEqual([], hits("```\n%s\n```" % self.BAD))
        self.assertEqual([], hits("~~~\n%s\n~~~" % self.BAD))
        self.assertEqual([], hits("Use `%s` here." % self.BAD))

    def test_include_code_turns_it_back_on(self):
        self.assertIn("em-dash", hits("```\n%s\n```" % self.BAD, include_code=True))

    def test_front_matter_and_comments_are_skipped(self):
        self.assertEqual([], hits("---\ntitle: %s\n---\n\nPlain text." % self.BAD))
        self.assertEqual([], hits("<!-- %s -->\nPlain text." % self.BAD))

    def test_urls_are_not_prose(self):
        self.assertNotIn("exclamation", hits("See https://example.com/a!b for detail."))

    def test_protected_lines_are_masked(self):
        line = "Design is not decoration \u2014 it is direction."
        self.assertIn("em-dash", hits(line))
        self.assertNotIn("em-dash", hits(line, protected_lines=(line,)))

    def test_disable_directive(self):
        text = "<!-- house-style: disable=exclamation,em-dash -->\nWow! And \u2014 also."
        self.assertEqual([], hits(text))

    def test_disable_option(self):
        self.assertEqual([], hits("Wow!", disable=("exclamation",)))


class Positions(unittest.TestCase):
    def test_line_and_column(self):
        f = lint_text("First line.\nSecond \u2014 line.")[0]
        self.assertEqual((2, 8), (f.line, f.col))

    def test_windows_line_endings_do_not_shift_lines(self):
        f = lint_text("One.\r\nTwo.\r\nThree \u2014 four.")[0]
        self.assertEqual(3, f.line)

    def test_masked_views_keep_length(self):
        text = "---\na: b\n---\nText `code` <!-- c -->\n```\nx\n```\nMore https://example.com end."
        d = Doc(text)
        self.assertEqual(len(d.text), len(d.body))
        self.assertEqual(len(d.text), len(d.prose))


if __name__ == "__main__":
    unittest.main()
