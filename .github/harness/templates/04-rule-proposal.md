---
status: pending
created: YYYY-MM-DD
destination: project-rule
statement: "<the rule as one imperative sentence>"
why: "<the user's words or the incident that prompted it>"
review_by: YYYY-MM-DD
reason:
base: main
allowed_files:
  - AGENTS.md
---
# Proposal: <short title>

Allowed values: status = pending | applied | rejected. destination = project-rule | agent-behavior | enforced-control.
`reason` is required when rejected. `allowed_files` is exactly the files Apply will touch.

## Evidence (verbatim user words)

## Is it general?
Signals from `rule_signals.py scan`, and your judgement. Durable or one-off? Scope?

## Duplicates and conflicts checked
Files searched and what was found.

## Placement and enforcement
Why this destination. Can a script, frontmatter restriction or lint enforce it? If so, which, and the two tests (must fire / must not fire).

## Exact change
```diff
```

## Removal condition
When can this rule be deleted?
