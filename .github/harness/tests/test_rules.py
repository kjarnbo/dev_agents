import datetime
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
S = REPO / ".github" / "harness" / "scripts"
sys.path.insert(0, str(S))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import harness_lint
import rule_signals
import scope_check
from test_harness import agent, git, make_repo

TODAY = datetime.date(2026, 11, 21)


class ClassifyTests(unittest.TestCase):
    def label(self, text):
        return rule_signals.classify(text)["label"]

    def test_clear_rules(self):
        for t in [
            "From now on always use snake_case for function names.",
            "Never use malloc in this project.",
            "We prefer early returns over nested ifs.",
        ]:
            self.assertEqual(self.label(t), "rule", t)

    def test_single_signal_is_likely_rule(self):
        self.assertEqual(
            self.label("Always run the unit tests before committing."), "likely_rule"
        )

    def test_ordinary_task_is_none(self):
        for t in [
            "Add a message handler for ID 0x123.",
            "Fix the null check in parse_frame.",
            "ok thanks",
        ]:
            self.assertEqual(self.label(t), "none", t)

    def test_one_off_scoping_beats_rule_words(self):
        self.assertEqual(
            self.label("Fix the typo in the README just for this PR."), "one_off"
        )
        self.assertEqual(
            self.label("Always run lint, but just for this PR."), "one_off"
        )

    def test_question_is_not_a_rule(self):
        for q in [
            "Do we always use snake_case here?",
            "Should we never use malloc in this project?",
        ]:
            self.assertEqual(self.label(q), "none", q)
        self.assertEqual(
            self.label("We always use snake_case here."), "rule"
        )  # same words as a statement

    def test_rule_found_inside_multi_sentence_prompt(self):
        r = rule_signals.classify(
            "Add the handler. From now on never skip the unit tests. Thanks."
        )
        self.assertEqual(r["label"], "rule")
        self.assertIn("never skip the unit tests", r["statement"])

    def test_oversized_sentences_ignored(self):
        self.assertEqual(self.label("always " * 80), "none")

    def test_regressions_from_probe(self):
        logged = [
            "Use 4-space indentation everywhere in this repo.",
            "Please don't touch the generated files, ever.",
            "Stop adding docstrings to every function, it's noisy.",
            "Prefer composition over inheritance.",
            "Our convention is MISRA C:2012 for all modules.",
            "Tests must pass before merging, no exceptions.",
        ]
        for t in logged:
            self.assertIn(self.label(t), ("rule", "likely_rule"), t)
        for t in [
            "Make the timeout 30 seconds.",
            "Rename foo to bar in this file.",
            "We should add a retry handler for the CAN driver.",
        ]:
            self.assertNotIn(self.label(t), ("rule", "likely_rule"), t)

    def test_known_limit_non_english_is_missed(self):
        # Documented limitation: English-only heuristic. If this starts failing, update DECISIONS.md.
        self.assertEqual(
            self.label("Utilisez toujours des noms en snake_case."), "none"
        )

    def test_empty_and_none_input(self):
        self.assertEqual(self.label(""), "none")
        self.assertEqual(rule_signals.classify(None)["label"], "none")


def hook(root, payload, raw=None):
    data = raw if raw is not None else json.dumps(payload)
    return subprocess.run(
        [sys.executable, str(S / "rule_signals.py"), "--hook"],
        input=data,
        capture_output=True,
        text=True,
        cwd=root,
    )


def cli(root, *args):
    r = subprocess.run(
        [sys.executable, str(S / "rule_signals.py"), *args, "--root", str(root)],
        capture_output=True,
        text=True,
    )
    return json.loads(r.stdout) if r.stdout.strip().startswith(("[", "{")) else r.stdout


