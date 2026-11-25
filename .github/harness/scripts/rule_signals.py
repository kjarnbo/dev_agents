#!/usr/bin/env python3
"""Deterministic first pass: does this text look like a durable rule? Stdlib only.

This is a cheap heuristic, not a judge. It exists so detection does not depend on an agent
remembering to look, and so the rule-curator gets an objective second opinion.
  scan "<text>" | scan -     classify text, print JSON
  --hook                     UserPromptSubmit hook: read payload on stdin, log candidates, never fail, print nothing
  list                       unreviewed candidates (JSON)
  mark ID [ID...]            mark candidates as reviewed (the hook will not log them again)
Logs live in .github/cache/ (git-ignored). Only rule-like sentences are stored, never whole prompts.
"""

import argparse
import datetime
import hashlib
import json
import os
import re
import sys
from pathlib import Path

GENERAL = {
    "always": r"\balways\b",
    "never": r"\bnever\b",
    "from_now_on": r"\b(from now on|going forward|from here on|in the future)\b",
    "project_scope": r"\b(in|for|across) (this|our|the) (project|repo|repository|codebase|team|org)\b",
    "we_statement": r"\bwe (always|never|usually|must|prefer|use|don'?t|do not)\b",
    "by_default": r"\bby default\b",
    "every_time": r"\b(every time|whenever|each time)\b",
    "dont_ever": r"\b(don'?t|do not)\b.*\bever\b",
    "universal_scope": r"\b(everywhere|every (function|file|module|class|commit|pr|change)|all (files|modules|functions|code|commits))\b",
    "no_exceptions": r"\bno exceptions\b",
    "corrective": r"\bstop (adding|using|doing|writing|making)\b",
    "convention": r"\b(convention|guideline|standard|policy|house rule)\b",
    "prefer_over": r"\bprefer\b.+\bover\b",
    "remember": r"\bremember (to|that)\b",
}
ONE_OFF = {
    "this_time": r"\b(this time|just this once|just for now|for now)\b",
    "scoped_here": r"\b(for|in|only in|just in) this (task|pr|change|file|function|commit|branch|case|one|class)\b",
    "temporal": r"\b(right now|today|temporarily|at the moment)\b",
}
GENERAL = {k: re.compile(v, re.IGNORECASE) for k, v in GENERAL.items()}
ONE_OFF = {k: re.compile(v, re.IGNORECASE) for k, v in ONE_OFF.items()}
MIN_LEN, MAX_LEN = 12, 300


def _score(sentence):
    g = [n for n, p in GENERAL.items() if p.search(sentence)]
    o = [n for n, p in ONE_OFF.items() if p.search(sentence)]
    score = len(g) - 2 * len(o)
    if sentence.endswith("?"):
        score = min(score, 0)  # a question asks about a rule; it does not state one
    return score, g, o


def classify(text):
    """Best sentence wins. Labels: rule (>=2), likely_rule (1), one_off, none."""
    best = None
    for s in (x.strip() for x in re.split(r"(?<=[.!?])\s+|\n+", text or "")):
        if not (MIN_LEN <= len(s) <= MAX_LEN):
            continue
        sc, g, o = _score(s)
        if best is None or sc > best["score"]:
            best = {"score": sc, "general": g, "one_off": o, "statement": s}
    if best is None:
        return {
            "label": "none",
            "score": 0,
            "general": [],
            "one_off": [],
            "statement": "",
        }
    label = (
        "rule"
        if best["score"] >= 2
        else "likely_rule"
        if best["score"] == 1
        else "one_off"
        if best["one_off"]
        else "none"
    )
    return {"label": label, **best}


def find_root(start):
    p = Path(start).resolve()
    for d in [p, *p.parents]:
        if (d / ".github").is_dir():
            return d
    return p


def _paths(root):
    c = Path(root) / ".github" / "cache"
    return c, c / "rule-candidates.jsonl", c / "rule-candidates.reviewed"


def cid(statement):
    return hashlib.sha1(statement.lower().encode()).hexdigest()[:10]


def _reviewed(root):
    f = _paths(root)[2]
    return set(f.read_text().split()) if f.exists() else set()


def _entries(root):
    f = _paths(root)[1]
    return (
        [json.loads(x) for x in f.read_text().splitlines() if x.strip()]
        if f.exists()
        else []
    )


def log_candidate(root, text):
    r = classify(text)
    if r["label"] not in ("rule", "likely_rule"):
        return None
    i = cid(r["statement"])
    if i in _reviewed(root) or i in {e["id"] for e in _entries(root)[-20:]}:
        return None
    cache, f, _ = _paths(root)
    cache.mkdir(parents=True, exist_ok=True)
    entry = {
        "id": i,
        "ts": datetime.datetime.now(datetime.UTC).isoformat(timespec="seconds"),
        "label": r["label"],
        "score": r["score"],
        "signals": r["general"],
        "statement": r["statement"],
    }
    with f.open("a") as fh:
        fh.write(json.dumps(entry) + "\n")
    return entry


def hook():
    try:
        data = json.loads(sys.stdin.read() or "{}")
        prompt = data.get("prompt") or ""
        log_candidate(find_root(data.get("cwd") or os.getcwd()), prompt)
    except Exception:
        pass
    return 0


def main():
    if "--hook" in sys.argv:
        return hook()
    p = argparse.ArgumentParser()
    p.add_argument("cmd", choices=["scan", "list", "mark"])
    p.add_argument("args", nargs="*")
    p.add_argument("--root")
    a = p.parse_args()
    root = Path(a.root) if a.root else find_root(os.getcwd())
    if a.cmd == "scan":
        text = sys.stdin.read() if a.args == ["-"] else " ".join(a.args)
        print(json.dumps(classify(text), indent=2))
    elif a.cmd == "list":
        done = _reviewed(root)
        print(json.dumps([e for e in _entries(root) if e["id"] not in done], indent=2))
    else:
        cache, _, rf = _paths(root)
        cache.mkdir(parents=True, exist_ok=True)
        with rf.open("a") as fh:
            fh.write("\n".join(a.args) + "\n")
        print(f"marked {len(a.args)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
