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
from test_harness import agent, make_repo

TODAY = datetime.date(2026, 11, 21)


def lint_one(name, text):
    with tempfile.TemporaryDirectory() as d:
        make_repo(d, {name: text})
        return harness_lint.lint(d, TODAY)[0]


class LocalOnlyFieldTests(unittest.TestCase):
    def test_each_local_only_field_is_rejected(self):
        extras = {
            "handoffs": "handoffs:\n  - label: go\n    agent: b\n    prompt: hi\n",
            "agents": "agents: ['b']\n",
            "argument-hint": "argument-hint: some hint\n",
            "advancedOptions": "advancedOptions: x\n",
        }
        for field, extra in extras.items():
            e = lint_one("a", agent(extra=extra))
            self.assertTrue(
                any(f"'{field}' is Local-harness-only" in x for x in e), field
            )

    def test_agent_without_them_passes(self):
        self.assertEqual(lint_one("a", agent()), [])


class SubagentInvocabilityTests(unittest.TestCase):
    def test_non_helper_must_disable_model_invocation(self):
        no_flag = (
            "---\ndescription: x. Use when a. Not for b.\ntools: ['read']\n---\nb\n"
        )
        self.assertTrue(
            any(
                "disable-model-invocation: true" in x
                for x in lint_one("coder", no_flag)
            )
        )
        false_flag = agent().replace(
            "disable-model-invocation: true", "disable-model-invocation: false"
        )
        self.assertTrue(
            any(
                "disable-model-invocation: true" in x
                for x in lint_one("coder", false_flag)
            )
        )
        self.assertEqual(lint_one("coder", agent()), [])

    def test_helper_must_be_hidden_and_invocable(self):
        helper_ok = agent(tools="['read']", helper=True)
        self.assertEqual(lint_one("explorer", helper_ok), [])
        picker_visible = (
            "---\ndescription: x. Use when a. Not for b.\ntools: ['read']\n---\nb\n"
        )
        self.assertTrue(
            any(
                "user-invocable: false" in x
                for x in lint_one("explorer", picker_visible)
            )
        )
        blocked = agent(helper=True, extra="disable-model-invocation: true\n")
        self.assertTrue(
            any("must stay invocable" in x for x in lint_one("explorer", blocked))
        )


class ToolRuleTests(unittest.TestCase):
    def test_agent_tool_only_for_delegators(self):
        t = "['read','agent']"
        self.assertTrue(
            any("not a delegator" in x for x in lint_one("coder", agent(tools=t)))
        )
        for ok in ("strategizer", "planner", "ask"):
            self.assertEqual(
                [x for x in lint_one(ok, agent(tools=t)) if "delegator" in x], [], ok
            )

    def test_unknown_tool_alias_flagged_qualified_and_known_pass(self):
        self.assertTrue(
            any(
                "unknown tool 'bash'" in x
                for x in lint_one("a", agent(tools="['read','bash']"))
            )
        )
        self.assertEqual(
            lint_one(
                "a", agent(tools="['read','search','web','todo','vscode/askQuestions']")
            ),
            [],
        )


class RepoConsistencyTests(unittest.TestCase):
    def body(self, name):
        return (REPO / ".github/agents" / f"{name}.agent.md").read_text()

    def test_no_button_vocabulary_in_agents_or_docs(self):
        for f in list((REPO / ".github/agents").glob("*.md")) + [REPO / "AGENTS.md"]:
            t = f.read_text().lower()
            self.assertNotIn("handoff button", t, f.name)
            self.assertNotIn('propose as a rule"', t.replace("`", ""), f.name)

    def test_phase_agents_use_phase_protocol_and_print_next(self):
        for name in ("strategizer", "planner", "coder", "reviewer"):
            t = self.body(name)
            self.assertIn("Phase", t, name)
            self.assertIn("Next:", t, name)

    def test_only_expected_agents_hold_the_agent_tool(self):
        holders = {
            f.name[: -len(".agent.md")]
            for f in (REPO / ".github/agents").glob("*.agent.md")
            if "'agent'" in f.read_text().split("\n---\n")[0]
        }
        self.assertEqual(holders, {"strategizer", "planner", "ask"})

    def test_reviewer_has_no_edit_tool_but_a_write_path(self):
        t = self.body("reviewer")
        self.assertNotIn("'edit'", t.split("\n---\n")[0])
        self.assertIn("phase.py put-review", t)

    def test_hook_registers_only_the_documented_event_with_timeout(self):
        cfg = json.loads((REPO / ".github/hooks/rule-signals.json").read_text())
        self.assertEqual(list(cfg["hooks"]), ["userPromptSubmitted"])
        self.assertEqual(cfg["hooks"]["userPromptSubmitted"][0]["timeoutSec"], 10)


