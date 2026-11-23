# Multi-agent coding workflow for GitHub Copilot (VS Code)

Three phase agents, helpers, a read-only `ask` agent, a `rule-curator`, and scripts for everything a machine can check.

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
| `ask` | **You** explore the codebase: configuration, behaviour, impact. Cited answers, never changes anything | search, read, agent |
| `rule-curator` | Decides if something you said is a durable rule; proposes where it goes and how to enforce it | search, read, edit, execute |
| `explorer` | Read-only scout; returns pointers, not file contents | search, read |
| `standards-discoverer` | Finds and VERIFIES build/test/lint commands; caches with file hashes | search, read, execute |

## Usage
1. Pick `strategizer`, describe the request. Review `00-brief.md`.
2. Click **Plan this brief**. Review `01-plan.md` (this is the cheapest place to catch mistakes).
3. Click **Implement this plan**. The coder commits one step at a time on `agent/<slug>`.
4. Click **Independent review**. Read `03-review.md`.

## Explore without changing anything
Pick `ask` and ask anything: "where does X get its default?", "how does Y work end to end?", "what depends on Z?".
Answers lead with the result, then a `path:symbol` trace, with each claim marked Confirmed, Inferred or Not found.
It has no edit or execute tools. Use **Turn this into a change request** to move into the workflow.

## Rules: capture, propose, approve
If you say something durable ("always...", "never...", "from now on...", "we use..."), it is caught two ways:
a hook (`.github/hooks/rule-signals.json`) logs rule-like sentences to `.github/cache/rule-candidates.jsonl`,
and phase agents end their reply with a "Possible general rule" line. Neither changes any rule.
Open `rule-curator` (or click **Propose as a rule**) and say "review candidates". It classifies each one
(rule / one-off / unclear), checks duplicates, picks a destination, and writes
`.github/harness/proposals/<date>-<slug>.md`. You then say `apply <slug>` or `reject <slug> <reason>`.
Destinations: a script or frontmatter control (preferred), an agent file, or `docs/rules/<topic>.md` for project conventions.

## If you hit a rate limit or lose the chat
State is in files. Start a new chat, select the agent for the current phase, say **"resume"**.
It reads `02-progress.md` and continues from the first unchecked step. Fewer subagents also means fewer requests per run.

## What is enforced by machine (see `.github/harness/CONTROLS.md`)
- Tool lists per agent (frontmatter): helpers cannot edit; coder cannot spawn agents.
- `scope_check.py`: only files in the plan's `allowed_files` may change; no work on main/master.
- `verify.py`: gates in order, fail fast, pre-existing failures reported separately, output bounded.
- `standards_cache.py`: cache holds verified commands + pointers, invalidated by content hash.
- `rule_signals.py`: deterministic rule detection (hook) plus candidate bookkeeping.
- `harness_lint.py` (CI): `ask`/`explorer` cannot execute, proposals and hooks valid, AGENTS.md ≤ 100 lines, agent bodies ≤ 90, hop chain ≤ 4, no `*` tools, controls not past review date.

Advisory only (prose, may be ignored): coder repair limit, reviewer independence, brief quality, the in-chat rule flag.

## Project setup
Optional: commit `.github/harness/gates.json` (`[{"name":"build","command":"make"}, ...]`, fastest first). It wins over discovery.
Add a short `AGENTS.md` (≤ 100 lines) to the target project as a map to your own docs.

## Maintaining the harness
Run `python .github/harness/scripts/harness_lint.py` and `python -m unittest discover -s .github/harness/tests`.
Add a control only after a real failure, and record it in CONTROLS.md. Delete controls that stop paying for themselves.
