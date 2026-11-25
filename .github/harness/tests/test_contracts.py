import datetime
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import harness_lint
from test_harness import make_repo, run_verify

TODAY = datetime.date(2026, 11, 21)
GOOD = "Does x. Use when a. Not for b."


def raw_agent(desc, extra=""):
    return f"---\ndescription: {desc}\ntools: ['read']\ndisable-model-invocation: true\n{extra}---\nBody\n"


class DescriptionContractTests(unittest.TestCase):
    def errs(self, text):
        with tempfile.TemporaryDirectory() as d:
            make_repo(d, {"a": text})
            return harness_lint.lint(d, TODAY)[0]

    def test_valid_description_passes(self):
        self.assertEqual(self.errs(raw_agent(GOOD)), [])

    def test_use_for_variant_and_do_not_use_for_variant_pass(self):
        self.assertEqual(
            self.errs(raw_agent("Does x. Use for questions. Do not use for edits.")), []
        )

    def test_missing_use_when_fails(self):
        self.assertTrue(
            any("needs both" in e for e in self.errs(raw_agent("Does x. Not for b.")))
        )

    def test_missing_not_for_fails(self):
        self.assertTrue(
            any("needs both" in e for e in self.errs(raw_agent("Does x. Use when a.")))
        )

    def test_use_after_is_not_a_use_when(self):
        self.assertTrue(
            any(
                "needs both" in e
                for e in self.errs(raw_agent("Does x. Use after y. Not for b."))
            )
        )

    def test_length_boundary(self):
        pad = lambda n: GOOD + " " + "x" * (n - len(GOOD) - 1)
        self.assertEqual(self.errs(raw_agent(pad(350))), [])
        self.assertTrue(any("351 chars" in e for e in self.errs(raw_agent(pad(351)))))


class YamlSafetyTests(unittest.TestCase):
    def errs(self, desc, extra=""):
        with tempfile.TemporaryDirectory() as d:
            make_repo(d, {"a": raw_agent(desc, extra)})
            return [e for e in harness_lint.lint(d, TODAY)[0] if "invalid YAML" in e]

    def test_colon_space_in_plain_value_flagged(self):
        self.assertEqual(len(self.errs("Does x: really. Use when a. Not for b.")), 1)

    def test_space_hash_in_plain_value_flagged(self):
        self.assertEqual(len(self.errs("Does x #1. Use when a. Not for b.")), 1)

    def test_quoted_value_is_fine(self):
        self.assertEqual(self.errs('"Does x: really. Use when a. Not for b."'), [])

    def test_colon_without_space_is_fine(self):
        self.assertEqual(self.errs("Follows MISRA C:2012. Use when a. Not for b."), [])

    def test_list_item_values_are_checked_too(self):
        extra = "handoffs:\n  - label: go\n    agent: a\n    prompt: Do this: now\n"
        self.assertEqual(len(self.errs(GOOD, extra)), 1)

    def test_real_agents_have_no_yaml_risks(self):
        repo = Path(__file__).resolve().parents[3]
        self.assertEqual(
            [e for e in harness_lint.lint(repo, TODAY)[0] if "invalid YAML" in e], []
        )


class VerifyLogTests(unittest.TestCase):
    def setUp(self):
        self.t = tempfile.TemporaryDirectory()
        self.root = Path(self.t.name)
        (self.root / ".github/harness").mkdir(parents=True)

    def tearDown(self):
        self.t.cleanup()

    def gates(self, items):
        (self.root / ".github/harness/gates.json").write_text(json.dumps(items))

    def test_full_log_saved_tail_bounded_early_error_surfaced(self):
        self.gates(
            [
                {
                    "name": "build",
                    "command": "echo 'src/a.c:3: error: boom'; seq 1 500; false",
                }
            ]
        )
        _, rep = run_verify(self.root)
        r = rep["results"][0]
        self.assertEqual(len(r["output_tail"].splitlines()), 40)
        self.assertNotIn("boom", r["output_tail"])  # scrolled off the tail...
        self.assertEqual(
            r["error_lines"], ["src/a.c:3: error: boom"]
        )  # ...but still surfaced
        log = (self.root / r["log"]).read_text().splitlines()
        self.assertEqual(len(log), 501)  # full output kept on disk

    def test_error_lines_capped_at_10(self):
        self.gates(
            [
                {
                    "name": "build",
                    "command": "for i in $(seq 1 30); do echo error $i; done; false",
                }
            ]
        )
        _, rep = run_verify(self.root)
        self.assertEqual(len(rep["results"][0]["error_lines"]), 10)

    def test_passing_gate_has_no_tail_or_errors_but_has_log(self):
        self.gates([{"name": "lint", "command": "echo 'error handling ok'"}])
        _, rep = run_verify(self.root)
        r = rep["results"][0]
        self.assertEqual((r["output_tail"], r["error_lines"]), ("", []))
        self.assertTrue((self.root / r["log"]).exists())

    def test_gate_name_cannot_escape_log_directory(self):
        for name in ["../evil name", "/etc/passwd", "a/../../b"]:
            self.gates([{"name": name, "command": "true"}])
            _, rep = run_verify(self.root)
            logpath = (self.root / rep["results"][0]["log"]).resolve()
            self.assertEqual(
                logpath.parent, (self.root / ".github/cache/gate-logs").resolve(), name
            )


if __name__ == "__main__":
    unittest.main()
