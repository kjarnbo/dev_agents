#!/usr/bin/env python3
"""Mechanical checks for the harness itself. Stdlib only. Exit 1 on errors.

Targets the Copilot harness in VS Code (Session Target: Copilot). The Local harness is deprecated and
removed in Feb 2027, so Local-only frontmatter (handoffs, agents, ...) is rejected rather than relied on.
Every message says how to fix the problem, because the reader is usually an agent.
"""

import argparse
import datetime
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import fm

MAX_AGENTS_MD_LINES = 100
MAX_AGENT_BODY_LINES = 90
MAX_DESC_CHARS = 350  # descriptions are loaded on every request and drive routing
MAX_PENDING_DAYS = 30
READ_ONLY = {"explorer", "reviewer", "standards-discoverer", "ask"}
NO_EXECUTE = {"explorer", "ask"}  # roles that must not run commands at all
HELPERS = {
    "explorer",
    "standards-discoverer",
}  # the only agents other agents may invoke as subagents
DELEGATORS = {
    "strategizer",
    "planner",
    "ask",
}  # the only agents that may hold the 'agent' tool
LOCAL_ONLY_FIELDS = ("handoffs", "agents", "argument-hint", "advancedOptions")
TOOL_ALIASES = {"execute", "read", "edit", "search", "agent", "web", "todo"}
PROPOSAL_STATUS = {"pending", "applied", "rejected"}
PROPOSAL_DEST = {"project-rule", "agent-behavior", "enforced-control"}
PROPOSAL_REQUIRED = (
    "status",
    "created",
    "destination",
    "statement",
    "why",
    "review_by",
)


def _agent_files(root):
    d = root / ".github" / "agents"
    return sorted(d.glob("*.agent.md")) if d.is_dir() else []


def _is_true(v):
    return str(v).strip().lower() == "true"


def _is_false(v):
    return str(v).strip().lower() == "false"


def lint(root, today=None):
    root, today = Path(root), today or datetime.date.today()
    errors, warnings = [], []
    adir = root / ".github" / "agents"

    for f in adir.rglob("*.md") if adir.is_dir() else []:
        if f.parent.name != "agents":
            errors.append(
                f"{f.relative_to(root)}: nested agent file. Move it to .github/agents/ (flat layout)."
            )

    for f in _agent_files(root):
        meta, body = fm.parse(f.read_text())
        name = meta.get("name") or f.name[: -len(".agent.md")]
        rel = f.relative_to(root)

        desc = meta.get("description")
        if not desc:
            errors.append(
                f"{rel}: missing 'description'. Add: what it does. Use when ... Not for ..."
            )
        else:
            if len(desc) > MAX_DESC_CHARS:
                errors.append(
                    f"{rel}: description is {len(desc)} chars (max {MAX_DESC_CHARS}). It is loaded on every request; shorten it."
                )
            if not re.search(r"\bUse (when|for)\b", desc, re.IGNORECASE) or not re.search(
                r"\bNot for\b|\bDo not use for\b", desc, re.IGNORECASE
            ):
                errors.append(
                    f"{rel}: description needs both 'Use when/for ...' and 'Not for ...' so routing between agents is unambiguous."
                )
        errors.extend(_yaml_issues(f.read_text(), rel))

        for field in LOCAL_ONLY_FIELDS:
            if field in meta:
                errors.append(
                    f"{rel}: '{field}' is Local-harness-only (deprecated, removed Feb 2027) and is not supported by the "
                    f"Copilot harness. Remove it. Chain phases with the 'Next:' line and the Phase field in 02-progress.md."
                )

        tools = meta.get("tools")
        if not isinstance(tools, list) or not tools:
            errors.append(
                f"{rel}: 'tools' must be an explicit non-empty list. Omitting it grants every tool."
            )
        else:
            if "*" in tools:
                errors.append(
                    f"{rel}: 'tools' contains '*'. List only the tools this role needs."
                )
            for t in tools:
                if t != "*" and t not in TOOL_ALIASES and "/" not in t:
                    errors.append(
                        f"{rel}: unknown tool '{t}'. Copilot aliases are {sorted(TOOL_ALIASES)}; qualified tools look like 'server/tool'."
                    )
            if name in READ_ONLY and "edit" in tools:
                errors.append(
                    f"{rel}: read-only role '{name}' has the 'edit' tool. Remove 'edit' from tools."
                )
            if name in NO_EXECUTE and "execute" in tools:
                errors.append(
                    f"{rel}: role '{name}' must not run commands but has the 'execute' tool. Remove 'execute' from tools."
                )
            if "agent" in tools and name not in DELEGATORS:
                errors.append(
                    f"{rel}: '{name}' has the 'agent' tool but is not a delegator {sorted(DELEGATORS)}. Remove 'agent' from tools."
                )

        # Subagent invocability is the only subagent control the Copilot harness has.
        dmi, uinv = meta.get("disable-model-invocation"), meta.get("user-invocable")
        if name in HELPERS:
            if not _is_false(uinv):
                errors.append(
                    f"{rel}: helper '{name}' must set 'user-invocable: false' (it is for other agents, not the picker)."
                )
            if _is_true(dmi):
                errors.append(
                    f"{rel}: helper '{name}' must stay invocable as a subagent. Remove 'disable-model-invocation: true'."
                )
        elif not _is_true(dmi):
            errors.append(
                f"{rel}: '{name}' must set 'disable-model-invocation: true' so other agents cannot invoke it as a subagent."
            )

        if "model" in meta:
            warnings.append(
                f"{rel}: pins model '{meta['model']}'. Pinned names go stale; remove it unless an eval justifies it."
            )
        n = len(body.splitlines())
        if n > MAX_AGENT_BODY_LINES:
            errors.append(
                f"{rel}: body is {n} lines (max {MAX_AGENT_BODY_LINES}). Move reference material to .github/harness/templates/ and link it."
            )

    am = root / "AGENTS.md"
    if not am.exists():
        errors.append(
            "AGENTS.md missing. Create a map of at most 100 lines that links to deeper docs."
        )
    else:
        n = len(am.read_text().splitlines())
        if n > MAX_AGENTS_MD_LINES:
            errors.append(
                f"AGENTS.md is {n} lines (max {MAX_AGENTS_MD_LINES}). Keep it a table of contents; move detail into linked files."
            )

    cf = root / ".github" / "harness" / "CONTROLS.md"
    if not cf.exists():
        errors.append(
            ".github/harness/CONTROLS.md missing. Record each control, the reason it exists, and a review-by date."
        )
    else:
        rows = [
            r
            for r in cf.read_text().splitlines()
            if r.startswith("|") and not re.match(r"^\|[\s:-]+\|", r)
        ][1:]
        if not rows:
            errors.append(
                "CONTROLS.md has no rows. Add a table: Control | Why | Enforcement | Review by."
            )
        for r in rows:
            cells = [c.strip() for c in r.strip("|").split("|")]
            if len(cells) < 4 or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", cells[3]):
                errors.append(
                    f"CONTROLS.md row '{cells[0][:40]}': needs 4 cells ending in a YYYY-MM-DD review-by date."
                )
            elif datetime.date.fromisoformat(cells[3]) < today:
                errors.append(
                    f"CONTROLS.md control '{cells[0][:40]}' passed its review-by date {cells[3]}. Re-justify it with evidence, or delete it."
                )
    _lint_proposals(root, today, errors)
    _lint_hooks(root, errors)
    return errors, warnings


