#!/usr/bin/env python3
"""Cache of VERIFIED commands plus pointers to authoritative config. Stdlib only.

Deliberately does not store paraphrased style rules: the repo's own config files
(.clang-format, CODING_STANDARDS.md, ...) are the source of truth; we store pointers.
Staleness is decided by content hashes of source files, not by a calendar timer.
  check            -> FRESH (exit 0) | STALE/MISSING (exit 1)
  write  < json    -> {"sources": [paths], "gates": [{"name","command","verified"}], "pointers": {}, "unknown": []}
"""
import argparse
import datetime
import hashlib
import json
import sys
from pathlib import Path


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def cache_path(root):
    return Path(root) / ".github" / "cache" / "standards.json"


def check(root):
    cp = cache_path(root)
    if not cp.exists():
        return "MISSING", ["no cache; run the standards-discoverer"]
    data = json.loads(cp.read_text())
    reasons = []
    for rel, h in data.get("sources", {}).items():
        f = Path(root) / rel
        if not f.exists():
            reasons.append(f"{rel}: deleted")
        elif sha(f) != h:
            reasons.append(f"{rel}: changed")
    reasons += [f"gate '{g['name']}' unverified" for g in data.get("gates", []) if not g.get("verified")]
    return ("STALE" if reasons else "FRESH"), reasons


def write(root, payload):
    for key in ("sources", "gates"):
        if key not in payload:
            raise SystemExit(f"missing '{key}' in input JSON")
    for g in payload["gates"]:
        if not (isinstance(g.get("name"), str) and isinstance(g.get("command"), str)):
            raise SystemExit("each gate needs string 'name' and 'command'")
    missing = [s for s in payload["sources"] if not (Path(root) / s).exists()]
    if missing:
        raise SystemExit(f"source files not found: {missing}. Only list files you actually read.")
    out = {"version": 1,
           "generated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
           "sources": {s: sha(Path(root) / s) for s in payload["sources"]},
           "gates": payload["gates"], "pointers": payload.get("pointers", {}), "unknown": payload.get("unknown", [])}
    cp = cache_path(root)
    cp.parent.mkdir(parents=True, exist_ok=True)
    cp.write_text(json.dumps(out, indent=2))
    return out


def main():
    p = argparse.ArgumentParser()
    p.add_argument("cmd", choices=["check", "write"])
    p.add_argument("--root", default=".")
    a = p.parse_args()
    if a.cmd == "check":
        state, reasons = check(a.root)
        print(state, *reasons, sep="\n  " if reasons else "")
        return 0 if state == "FRESH" else 1
    write(a.root, json.load(sys.stdin))
    print("cache written")
    return 0


if __name__ == "__main__":
    sys.exit(main())
