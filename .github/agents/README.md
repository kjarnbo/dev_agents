# Multi-agent coding workflow for GitHub Copilot (VS Code)

Three phase agents, three read-only helpers, scripts for everything that can be checked by a machine.

```
user ─▶ strategizer ─▶ planner ─▶ coder ─▶ reviewer        (≤ 3 handoffs, each a button YOU click)
          │  └ standards-discoverer, explorer   └ explorer
          ▼
   docs/exec-plans/active/<date>-<slug>/   00-brief.md → 01-plan.md → 02-progress.md → 03-review.md
```

| Agent | Job | Tools (least privilege) |
|---|---|---|
| `strategizer` | WHAT + acceptance criteria → `00-brief.md` | search, read, edit, todo, agent |
| `planner` | HOW → `01-plan.md` (anchors + exact code, small green steps, `allowed_files`) | search, read, edit, todo, agent |
| `coder` | Executes the plan; verifies after every step; bounded self-repair | search, read, edit, execute, todo |
| `reviewer` | Independent check of diff vs. acceptance criteria; never edits | search, read, execute |
| `explorer` | Read-only scout; returns pointers, not file contents | search, read |
| `standards-discoverer` | Finds and VERIFIES build/test/lint commands; caches with file hashes | search, read, execute |

## Usage
1. Pick `strategizer`, describe the request. Review `00-brief.md`.
2. Click **Plan this brief**. Review `01-plan.md` (this is the cheapest place to catch mistakes).
3. Click **Implement this plan**. The coder commits one step at a time on `agent/<slug>`.
4. Click **Independent review**. Read `03-review.md`.

## If you hit a rate limit or lose the chat
State is in files. Start a new chat, select the agent for the current phase, say **"resume"**.
It reads `02-progress.md` and continues from the first unchecked step. Fewer subagents also means fewer requests per run.

## What is enforced by machine (see `.github/harness/CONTROLS.md`)
- Tool lists per agent (frontmatter): helpers cannot edit; coder cannot spawn agents.
- `scope_check.py`: only files in the plan's `allowed_files` may change; no work on main/master.
- `verify.py`: gates in order, fail fast, pre-existing failures reported separately, output bounded.
- `standards_cache.py`: cache holds verified commands + pointers, invalidated by content hash.
- `harness_lint.py` (CI): AGENTS.md ≤ 100 lines, agent bodies ≤ 90, hop chain ≤ 4, no `*` tools, controls not past review date.

Advisory only (prose, may be ignored): coder repair limit, reviewer independence, brief quality.

## Project setup
Optional: commit `.github/harness/gates.json` (`[{"name":"build","command":"make"}, ...]`, fastest first). It wins over discovery.
Add a short `AGENTS.md` (≤ 100 lines) to the target project as a map to your own docs.

## Maintaining the harness
Run `python .github/harness/scripts/harness_lint.py` and `python -m unittest discover -s .github/harness/tests`.
Add a control only after a real failure, and record it in CONTROLS.md. Delete controls that stop paying for themselves.
