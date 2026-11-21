# Decisions

## 2026-11-21 — Consolidate 11 agents into 3 phase agents + 3 helpers
Why: the old flow was ~6 agent-to-agent hops with 8 subagents. A production SRE agent grew to 50+ specialists, saw
failures past 4 handoffs, and rolled back to a few generalists. A 4-role team solved 72.2% vs 71.8% for the best single agent.
Removed: requirements-analyzer, validator, spec-writer, change-planner, code-applier, verifier (each was a step of its
parent's reasoning, or a command runner). Kept: explorer (renamed code-analyzer), standards-discoverer.
Sources: Microsoft Azure SRE Agent; Marmelab 2026 (citing Agyn).

## 2026-11-21 — Exact line numbers replaced by anchors
Why: with several edits per file, line numbers are wrong after the first edit.

## 2026-11-21 — "Dumb coder" relaxed to bounded self-repair
Why: the loop of act, run an oracle, repair, repeat is the pattern with production evidence at scale.
Bound: 3 attempts, inside `allowed_files`, logged. REVERT if evals show scope creep.
Sources: OpenAI harness engineering; Vercel verification contract.

## 2026-11-21 — Files, not chat, carry state between phases
Why: agents only see what is in context or the repo; file state also survives rate limits and new chats.
Sources: OpenAI (repository as system of record); Microsoft (filesystem as the agent's world).

## 2026-11-21 — Reviewer kept, but grounded in an oracle and independent of the Coder
Conflict in sources: one ablation found an added reviewer lowered success 8%; others find separate evaluators beat
self-evaluation. Resolution: keep one reviewer that sees only brief, plan, diff and script output. MEASURE before trusting.

## 2026-11-21 — Prose rules paired with scripts
Why: only ~4-16% of written security rules had a matching built-in control in a study of 481 CLAUDE.md files.
Sources: arXiv 2608.23550; Marmelab.

## 2026-11-21 — Stale `model:` pins removed
Why: gpt-4o / gpt-4o-mini pins date from Oct 2025. Controls that compensate for a model's weaknesses rot as models improve.
