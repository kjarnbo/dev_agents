---
name: standards-discoverer
description: Finds the project's verified build/test/lint commands and points at its authoritative style config. Caches the result with source hashes.
tools: ['search', 'read', 'execute']
agents: []
user-invocable: false
---

# Standards discoverer

## Steps
1. `python .github/harness/scripts/standards_cache.py check`. If FRESH, return the cached summary and stop.
2. Find sources (read only what exists): `AGENTS.md`, `README.md`, `CONTRIBUTING.md`, build files
   (`Makefile`, `CMakeLists.txt`, `package.json`, ...), CI config (`.github/workflows/`), `.clang-format`,
   `.clang-tidy`, `.editorconfig`, a coding-standards document.
3. Extract **commands**: build, test, lint/static-analysis. Prefer what CI runs, since CI is proven.
4. **Verify each command** by running it once. Mark `verified: true` only if it exited 0. Order gates fastest first.
5. Record **pointers**, not paraphrases: `{"formatting": ".clang-format", "style_guide": "CODING_STANDARDS.md"}`.
   The repo's own files are the source of truth; a summary of them can drift or mislead.
6. Write the cache: pipe JSON to `python .github/harness/scripts/standards_cache.py write`
   with keys `sources` (files you read), `gates`, `pointers`, `unknown`.

## Rules
- Never invent a command or a standard. Put anything you could not find in `unknown`, and return questions for the user.
- Output to the caller: the gates (with verified flags), the pointers, and `unknown`. Max 30 lines.
