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
import harness_lint
import scope_check
import standards_cache

TODAY = datetime.date(2026, 11, 21)


def agent(tools="['read']", extra="", body="Body\n", helper=False):
    """A lint-clean Copilot-harness agent. helper=True makes it a subagent-only helper."""
    flag = "user-invocable: false" if helper else "disable-model-invocation: true"
    return f"---\ndescription: x. Use when a. Not for b.\ntools: {tools}\n{flag}\n{extra}---\n{body}"


def make_repo(root, agents, agents_md_lines=10, review="2027-02-21"):
    root = Path(root)
    (root / ".github/agents").mkdir(parents=True)
    (root / ".github/harness").mkdir(parents=True)
    for n, t in agents.items():
        (root / ".github/agents" / f"{n}.agent.md").write_text(t)
    (root / "AGENTS.md").write_text("line\n" * agents_md_lines)
    (root / ".github/harness/CONTROLS.md").write_text(
        f"| Control | Why | Enforcement | Review by |\n|---|---|---|---|\n| c | w | script | {review} |\n"
    )


def errs(root, today=TODAY):
    return harness_lint.lint(root, today)[0]


class LintTests(unittest.TestCase):
    def setUp(self):
        self.t = tempfile.TemporaryDirectory()
        self.root = Path(self.t.name)

    def tearDown(self):
        self.t.cleanup()

    def test_real_repo_is_clean(self):
        self.assertEqual(harness_lint.lint(REPO, TODAY)[0], [])

    def test_valid_minimal_repo_passes(self):
        make_repo(self.root, {"a": agent()})
        self.assertEqual(errs(self.root), [])

    def test_wildcard_tools_fail(self):
        make_repo(self.root, {"a": agent(tools="['*']")})
        self.assertTrue(any("'*'" in e for e in errs(self.root)))

    def test_missing_tools_fail(self):
        make_repo(
            self.root,
            {
                "a": "---\ndescription: x. Use when a. Not for b.\ndisable-model-invocation: true\n---\nb\n"
            },
        )
        self.assertTrue(any("'tools' must be" in e for e in errs(self.root)))

    def test_read_only_role_with_edit_fails_but_other_role_may_edit(self):
        make_repo(
            self.root,
            {
                "explorer": agent(tools="['read','edit']"),
                "coder": agent(tools="['read','edit']"),
            },
        )
        e = errs(self.root)
        self.assertEqual(len([x for x in e if "read-only" in x]), 1)
        self.assertIn("explorer", [x for x in e if "read-only" in x][0])

    def test_agents_md_boundary(self):
        make_repo(self.root, {"a": agent()}, agents_md_lines=100)
        self.assertEqual(errs(self.root), [])
        (self.root / "AGENTS.md").write_text("x\n" * 101)
        self.assertTrue(any("AGENTS.md is 101" in e for e in errs(self.root)))

    def test_agent_body_boundary(self):
        make_repo(self.root, {"a": agent(body="x\n" * 90)})
        self.assertEqual(errs(self.root), [])
        make_repo(Path(tempfile.mkdtemp()), {"a": agent(body="x\n" * 91)})
        r2 = Path(tempfile.mkdtemp())
        make_repo(r2, {"a": agent(body="x\n" * 91)})
        self.assertTrue(any("body is 91" in e for e in errs(r2)))

    def test_expired_control_fails_unexpired_passes(self):
        make_repo(self.root, {"a": agent()}, review="2026-11-20")
        self.assertTrue(any("review-by" in e for e in errs(self.root)))
        make_repo(Path(tempfile.mkdtemp()), {"a": agent()}, review=TODAY.isoformat())
        r2 = Path(tempfile.mkdtemp())
        make_repo(r2, {"a": agent()}, review=TODAY.isoformat())
        self.assertEqual(errs(r2), [])


def git(root, *a):
    subprocess.run(
        ["git", "-c", "user.name=t", "-c", "user.email=t@t", *a],
        cwd=root,
        check=True,
        capture_output=True,
    )


