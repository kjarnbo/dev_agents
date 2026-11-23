# Controls register

Every control exists to stop a specific failure. When the model stops making that mistake, the control is pure cost:
re-justify it with evidence by its review date, or delete it. `harness_lint.py` fails once a date has passed.

`Enforcement`: `frontmatter` = blocked by the Copilot tool list; `script` = checked deterministically; `advisory` = prose only, may be ignored.

| Control | Why (failure it prevents) | Enforcement | Review by |
|---|---|---|---|
| Explorer, reviewer, discoverer have no `edit` tool | An exploring agent "helpfully" fixes code it was only meant to read | frontmatter + harness_lint | 2027-02-21 |
| `tools` and `agents` always explicit in every agent | Omitted `tools` grants everything; most subagents in the wild see all tools | harness_lint | 2027-02-21 |
| Coder may touch only plan `allowed_files` | "Do not deviate from the spec" as prose is not enforced | script: scope_check.py | 2027-02-21 |
| No agent work on main/master | Direct edits to the default branch are hard to undo | script: scope_check.py | 2027-02-21 |
| Gates run fixed order, fail fast, pre-existing failures flagged | Agents claim "tests pass" without running them, or blame themselves for old failures | script: verify.py | 2027-02-21 |
| Standards cache stores verified commands and pointers, invalidated by file hash | Generated prose context lowers success and cost more; calendar expiry misses real changes | script: standards_cache.py | 2027-02-21 |
| AGENTS.md at most 100 lines; agent bodies at most 90 | Oversized instruction files crowd out the task and rot | harness_lint | 2027-02-21 |
| Longest agent hop chain at most 4 | Handoff chains beyond 4 failed in a production agent | harness_lint | 2027-02-21 |
| Coder repair limit of 3 attempts, then stop | Unbounded self-repair loops burn quota and drift out of scope | advisory (reviewer checks progress log) | 2027-02-21 |
| Reviewer ignores Coder narrative | Self-evaluation is biased toward approving own work | advisory | 2027-02-21 |
| `ask` and `explorer` have no `execute` tool; `ask` also has no `edit` | Exploring must never change the codebase, even by running a command | frontmatter + harness_lint | 2027-02-21 |
| Rule-like prompts are detected by a hook and logged to a git-ignored file | Relying on each agent to notice a durable rule means it gets missed | script: rule_signals.py via .github/hooks (hook support unverified in your VS Code build) | 2027-02-21 |
| Phase agents flag possible rules at the end of a reply | Fallback when hooks are off | advisory | 2027-02-21 |
| Rules change only via a proposal the user approves (`apply <slug>`) | Auto-edited instructions bloat and rot; generated context lowers success | advisory (rule-curator) + proposal lint | 2027-02-21 |
| Pending proposals expire after 30 days; applied rules carry a review-by date | Proposal pile-up and stale rules | harness_lint | 2027-02-21 |
| Rule application edits only the proposal's `allowed_files` | An approved rule should not widen into unrelated edits | script: scope_check.py (curator must run it) | 2027-02-21 |
| Hook configs must be valid and point at existing scripts | A dead hook fails silently | harness_lint | 2027-02-21 |
