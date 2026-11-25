#!/usr/bin/env python3
"""Run verification gates in order, fail fast, report scoped claims. Stdlib only.

Gates come from .github/harness/gates.json (human-owned, wins) or from the verified
gates in .github/cache/standards.json. Context-safe output: each gate's FULL output is saved to .github/cache/gate-logs/<name>.log;
the report carries only the last 40 lines plus up to 10 error-looking lines (build errors often scroll
off the tail). To dig deeper, grep the saved log; never paste it whole.
  --baseline   run all gates on the untouched tree and record which already fail
Exit: 0 no NEW failure, 1 new failure, 2 no gates configured.
"""

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

TAIL = 40
MAX_ERROR_LINES = 10
ERR = re.compile(r"\b(error|fatal|failed|failure)\b", re.IGNORECASE)


def load_gates(root):
    human = root / ".github" / "harness" / "gates.json"
    if human.exists():
        return json.loads(human.read_text())
    cache = root / ".github" / "cache" / "standards.json"
    if cache.exists():
        return [
            g
            for g in json.loads(cache.read_text()).get("gates", [])
            if g.get("verified")
        ]
    return []


def run(gate, root, timeout):
    try:
        r = subprocess.run(
            gate["command"],
            shell=True,
            cwd=root / gate.get("cwd", "."),
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        out, rc = (r.stdout + r.stderr), r.returncode
    except subprocess.TimeoutExpired:
        out, rc = f"TIMEOUT after {timeout}s", 124
    return rc, out.strip()


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--root", default=".")
    p.add_argument("--baseline", action="store_true")
    p.add_argument("--timeout", type=int, default=900)
    a = p.parse_args()
    root = Path(a.root).resolve()
    gates = load_gates(root)
    if not gates:
        print(
            "No gates configured. Run the standards-discoverer agent, or create .github/harness/gates.json "
            'as [{"name": "build", "command": "..."}] ordered fastest first.'
        )
        return 2
    cache = root / ".github" / "cache"
    cache.mkdir(parents=True, exist_ok=True)
    bfile = cache / "baseline.json"
    baseline = (
        json.loads(bfile.read_text()) if bfile.exists() and not a.baseline else {}
    )
    results, not_run, stop = [], [], False
    for g in gates:
        if stop:
            not_run.append(g["name"])
            continue
        rc, full = run(g, root, a.timeout)
        lines = full.splitlines()
        logdir = cache / "gate-logs"
        logdir.mkdir(parents=True, exist_ok=True)
        logfile = logdir / (re.sub(r"[^A-Za-z0-9_.-]", "_", g["name"]) + ".log")
        logfile.write_text(full)
        if rc == 0:
            status = "passed"
        elif baseline.get(g["name"], 0) != 0:
            status = "failed_preexisting"
        else:
            status = "failed"
        results.append(
            {
                "gate": g["name"],
                "command": g["command"],
                "exit_code": rc,
                "status": status,
                "output_tail": "\n".join(lines[-TAIL:]) if rc else "",
                "error_lines": [x for x in lines if ERR.search(x)][:MAX_ERROR_LINES]
                if rc
                else [],
                "log": logfile.relative_to(root).as_posix(),
            }
        )
        if status == "failed" and not a.baseline:
            stop = True
    if a.baseline:
        bfile.write_text(
            json.dumps({r["gate"]: r["exit_code"] for r in results}, indent=2)
        )
    claims = [f"{r['gate']}: {r['status'].replace('_', ' ')}" for r in results] + [
        f"{n}: NOT RUN" for n in not_run
    ]
    report = {
        "baseline_recorded": a.baseline,
        "results": results,
        "not_run": not_run,
        "claims": claims,
    }
    (cache / "last_verify.json").write_text(json.dumps(report, indent=2))
    print(json.dumps(report, indent=2))
    return 1 if any(r["status"] == "failed" for r in results) and not a.baseline else 0


if __name__ == "__main__":
    sys.exit(main())