def _yaml_issues(text, rel):
    """Plain YAML scalars must not contain ': ' or ' #'. Quote the value instead."""
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return []
    end = next(
        (i for i in range(1, len(lines)) if lines[i].strip() == "---"), len(lines)
    )
    out = []
    for n, ln in enumerate(lines[1:end], start=2):
        m = re.match(r"^\s*(?:-\s+)?[\w-]+:\s+(.*)$", ln)
        if m:
            v = m.group(1)
            if v and v[0] not in "\"'[{|>" and (": " in v or " #" in v):
                out.append(
                    f"{rel}:{n}: unquoted value contains ': ' or ' #', which is invalid YAML. Wrap the value in double quotes."
                )
    return out


def _date(v):
    try:
        return datetime.date.fromisoformat(str(v))
    except ValueError:
        return None


def _lint_proposals(root, today, errors):
    d = root / ".github" / "harness" / "proposals"
    if not d.is_dir():
        return
    for f in sorted(d.glob("*.md")):
        meta, _ = fm.parse(f.read_text())
        rel = f.relative_to(root)
        errors.extend(_yaml_issues(f.read_text(), rel))
        missing = [k for k in PROPOSAL_REQUIRED if not meta.get(k)]
        if missing:
            errors.append(
                f"{rel}: missing frontmatter {missing}. Copy .github/harness/templates/04-rule-proposal.md."
            )
            continue
        if meta["status"] not in PROPOSAL_STATUS:
            errors.append(
                f"{rel}: status '{meta['status']}' must be one of {sorted(PROPOSAL_STATUS)}."
            )
        if meta["destination"] not in PROPOSAL_DEST:
            errors.append(
                f"{rel}: destination '{meta['destination']}' must be one of {sorted(PROPOSAL_DEST)}."
            )
        created, review = _date(meta["created"]), _date(meta["review_by"])
        if not created or not review:
            errors.append(f"{rel}: 'created' and 'review_by' must be YYYY-MM-DD.")
            continue
        if meta["status"] == "rejected" and not meta.get("reason"):
            errors.append(
                f"{rel}: rejected proposals need a 'reason' so the rule is not proposed again."
            )
        if meta["status"] == "pending" and (today - created).days > MAX_PENDING_DAYS:
            errors.append(
                f"{rel}: pending for {(today - created).days} days (max {MAX_PENDING_DAYS}). Apply it or reject it with a reason."
            )
        if meta["status"] == "applied" and review < today:
            errors.append(
                f"{rel}: applied rule passed its review-by date {review}. Re-justify it with evidence, or remove it."
            )


def _lint_hooks(root, errors):
    d = root / ".github" / "hooks"
    if not d.is_dir():
        return
    for f in sorted(d.glob("*.json")):
        rel = f.relative_to(root)
        try:
            cfg = json.loads(f.read_text())
        except ValueError:
            errors.append(f"{rel}: invalid JSON. Fix the syntax.")
            continue
        if cfg.get("version") != 1:
            errors.append(f"{rel}: 'version' must be 1.")
        for event, entries in (cfg.get("hooks") or {}).items():
            for e in entries:
                cmd = " ".join(
                    str(e.get(k, "")) for k in ("command", "bash", "powershell")
                )
                for path in sorted(set(re.findall(r"\.github/[^\s\"']+\.py", cmd))):
                    if not (root / path).exists():
                        errors.append(
                            f"{rel}: '{event}' runs missing script {path}. Fix the path or delete the hook."
                        )


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--root", default=".")
    a = p.parse_args()
    errors, warnings = lint(a.root)
    for w in warnings:
        print("WARN ", w)
    for e in errors:
        print("ERROR", e)
    print(f"{len(errors)} error(s), {len(warnings)} warning(s)")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
