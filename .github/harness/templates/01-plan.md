---
base: main
allowed_files:
  - path/to/file.c
  - tests/**
---
# Plan: <title>
Brief: 00-brief.md

## Step 1: <title>
- **File**: `path/to/file.c`
- **Anchor**: `<unique existing text or symbol>` (never a line number)
- **Change**: <insert after / replace / delete>
```c
<exact code for new or changed logic>
```
- **Check**: `<command>` expects `<result>`  (covers AC1)
- **Commit**: `step 1: <title>`

## Risks
- <risk and mitigation>
