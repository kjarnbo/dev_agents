# dev_agents — map for agents working on this repo

This repo IS a harness for GitHub Copilot in VS Code: three phase agents (strategizer → planner → coder), helpers
(explorer, standards-discoverer, reviewer), `ask` (read-only Q&A for users) and `rule-curator` (turns durable rules into proposals). This file is a map, not a manual.

## Where things live
- `.github/agents/*.agent.md` — the eight agents (flat folder, one file each)
- `.github/hooks/` — hook config; `rule-signals.json` logs rule-like prompts
- `.github/harness/proposals/` — rule proposals (pending / applied / rejected)
- `.github/harness/CONTROLS.md` — every control, why it exists, how it is enforced, when to re-justify it
- `.github/harness/DECISIONS.md` — dated decisions and the evidence behind them
- `.github/harness/templates/` — brief, plan, progress, review templates
- `.github/harness/scripts/` — verify, scope_check, standards_cache, rule_signals, phase, harness_lint (stdlib Python only)
- `.github/harness/tests/` — tests for the scripts and the lint
- `.github/agents/README.md` — human-facing overview and usage

## Commands (run before finishing any change here)
- `python .github/harness/scripts/harness_lint.py`
- `python -m unittest discover -s .github/harness/tests -v`

## Rules for changing the harness
1. Add a control only in response to an observed failure. Record that failure in CONTROLS.md and DECISIONS.md.
2. Prefer a script or a frontmatter restriction over a prose rule. Prose is advisory; mark it `advisory` in CONTROLS.md.
3. Every script rule gets two tests: one where it must fire, one where it must not.
4. Keep this file at 100 lines or fewer and each agent body at 90 lines or fewer (the lint enforces both).
5. Never pin a `model:` in agent frontmatter without an eval that justifies it.
   Target the Copilot harness only: no `handoffs`, `agents`, `argument-hint`, `advancedOptions` (Local-only, deprecated).
6. Remove a rule before adding a new one when they overlap.
7. A user-stated rule goes through `rule-curator`: propose, user approves, then apply. Never edit rules directly.
8. Agent `description` = what it does. `Use when ...`. `Not for ...`. Max 350 chars, no bare `: ` (quote it).

## Resuming interrupted work
Work state lives in files, not in chat. Active work is in `docs/exec-plans/active/<date>-<slug>/`;
`02-progress.md` there is the resume point, and its `Phase:` line names the next agent.
Run `python .github/harness/scripts/phase.py status` to see where each plan is, then pick that agent and say "resume".
