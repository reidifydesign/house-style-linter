import contextlib
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest

from house_style_linter import RULES
from house_style_linter.cli import main

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def run(argv, stdin_text=None):
    """Call main() and return (exit_code, stdout, stderr)."""
    out, err = io.StringIO(), io.StringIO()
    old_stdin = sys.stdin
    if stdin_text is not None:
        sys.stdin = io.StringIO(stdin_text)
    try:
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = main(argv)
    finally:
        sys.stdin = old_stdin
    return code, out.getvalue(), err.getvalue()


class Cli(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)

    def write(self, name, text):
        path = os.path.join(self.tmp.name, name)
        with open(path, "w", encoding="utf-8", newline="") as fh:
            fh.write(text)
        return path

    def test_clean_file_exits_zero(self):
        p = self.write("ok.txt", "We shipped the fix on Monday.\n")
        code, out, _ = run([p])
        self.assertEqual(0, code)
        self.assertIn("1 file checked, no findings", out)

    def test_error_exits_one(self):
        p = self.write("bad.txt", "We shipped it!\n")
        code, out, _ = run([p])
        self.assertEqual(1, code)
        self.assertIn("exclamation", out)
        self.assertRegex(out, r"  1:[0-9]+  error")

    def test_warning_only_exits_zero_unless_strict(self):
        p = self.write("warn.txt", "Members get a groundbreaking tool.\n")
        self.assertEqual(0, run([p])[0])
        self.assertEqual(1, run(["--strict", p])[0])

    def test_json_output(self):
        p = self.write("bad.txt", "Ship it now!\n")
        code, out, _ = run(["--format", "json", p])
        data = json.loads(out)
        self.assertEqual(1, code)
        self.assertEqual(1, data["summary"]["errors"])
        self.assertEqual("exclamation", data["files"][0]["findings"][0]["rule"])

    def test_directory_is_walked_for_text_files_only(self):
        self.write("a.md", "Fine.\n")
        self.write("b.txt", "Wow!\n")
        self.write("c.py", "print('Wow!')\n")
        code, out, _ = run([self.tmp.name])
        self.assertEqual(1, code)
        self.assertIn("in 1 of 2 files", out)

    def test_stdin_is_read_as_utf8_text(self):
        code, out, _ = run(["-"], stdin_text="One \u2014 two.\n")
        self.assertEqual(1, code)
        self.assertIn("<stdin>", out)
        self.assertIn("em-dash", out)

    def test_next_step_flag_and_directive(self):
        p = self.write("note.txt", "A note about the weather.\n")
        self.assertEqual(0, run([p, "--strict"])[0])
        self.assertEqual(1, run([p, "--strict", "--require-next-step"])[0])
        q = self.write("client.txt", "house-style: client-facing\n\nA note about the weather.\n")
        self.assertEqual(1, run([q, "--strict"])[0])

    def test_max_words_flag(self):
        p = self.write("long.txt", "word " * 30 + "\n")
        self.assertEqual(1, run([p, "--strict", "--max-words", "10"])[0])

    def test_disable_flag_and_unknown_rule(self):
        p = self.write("bad.txt", "Wow!\n")
        self.assertEqual(0, run([p, "--disable", "exclamation"])[0])
        code, _, err = run([p, "--disable", "not-a-rule"])
        self.assertEqual(2, code)
        self.assertIn("unknown rule id", err)

    def test_config_file(self):
        cfg = self.write("cfg.json", json.dumps({"banned_phrases": ["secret sauce"], "disable": ["exclamation"]}))
        p = self.write("bad.txt", "Our secret sauce works!\n")
        code, out, _ = run([p, "--config", cfg])
        self.assertEqual(1, code)
        self.assertIn("banned-phrase", out)
        self.assertNotIn("exclamation", out)

    def test_bad_config_exits_two(self):
        cfg = self.write("cfg.json", json.dumps({"nope": 1}))
        p = self.write("ok.txt", "Fine.\n")
        code, _, err = run([p, "--config", cfg])
        self.assertEqual(2, code)
        self.assertIn("unknown keys", err)

    def test_usage_errors_exit_two(self):
        self.assertEqual(2, run([])[0])
        self.assertEqual(2, run([os.path.join(self.tmp.name, "missing.txt")])[0])

    def test_include_code_flag(self):
        p = self.write("code.md", "```\nWow!\n```\n")
        self.assertEqual(0, run([p])[0])
        self.assertEqual(1, run([p, "--include-code"])[0])

    def test_list_rules_names_every_rule(self):
        code, out, _ = run(["--list-rules"])
        self.assertEqual(0, code)
        for rule in RULES:
            self.assertIn(rule.id, out)

    def test_module_entry_point_in_a_fresh_process(self):
        p = self.write("bad.txt", "One \u2014 two.\n")
        proc = subprocess.run([sys.executable, "-m", "house_style_linter", p],
                              cwd=ROOT, capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(1, proc.returncode, proc.stderr)
        self.assertIn("em-dash", proc.stdout)


if __name__ == "__main__":
    unittest.main()
