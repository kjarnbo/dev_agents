"""Minimal YAML-frontmatter reader (stdlib only). Handles scalars, inline lists, block lists."""

import re


def _val(v):
    v = v.strip()
    if v.startswith("[") and v.endswith("]"):
        return [x.strip().strip("'\"") for x in v[1:-1].split(",") if x.strip()]
    return v.strip("'\"")


def parse(text):
    """Return (frontmatter dict, body str). Raw block text is kept under '_raw_<key>'."""
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}, text
    end = next((i for i in range(1, len(lines)) if lines[i].strip() == "---"), None)
    if end is None:
        return {}, text
    fm, key = {}, None
    for ln in lines[1:end]:
        m = re.match(r"^([A-Za-z0-9_-]+):\s*(.*)$", ln)
        if m and not ln.startswith((" ", "\t")):
            key = m.group(1)
            fm[key] = _val(m.group(2))
            fm["_raw_" + key] = ln
        elif key is not None:
            fm["_raw_" + key] += "\n" + ln
            item = re.match(r"^\s+-\s+(.*)$", ln)
            if item:
                if fm[key] == "":
                    fm[key] = []
                if isinstance(fm[key], list):
                    fm[key].append(item.group(1).strip().strip("'\""))
    return fm, "\n".join(lines[end + 1 :])