class ScopeTests(unittest.TestCase):
    def setUp(self):
        self.t = tempfile.TemporaryDirectory()
        self.root = Path(self.t.name)
        git(self.root, "init", "-b", "main")
        (self.root / "src").mkdir()
        (self.root / "src/a.c").write_text("a\n")
        (self.root / "other.c").write_text("o\n")
        plan_dir = self.root / "docs/exec-plans/active/x"
        plan_dir.mkdir(parents=True)
        self.plan = plan_dir / "01-plan.md"
        self.plan.write_text(
            "---\nbase: main\nallowed_files:\n  - src/*.c\n---\nplan\n"
        )
        git(self.root, "add", "-A")
        git(self.root, "commit", "-m", "base")
        git(self.root, "switch", "-c", "agent/x")

    def tearDown(self):
        self.t.cleanup()

    def v(self):
        return scope_check.check(self.root, self.plan)

    def test_in_scope_change_ok(self):
        (self.root / "src/a.c").write_text("changed\n")
        self.assertEqual(self.v(), [])

    def test_out_of_scope_change_flagged(self):
        (self.root / "other.c").write_text("changed\n")
        v = self.v()
        self.assertEqual(len(v), 1)
        self.assertIn("other.c", v[0])

    def test_new_untracked_out_of_scope_flagged(self):
        (self.root / "new.txt").write_text("x\n")
        self.assertIn("new.txt", self.v()[0])

    def test_plan_folder_changes_allowed(self):
        (self.root / "docs/exec-plans/active/x/02-progress.md").write_text("p\n")
        self.assertEqual(self.v(), [])

    def test_committed_out_of_scope_still_flagged(self):
        (self.root / "other.c").write_text("changed\n")
        git(self.root, "commit", "-am", "oops")
        self.assertIn("other.c", self.v()[0])

    def test_protected_branch_flagged(self):
        git(self.root, "switch", "main")
        self.assertTrue(any("protected branch" in x for x in self.v()))

    def test_missing_allowed_files_flagged(self):
        self.plan.write_text("---\nbase: main\n---\nplan\n")
        self.assertIn("allowed_files", self.v()[0])


def run_verify(root, *args):
    r = subprocess.run(
        [sys.executable, str(S / "verify.py"), "--root", str(root), *args],
        capture_output=True,
        text=True,
    )
    return r.returncode, (
        json.loads(r.stdout) if r.stdout.strip().startswith("{") else r.stdout
    )


class VerifyTests(unittest.TestCase):
    def setUp(self):
        self.t = tempfile.TemporaryDirectory()
        self.root = Path(self.t.name)
        (self.root / ".github/harness").mkdir(parents=True)

    def tearDown(self):
        self.t.cleanup()

    def gates(self, items):
        (self.root / ".github/harness/gates.json").write_text(json.dumps(items))

    def test_all_pass(self):
        self.gates([{"name": "a", "command": "true"}, {"name": "b", "command": "true"}])
        rc, rep = run_verify(self.root)
        self.assertEqual(rc, 0)
        self.assertEqual(rep["claims"], ["a: passed", "b: passed"])

    def test_fail_fast_reports_not_run(self):
        self.gates(
            [
                {"name": "a", "command": "echo boom; false"},
                {"name": "b", "command": "true"},
            ]
        )
        rc, rep = run_verify(self.root)
        self.assertEqual(rc, 1)
        self.assertEqual(rep["not_run"], ["b"])
        self.assertIn("boom", rep["results"][0]["output_tail"])

    def test_preexisting_failure_does_not_block(self):
        self.gates(
            [{"name": "a", "command": "false"}, {"name": "b", "command": "true"}]
        )
        self.assertEqual(run_verify(self.root, "--baseline")[0], 0)
        rc, rep = run_verify(self.root)
        self.assertEqual(rc, 0)
        self.assertEqual(rep["claims"], ["a: failed preexisting", "b: passed"])

    def test_new_failure_still_blocks_with_baseline_present(self):
        self.gates([{"name": "a", "command": "true"}])
        run_verify(self.root, "--baseline")
        self.gates([{"name": "a", "command": "false"}])
        self.assertEqual(run_verify(self.root)[0], 1)

    def test_no_gates_exit_2(self):
        self.assertEqual(run_verify(self.root)[0], 2)

    def test_output_is_bounded(self):
        self.gates([{"name": "a", "command": "seq 1 500; false"}])
        _, rep = run_verify(self.root)
        self.assertEqual(len(rep["results"][0]["output_tail"].splitlines()), 40)


class CacheTests(unittest.TestCase):
    def setUp(self):
        self.t = tempfile.TemporaryDirectory()
        self.root = Path(self.t.name)
        (self.root / "Makefile").write_text("all:\n")

    def tearDown(self):
        self.t.cleanup()

    def payload(self):
        return {
            "sources": ["Makefile"],
            "gates": [{"name": "build", "command": "make", "verified": True}],
        }

    def test_missing_then_fresh_then_stale_on_change(self):
        self.assertEqual(standards_cache.check(self.root)[0], "MISSING")
        standards_cache.write(self.root, self.payload())
        self.assertEqual(standards_cache.check(self.root)[0], "FRESH")
        (self.root / "Makefile").write_text("all:\n\techo\n")
        self.assertEqual(standards_cache.check(self.root)[0], "STALE")

    def test_unrelated_file_change_stays_fresh(self):
        standards_cache.write(self.root, self.payload())
        (self.root / "README.md").write_text("new\n")
        self.assertEqual(standards_cache.check(self.root)[0], "FRESH")

    def test_unverified_gate_makes_stale(self):
        p = self.payload()
        p["gates"][0]["verified"] = False
        standards_cache.write(self.root, p)
        self.assertEqual(standards_cache.check(self.root)[0], "STALE")

    def test_write_rejects_nonexistent_source(self):
        p = self.payload()
        p["sources"] = ["ghost.md"]
        with self.assertRaises(SystemExit):
            standards_cache.write(self.root, p)


if __name__ == "__main__":
    unittest.main()