class PhaseTests(unittest.TestCase):
    def setUp(self):
        self.t = tempfile.TemporaryDirectory()
        self.root = Path(self.t.name)

    def tearDown(self):
        self.t.cleanup()

    def plan(self, slug, phase_line="Phase: plan", extra="\n## Steps\n- [ ] 1 x\n"):
        d = self.root / "docs/exec-plans/active" / slug
        d.mkdir(parents=True)
        (d / "02-progress.md").write_text(f"# Progress\n{phase_line}\n{extra}")
        return d

    def run_cli(self, *args, stdin=""):
        r = subprocess.run(
            [sys.executable, str(S / "phase.py"), *args, "--root", str(self.root)],
            input=stdin,
            capture_output=True,
            text=True,
        )
        return r.returncode, r.stdout + r.stderr

    def test_status_names_next_agent_per_phase(self):
        for slug, ph, agent_name in [
            ("a", "brief", "strategizer"),
            ("b", "plan", "planner"),
            ("c", "implement", "coder"),
            ("d", "review", "reviewer"),
        ]:
            self.plan(slug, f"Phase: {ph}")
        rc, out = self.run_cli("status")
        self.assertEqual(rc, 0)
        for slug, agent_name in [
            ("a", "strategizer"),
            ("b", "planner"),
            ("c", "coder"),
            ("d", "reviewer"),
        ]:
            self.assertRegex(out, rf"{slug}: Phase=\w+\. Next: switch to {agent_name}")

    def test_done_plan_has_no_next_agent(self):
        self.plan("x", "Phase: done")
        rc, out = self.run_cli("status")
        self.assertEqual(rc, 0)
        self.assertIn("Finished", out)
        self.assertNotIn("Next:", out)

    def test_invalid_or_missing_phase_exits_1(self):
        self.plan("x", "Phase: shipping")
        self.assertEqual(self.run_cli("status")[0], 1)
        d = self.root / "docs/exec-plans/active/y"
        d.mkdir(parents=True)
        (d / "02-progress.md").write_text("# no phase line here\n")
        rc, out = self.run_cli("status")
        self.assertEqual(rc, 1)
        self.assertIn("INVALID or missing", out)

    def test_no_plans_is_not_an_error(self):
        rc, out = self.run_cli("status")
        self.assertEqual(rc, 0)
        self.assertIn("No active plans", out)

    def test_set_changes_only_the_phase_line(self):
        d = self.plan(
            "x",
            "Phase: plan",
            extra="\n## Steps\n- [x] 1 keep me\nPhase mentioned in prose stays.\n",
        )
        before = (d / "02-progress.md").read_text()
        rc, _ = self.run_cli("set", "docs/exec-plans/active/x", "implement")
        after = (d / "02-progress.md").read_text()
        self.assertEqual(rc, 0)
        self.assertEqual(after, before.replace("Phase: plan", "Phase: implement", 1))

    def test_set_rejects_invalid_phase(self):
        d = self.plan("x")
        before = (d / "02-progress.md").read_text()
        rc, out = self.run_cli("set", "docs/exec-plans/active/x", "shipping")
        self.assertNotEqual(rc, 0)
        self.assertEqual((d / "02-progress.md").read_text(), before)

    def test_put_review_writes_only_the_review(self):
        d = self.plan("x")
        rc, _ = self.run_cli(
            "put-review", "docs/exec-plans/active/x", stdin="# Review\nall met\n"
        )
        self.assertEqual(rc, 0)
        self.assertEqual((d / "03-review.md").read_text(), "# Review\nall met\n")
        self.assertEqual(
            sorted(p.name for p in d.iterdir()), ["02-progress.md", "03-review.md"]
        )

    def test_put_review_refuses_empty_input(self):
        d = self.plan("x")
        rc, _ = self.run_cli("put-review", "docs/exec-plans/active/x", stdin="  \n")
        self.assertNotEqual(rc, 0)
        self.assertFalse((d / "03-review.md").exists())

    def test_folders_outside_exec_plans_are_refused(self):
        (self.root / "src").mkdir()
        (self.root / "src/02-progress.md").write_text("Phase: plan\n")
        for bad in ["src", "../outside", "docs/exec-plans/../../src", "/tmp"]:
            rc, out = self.run_cli("put-review", bad, stdin="x\n")
            self.assertNotEqual(rc, 0, bad)
        self.assertFalse((self.root / "src/03-review.md").exists())
        rc, _ = self.run_cli("set", "src", "done")
        self.assertNotEqual(rc, 0)
        self.assertEqual(
            (self.root / "src/02-progress.md").read_text(), "Phase: plan\n"
        )


if __name__ == "__main__":
    unittest.main()
