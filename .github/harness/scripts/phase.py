#!/usr/bin/env python3
"""Workflow state machine for plan folders. Stdlib only.

The Copilot harness has no agent-to-agent handoff buttons, so phases are chained by a `Phase:` line in
docs/exec-plans/active/<slug>/02-progress.md. `Phase` names the NEXT phase to run and who owns it:
  brief -> strategizer | plan -> planner | implement -> coder | review -> reviewer | done -> (nobody)
  status                       where is each active plan, and which agent should you pick next?
  set <folder> <phase>         change only the Phase line
  put-review <folder> < text   write <folder>/03-review.md from stdin (the reviewer's only write path)
Folders must live under docs/exec-plans/. Exit: 0 ok, 1 invalid state, 2 bad arguments.
"""
import argparse
import re
import sys
from pathlib import Path

PHASES = {"brief": "strategizer", "plan": "planner", "implement": "coder", "review": "reviewer", "done": None}
PHASE_RE = re.compile(r"^Phase:\s*([A-Za-z-]+)", re.M)
PLANS = Path("docs") / "exec-plans"


def read_phase(progress):
    m = PHASE_RE.search(progress.read_text()) if progress.exists() else None
    return m.group(1).lower() if m else None


def plan_folder(root, arg):
    """Resolve a folder argument, refusing anything outside docs/exec-plans/."""
    root = Path(root).resolve()
    p = (root / arg).resolve() if not Path(arg).is_absolute() else Path(arg).resolve()
    allowed = (root / PLANS).resolve()
    if allowed != p and allowed not in p.parents:
        raise SystemExit(f"refusing '{arg}': plan folders must be inside docs/exec-plans/")
    return p


def status(root):
    root = Path(root).resolve()
    files = sorted((root / PLANS / "active").glob("*/02-progress.md"))
    if not files:
        print("No active plans. Start with the strategizer agent.")
        return 0
    bad = 0
    for f in files:
        ph = read_phase(f)
        rel = f.parent.relative_to(root).as_posix()
        if ph not in PHASES:
            print(f"{rel}: INVALID or missing Phase ({ph!r}). Set one of {sorted(PHASES)} (python phase.py set).")
            bad += 1
        elif PHASES[ph] is None:
            print(f"{rel}: Phase={ph}. Finished. Move it to docs/exec-plans/completed/ when merged.")
        else:
            print(f"{rel}: Phase={ph}. Next: switch to {PHASES[ph]} and send \"resume\".")
    return 1 if bad else 0


def set_phase(root, folder, phase):
    if phase not in PHASES:
        raise SystemExit(f"invalid phase '{phase}'. Use one of {sorted(PHASES)}")
    f = plan_folder(root, folder) / "02-progress.md"
    if not f.exists():
        raise SystemExit(f"{f} not found")
    text = f.read_text()
    new, n = PHASE_RE.subn(f"Phase: {phase}", text, count=1)
    f.write_text(new if n else f"Phase: {phase}\n" + text)
    print(f"Phase: {phase}")
    return 0


def put_review(root, folder, content):
    if not content.strip():
        raise SystemExit("refusing to write an empty review")
    d = plan_folder(root, folder)
    if not d.is_dir():
        raise SystemExit(f"{d} is not an existing plan folder")
    (d / "03-review.md").write_text(content if content.endswith("\n") else content + "\n")
    print("wrote 03-review.md")
    return 0


def main():
    p = argparse.ArgumentParser()
    p.add_argument("cmd", choices=["status", "set", "put-review"])
    p.add_argument("args", nargs="*")
    p.add_argument("--root", default=".")
    a = p.parse_args()
    if a.cmd == "status":
        return status(a.root)
    if a.cmd == "set":
        if len(a.args) != 2:
            raise SystemExit("usage: phase.py set <folder> <phase>")
        return set_phase(a.root, *a.args)
    if len(a.args) != 1:
        raise SystemExit("usage: phase.py put-review <folder> < review.md")
    return put_review(a.root, a.args[0], sys.stdin.read())


if __name__ == "__main__":
    sys.exit(main())