class HookTests(unittest.TestCase):
    def setUp(self):
        self.t = tempfile.TemporaryDirectory()
        self.root = Path(self.t.name)
        (self.root / ".github").mkdir()
        self.log = self.root / ".github/cache/rule-candidates.jsonl"

    def tearDown(self):
        self.t.cleanup()

    def lines(self):
        return self.log.read_text().splitlines() if self.log.exists() else []

    def test_rule_prompt_is_logged_silently(self):
        r = hook(
            self.root,
            {"prompt": "From now on always use snake_case.", "cwd": str(self.root)},
        )
        self.assertEqual((r.returncode, r.stdout), (0, ""))
        self.assertEqual(len(self.lines()), 1)
        self.assertEqual(json.loads(self.lines()[0])["label"], "rule")

    def test_ordinary_and_one_off_prompts_not_logged(self):
        hook(
            self.root, {"prompt": "Add a handler for ID 0x123.", "cwd": str(self.root)}
        )
        hook(
            self.root,
            {"prompt": "Always run lint, but just for this PR.", "cwd": str(self.root)},
        )
        self.assertEqual(self.lines(), [])

    def test_duplicate_events_log_once(self):
        p = {"prompt": "Never use malloc in this project.", "cwd": str(self.root)}
        hook(self.root, p)
        hook(self.root, p)
        self.assertEqual(len(self.lines()), 1)

    def test_whole_prompt_is_not_stored(self):
        hook(
            self.root,
            {
                "prompt": "Secret token abc123 is in the config. Never use malloc in this project.",
                "cwd": str(self.root),
            },
        )
        self.assertNotIn("abc123", self.log.read_text())

    def test_garbage_input_never_fails(self):
        for raw in ["", "not json", "[]", '{"prompt": 5}']:
            r = hook(self.root, None, raw=raw)
            self.assertEqual((r.returncode, r.stdout), (0, ""), raw)

    def test_list_and_mark_suppress_future_logging(self):
        hook(
            self.root,
            {"prompt": "Never use malloc in this project.", "cwd": str(self.root)},
        )
        entries = cli(self.root, "list")
        self.assertEqual(len(entries), 1)
        cli(self.root, "mark", entries[0]["id"])
        self.assertEqual(cli(self.root, "list"), [])
        hook(
            self.root,
            {"prompt": "Never use malloc in this project.", "cwd": str(self.root)},
        )
        self.assertEqual(len(self.lines()), 1)  # not logged again

    def test_scan_cli_returns_classification(self):
        out = cli(self.root, "scan", "Never use malloc in this project.")
        self.assertEqual(out["label"], "rule")


def proposal(**over):
    meta = {
        "status": "pending",
        "created": "2026-11-21",
        "destination": "project-rule",
        "statement": "s",
        "why": "w",
        "review_by": "2027-02-21",
        "reason": "",
    }
    meta.update(over)
    lines = [f"{k}: {v}" for k, v in meta.items() if v != "__omit__"]
    return "---\n" + "\n".join(lines) + "\n---\nbody\n"


class ProposalLintTests(unittest.TestCase):
    def setUp(self):
        self.t = tempfile.TemporaryDirectory()
        self.root = Path(self.t.name)
        make_repo(self.root, {"a": agent()})
        (self.root / ".github/harness/proposals").mkdir()

    def tearDown(self):
        self.t.cleanup()

    def errs(self, text, name="p.md"):
        (self.root / ".github/harness/proposals" / name).write_text(text)
        return harness_lint.lint(self.root, TODAY)[0]

    def test_valid_proposal_passes(self):
        self.assertEqual(self.errs(proposal()), [])

    def test_missing_field_fails(self):
        self.assertTrue(
            any("missing frontmatter" in e for e in self.errs(proposal(why="__omit__")))
        )

    def test_bad_status_and_destination_fail(self):
        self.assertTrue(
            any("status 'maybe'" in e for e in self.errs(proposal(status="maybe")))
        )
        self.assertTrue(
            any("destination 'x'" in e for e in self.errs(proposal(destination="x")))
        )

    def test_rejected_needs_reason(self):
        self.assertTrue(
            any("reason" in e for e in self.errs(proposal(status="rejected")))
        )
        self.assertEqual(
            self.errs(
                proposal(status="rejected", reason="duplicate of AGENTS.md rule 3")
            ),
            [],
        )

    def test_pending_age_boundary_30_ok_31_fails(self):
        ok = (TODAY - datetime.timedelta(days=30)).isoformat()
        old = (TODAY - datetime.timedelta(days=31)).isoformat()
        self.assertEqual(self.errs(proposal(created=ok)), [])
        self.assertTrue(
            any("pending for 31 days" in e for e in self.errs(proposal(created=old)))
        )

    def test_old_applied_proposal_is_fine_until_review_by_passes(self):
        old = (TODAY - datetime.timedelta(days=200)).isoformat()
        self.assertEqual(self.errs(proposal(status="applied", created=old)), [])
        self.assertTrue(
            any(
                "review-by" in e
                for e in self.errs(proposal(status="applied", review_by="2026-11-20"))
            )
        )

    def test_bad_dates_fail(self):
        self.assertTrue(
            any("YYYY-MM-DD" in e for e in self.errs(proposal(created="soon")))
        )


