"""Regression floors on the labeled fixture set, plus self-checks on the shipped docs."""
import io
import os
import unittest

from house_style_linter import lint_text
from house_style_linter.evaluate import evaluate

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LABELS = os.path.join(ROOT, "fixtures", "labels.json")


class Fixtures(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.res = evaluate(LABELS)

    def test_precision_floor(self):
        self.assertGreaterEqual(self.res["all"]["precision"], 0.95, self.res["all"]["false_positives"])

    def test_holdout_precision_floor(self):
        self.assertGreaterEqual(self.res["holdout"]["precision"], 0.90, self.res["holdout"]["false_positives"])

    def test_error_rules_never_fire_wrongly(self):
        self.assertEqual([], self.res["errors_only"]["false_positives"])

    def test_recall_floor(self):
        self.assertGreaterEqual(self.res["all"]["recall"], 0.95, self.res["all"]["misses"])

    def test_clean_files_have_no_error_findings(self):
        import json

        with io.open(LABELS, encoding="utf-8") as fh:
            labels = json.load(fh)
        for rel, pairs in labels.items():
            if pairs:
                continue
            with io.open(os.path.join(ROOT, "fixtures", rel), encoding="utf-8") as fh:
                errors = [f.rule for f in lint_text(fh.read()) if f.severity == "error"]
            self.assertEqual([], errors, rel)

    def test_every_rule_is_exercised_by_a_label(self):
        import json

        from house_style_linter import RULES

        with io.open(LABELS, encoding="utf-8") as fh:
            labeled = {rule for pairs in json.load(fh).values() for _, rule in pairs}
        untested = sorted(r.id for r in RULES if r.id not in labeled and not r.opt_in)
        self.assertEqual([], untested)


class SelfCheck(unittest.TestCase):
    def test_readme_passes_its_own_linter(self):
        with io.open(os.path.join(ROOT, "README.md"), encoding="utf-8") as fh:
            findings = lint_text(fh.read())
        self.assertEqual([], [(f.line, f.rule, f.snippet) for f in findings])

    def test_readme_has_no_em_dash_or_curly_quote_anywhere(self):
        with io.open(os.path.join(ROOT, "README.md"), encoding="utf-8") as fh:
            text = fh.read()
        for ch in "\u2014\u2013\u2018\u2019\u201c\u201d":
            self.assertNotIn(ch, text)

    def test_readme_sample_output_is_real_output(self):
        import contextlib

        from house_style_linter.cli import main

        with io.open(os.path.join(ROOT, "README.md"), encoding="utf-8") as fh:
            readme = fh.read()
        block = readme.split("```text\n", 1)[1].split("\n```", 1)[0]
        for path in ("examples/before.md", "examples/after.md"):
            self.assertIn("$ python -m house_style_linter " + path, block)
            buf = io.StringIO()
            old = os.getcwd()
            os.chdir(ROOT)
            try:
                with contextlib.redirect_stdout(buf):
                    main([path])
            finally:
                os.chdir(old)
            self.assertIn(buf.getvalue().rstrip("\n"), block, path)


if __name__ == "__main__":
    unittest.main()
