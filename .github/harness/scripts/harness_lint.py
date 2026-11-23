#!/usr/bin/env python3
"""Mechanical checks for the harness itself. Stdlib only. Exit 1 on errors.

Every message says how to fix the problem, because the reader is usually an agent.
"""
import argparse
import datetime
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import fm  # noqa: E402

MAX_AGENTS_MD_LINES = 100
MAX_AGENT_BODY_LINES = 90
MAX_HOPS = 4
READ_ONLY = {"explorer", "reviewer", "standards-discoverer", "ask"}
NO_EXECUTE = {"explorer", "ask"}  # roles that must not run commands at all
MAX_PENDING_DAYS = 30
PROPOSAL_STATUS = {"pending", "applied", "rejected"}
PROPOSAL_DEST = {"project-rule", "agent-behavior", "enforced-control"}
PROPOSAL_REQUIRED = ("status", "created", "destination", "statement", "why", "review_by")


def _agent_files(root):
    d = root / ".github" / "agents"
    return sorted(d.glob("*.agent.md")) if d.is_dir() else []


def _longest_path(graph, node, seen=()):
    best = 0
    for nxt in graph.get(node, ()):
        if nxt in seen:
            continue
        best = max(best, 1 + _longest_path(graph, nxt, seen + (node,)))
    return best


def lint(root, today=None):
    root, today = Path(root), today or datetime.date.today()
    errors, warnings = [], []
    agents, graph = {}, {}

    for f in (root / ".github" / "agents").rglob("*.md") if (root / ".github" / "agents").is_dir() else []:
        if f.parent.name != "agents":
            errors.append(f"{f.relative_to(root)}: nested agent file. Move it to .github/agents/ (flat layout).")

    for f in _agent_files(root):
        meta, body = fm.parse(f.read_text())
        name = meta.get("name") or f.name[: -len(".agent.md")]
        rel = f.relative_to(root)
        agents[name] = meta
        if not meta.get("description"):
            errors.append(f"{rel}: missing 'description'. Add one sentence saying when to use this agent.")
        tools = meta.get("tools")
        if not isinstance(tools, list) or not tools:
            errors.append(f"{rel}: 'tools' must be an explicit non-empty list. Omitting it grants every tool.")
        elif "*" in tools:
            errors.append(f"{rel}: 'tools' contains '*'. List only the tools this role needs.")
        elif name in READ_ONLY and "edit" in tools:
            errors.append(f"{rel}: read-only role '{name}' has the 'edit' tool. Remove 'edit' from tools.")
        if isinstance(tools, list) and name in NO_EXECUTE and "execute" in tools:
            errors.append(f"{rel}: role '{name}' must not run commands but has the 'execute' tool. Remove 'execute' from tools.")
        if "agents" not in meta:
            errors.append(f"{rel}: 'agents' is not set. Add 'agents: []' (or list allowed subagents) so subagent use is explicit.")
        subs = meta.get("agents") if isinstance(meta.get("agents"), list) else []
        if subs and isinstance(tools, list) and "agent" not in tools:
            errors.append(f"{rel}: lists subagents but 'tools' lacks 'agent'. Add 'agent' to tools.")
        if "model" in meta:
            warnings.append(f"{rel}: pins model '{meta['model']}'. Pinned names go stale; remove it unless an eval justifies it.")
        n = len(body.splitlines())
        if n > MAX_AGENT_BODY_LINES:
            errors.append(f"{rel}: body is {n} lines (max {MAX_AGENT_BODY_LINES}). Move reference material to .github/harness/templates/ and link it.")
        targets = re.findall(r"^\s+agent:\s*(\S+)", meta.get("_raw_handoffs", ""), re.M)
        graph[name] = list(dict.fromkeys(targets + subs))

    for name, outs in graph.items():
        for t in outs:
            if t not in agents:
                errors.append(f"agent '{name}' references unknown agent '{t}'. Fix the name or create .github/agents/{t}.agent.md.")
    for name in graph:
        hops = _longest_path(graph, name)
        if hops > MAX_HOPS:
            errors.append(f"agent '{name}' starts a chain of {hops} hops (max {MAX_HOPS}). Merge roles; long handoff chains fail in practice.")

    am = root / "AGENTS.md"
    if not am.exists():
        errors.append("AGENTS.md missing. Create a map of at most 100 lines that links to deeper docs.")
    else:
        n = len(am.read_text().splitlines())
        if n > MAX_AGENTS_MD_LINES:
            errors.append(f"AGENTS.md is {n} lines (max {MAX_AGENTS_MD_LINES}). Keep it a table of contents; move detail into linked files.")

    cf = root / ".github" / "harness" / "CONTROLS.md"
    if not cf.exists():
        errors.append(".github/harness/CONTROLS.md missing. Record each control, the reason it exists, and a review-by date.")
    else:
        rows = [r for r in cf.read_text().splitlines() if r.startswith("|") and not re.match(r"^\|[\s:-]+\|", r)][1:]
        if not rows:
            errors.append("CONTROLS.md has no rows. Add a table: Control | Why | Enforcement | Review by.")
        for r in rows:
            cells = [c.strip() for c in r.strip("|").split("|")]
            if len(cells) < 4 or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", cells[3]):
                errors.append(f"CONTROLS.md row '{cells[0][:40]}': needs 4 cells ending in a YYYY-MM-DD review-by date.")
            elif datetime.date.fromisoformat(cells[3]) < today:
                errors.append(f"CONTROLS.md control '{cells[0][:40]}' passed its review-by date {cells[3]}. Re-justify it with evidence, or delete it.")
    _lint_proposals(root, today, errors)
    _lint_hooks(root, errors)
    return errors, warnings


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
        missing = [k for k in PROPOSAL_REQUIRED if not meta.get(k)]
        if missing:
            errors.append(f"{rel}: missing frontmatter {missing}. Copy .github/harness/templates/04-rule-proposal.md.")
            continue
        if meta["status"] not in PROPOSAL_STATUS:
            errors.append(f"{rel}: status '{meta['status']}' must be one of {sorted(PROPOSAL_STATUS)}.")
        if meta["destination"] not in PROPOSAL_DEST:
            errors.append(f"{rel}: destination '{meta['destination']}' must be one of {sorted(PROPOSAL_DEST)}.")
        created, review = _date(meta["created"]), _date(meta["review_by"])
        if not created or not review:
            errors.append(f"{rel}: 'created' and 'review_by' must be YYYY-MM-DD.")
            continue
        if meta["status"] == "rejected" and not meta.get("reason"):
            errors.append(f"{rel}: rejected proposals need a 'reason' so the rule is not proposed again.")
        if meta["status"] == "pending" and (today - created).days > MAX_PENDING_DAYS:
            errors.append(f"{rel}: pending for {(today - created).days} days (max {MAX_PENDING_DAYS}). Apply it or reject it with a reason.")
        if meta["status"] == "applied" and review < today:
            errors.append(f"{rel}: applied rule passed its review-by date {review}. Re-justify it with evidence, or remove it.")


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
                cmd = " ".join(str(e.get(k, "")) for k in ("bash", "powershell"))
                for path in sorted(set(re.findall(r"\.github/[^\s\"']+\.py", cmd))):
                    if not (root / path).exists():
                        errors.append(f"{rel}: '{event}' runs missing script {path}. Fix the path or delete the hook.")


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