class RoleAndHookLintTests(unittest.TestCase):
    def setUp(self):
        self.t = tempfile.TemporaryDirectory()
        self.root = Path(self.t.name)

    def tearDown(self):
        self.t.cleanup()

    def errs(self):
        return harness_lint.lint(self.root, TODAY)[0]

    def test_ask_and_explorer_may_not_execute(self):
        make_repo(
            self.root,
            {
                "ask": agent(tools="['read','execute']"),
                "explorer": agent(tools="['read','execute']"),
            },
        )
        self.assertEqual(
            len([e for e in self.errs() if "must not run commands" in e]), 2
        )

    def test_ask_may_not_edit(self):
        make_repo(self.root, {"ask": agent(tools="['read','edit']")})
        self.assertTrue(any("read-only role 'ask'" in e for e in self.errs()))

    def test_reviewer_may_execute(self):
        make_repo(self.root, {"reviewer": agent(tools="['read','execute']")})
        self.assertEqual(self.errs(), [])

    def test_read_only_ask_passes(self):
        make_repo(self.root, {"ask": agent(tools="['search','read','agent']")})
        self.assertEqual(self.errs(), [])

    def _hook(self, cfg):
        self.root = Path(tempfile.mkdtemp())
        make_repo(self.root, {"a": agent()})
        (self.root / ".github/hooks").mkdir()
        (self.root / ".github/hooks/h.json").write_text(
            cfg if isinstance(cfg, str) else json.dumps(cfg)
        )
        return self.errs()

    def _cfg(self, script, version=1):
        return {
            "version": version,
            "hooks": {
                "UserPromptSubmit": [
                    {"type": "command", "bash": f"python3 {script} --hook"}
                ]
            },
        }

    def test_hook_with_existing_script_passes(self):
        make_repo(self.root, {"a": agent()})
        (self.root / ".github/harness/scripts").mkdir(parents=True)
        (self.root / ".github/harness/scripts/x.py").write_text("")
        (self.root / ".github/hooks").mkdir()
        (self.root / ".github/hooks/h.json").write_text(
            json.dumps(self._cfg(".github/harness/scripts/x.py"))
        )
        self.assertEqual(self.errs(), [])

    def test_hook_with_missing_script_fails(self):
        self.assertTrue(
            any(
                "missing script" in e
                for e in self._hook(self._cfg(".github/harness/scripts/nope.py"))
            )
        )

    def test_hook_bad_version_and_bad_json_fail(self):
        self.assertTrue(
            any(
                "'version' must be 1" in e
                for e in self._hook(self._cfg("x", version=2))
            )
        )
        self.assertTrue(any("invalid JSON" in e for e in self._hook("{oops")))


class ProposalScopeTests(unittest.TestCase):
    def test_proposal_files_do_not_count_as_out_of_scope(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            git(root, "init", "-b", "main")
            (root / "src").mkdir()
            (root / "src/a.c").write_text("a\n")
            pd = root / "docs/exec-plans/active/x"
            pd.mkdir(parents=True)
            plan = pd / "01-plan.md"
            plan.write_text("---\nbase: main\nallowed_files:\n  - src/*.c\n---\n")
            git(root, "add", "-A")
            git(root, "commit", "-m", "b")
            git(root, "switch", "-c", "agent/x")
            (root / ".github/harness/proposals").mkdir(parents=True)
            (root / ".github/harness/proposals/p.md").write_text("x\n")
            self.assertEqual(scope_check.check(root, plan), [])
            (root / ".github/harness/other.md").write_text("x\n")
            self.assertTrue(any("other.md" in v for v in scope_check.check(root, plan)))


if __name__ == "__main__":
    unittest.main()
