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

## 2026-11-21 — `ask`: a user-facing read-only guide, separate from `explorer`
Why: `explorer` is a subagent that returns pointers to other agents. Users need cited, evidence-labelled answers about
configuration and behaviour. Different audience, different output, so a separate agent. Tools are `search`, `read`, `agent`
only; lint forbids `edit` and `execute`, so "without changing it" is enforced, not requested.
Sources: Vercel (read-only explorer, context isolation); Marmelab (restrict subagent tools).

## 2026-11-21 — Rule capture: deterministic detection, model judgement, human approval
Why: durable user rules were lost when they appeared only in chat. Detection is a hook plus a regex heuristic, which is
cheap and does not depend on the model remembering. Judgement and placement are the rule-curator's. Nothing changes without
an explicit `apply`. Prefer a script or frontmatter control over prose.
Limits: the heuristic is English-only and will miss rules phrased without signal words; the hook only logs, because I
could not confirm that Copilot hook output can inject context. The in-chat flag is the fallback.
Sources: Marmelab (every control needs an incident and an expiry; generated context hurts); arXiv 2608.23550 (prose rules
are rarely backed by a control).

## 2026-11-21 — Proposal lifecycle keeps rejected proposals
Why: a record of declined rules stops the same rule being proposed repeatedly. Pending proposals expire after 30 days.

## 2026-11-21 — Reading pass 2: what was read, and what it changed
Read directly: Vercel lessons "Descriptions That Work", "Structuring Agent Instructions", "Explorer Subagent",
"Structured Questions", "Fast Context Understanding" (plus "Why Delegate", "Verification Contract" earlier).
Read via a secondary summary only (ZenML LLMOps Database): the Microsoft Azure SRE Agent article. The primary page
returns no body. Its figures are self-reported by Microsoft; treat them as one team's experience.
NOT read: Vercel modules 4, 7, 10; "Approval Config", "Todo Tool", "Skills System", "Pruning Old Results",
"Tool Output Design", "Extension Points", "Hard-Won Lessons".

## 2026-11-21 — Agent descriptions are a routing contract
Why: in Vercel's tests, models drift toward the most general option ("bash gravity") unless descriptions say both when
to use a tool and when not to. In Copilot the `description` plays that role for subagent routing. Lint requires
"Use when/for" and "Not for", and a 350-char cap because descriptions are loaded on every request.
Also found while checking: a bare ": " in a plain YAML value is invalid and can break loading; lint now catches it.

## 2026-11-21 — Ambiguity protocol added to the strategizer
Why: "models will not ask on their own". Scripted as search, ask (max 3, numbered options, recommended default, end the
turn), act, with one example of each case. Specific tasks are told not to ask, to avoid over-asking.
Source: Vercel "Structured Questions". Cost: asking uses a turn, which matters on a free tier; the "cheap to reverse"
exception keeps it rare.

## 2026-11-21 — Large output is data, not context
Why: Microsoft's agent hit a 200,000-token log row; their fix was to write large outputs to files and inspect them
on demand. `verify.py` now saves each gate's full output, reports a 40-line tail plus up to 10 error lines, and
agents are told to grep the saved log. Early compiler errors scroll off a pure tail, so error lines are pulled out too.

## 2026-11-21 — Explorer gets a step budget and must never return silence
Why: Vercel caps explorers at 5 steps and returns failures as text so the parent can react. Parents are told not to
repeat a question the explorer answered with "Unknown".

## 2026-11-21 — Skills still deferred
Why: Vercel and Microsoft both describe skills (names in context, full content on demand). I could not confirm how
Copilot skills interact with custom agents that have restricted `tools`, so nothing was added. Revisit after verifying.

## 2026-11-21 — CORRECTION: handoffs and `agents` are Local-harness-only
Reported by the user (handoffs did not work). Verified against VS Code docs: custom-agent file reference (11/18/2026),
subagents, hooks (10/28/2026). `handoffs`, `agents`, `argument-hint`, `advancedOptions` are Local-only; the Local
harness is deprecated and removed Feb 2027; the Copilot harness does not accept them. My earlier "verification" read a
doc snippet without checking which harness it described. That was the error.
Changes: removed those fields; lint now rejects them. Phases chain through a `Phase:` line in 02-progress.md and a
`Next:` line each agent prints; `phase.py status` shows where each plan is. Subagent control now uses
`disable-model-invocation` and `user-invocable` (the only controls in the Copilot harness).
Supersedes: "hop chain <= 4" lint (no machine-readable edges remain; the workflow still has 4 user-driven phases).
Also found: `target: github-copilot` refers to the Copilot CLOUD agent, not the Copilot harness in VS Code. Not used.
Also fixed: the reviewer was told to write 03-review.md but had no edit tool. It now writes only through `phase.py`.
Hooks: format confirmed (`.github/hooks/*.json`, `version: 1`, `userPromptSubmitted`, `timeoutSec`; output ignored for
that event, so log-only is correct). Removed the redundant PascalCase event, since event names select the payload format.
NOT verified: exact `userPromptSubmitted` payload fields (docs.github.com hooks reference not read), and whether hooks
run for every session target. Test with a disposable session.
