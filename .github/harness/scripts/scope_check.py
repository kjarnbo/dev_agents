#!/usr/bin/env python3
"""Deterministic scope guard: changed files must match the plan's allowed_files globs,
and work must not happen on a protected branch. Stdlib only. Exit 0 ok, 1 violation.
  python scope_check.py --plan docs/exec-plans/active/<slug>/01-plan.md
"""

import argparse
import fnmatch
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import fm

PROTECTED = {"main", "master"}


def git(root, *args):
    r = subprocess.run(["git", *args], check=False, cwd=root, capture_output=True, text=True)
    return r.returncode, r.stdout.strip()


def changed_files(root, base):
    rc, mb = git(root, "merge-base", "HEAD", base)
    ref = mb if rc == 0 and mb else "HEAD"
    files = set(git(root, "diff", "--name-only", ref)[1].splitlines())
    files |= set(
        git(root, "ls-files", "--others", "--exclude-standard")[1].splitlines()
    )
    return {f for f in files if f}


def check(root, plan_path):
    root = Path(root).resolve()
    plan = Path(plan_path)
    plan = plan if plan.is_absolute() else root / plan
    meta, _ = fm.parse(plan.read_text())
    allowed = meta.get("allowed_files") or []
    if not isinstance(allowed, list) or not allowed:
        return [
            f"{plan.name}: no 'allowed_files' list in frontmatter. Planner must list every file (globs ok) the Coder may touch."
        ]
    base = meta.get("base") or "main"
    plan_dir = plan.parent.relative_to(root).as_posix() + "/"
    violations = []
    _, branch = git(root, "rev-parse", "--abbrev-ref", "HEAD")
    if branch in PROTECTED:
        violations.append(
            f"On protected branch '{branch}'. Run: git switch -c agent/<slug> before editing."
        )
    for f in sorted(changed_files(root, base)):
        if f.startswith(
            (plan_dir, ".github/cache/", ".github/harness/proposals/")
        ) or any(fnmatch.fnmatch(f, g) for g in allowed):
            continue
        violations.append(
            f"Out-of-scope change: {f}. Revert it (git checkout -- {f}) or stop and ask the Planner to amend allowed_files."
        )
    return violations


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--root", default=".")
    p.add_argument("--plan", required=True)
    a = p.parse_args()
    v = check(a.root, a.plan)
    for line in v:
        print("VIOLATION", line)
    print("scope ok" if not v else f"{len(v)} violation(s)")
    return 1 if v else 0


if __name__ == "__main__":
    sys.exit(main())
