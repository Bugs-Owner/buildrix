---
name: error
description: >-
  Self-improvement protocol for Buildrix skills. Before using any skill,
  check its NOTES.md for known issues. After fixing an error, log it.
  After accumulating enough lessons, update the skill's actual code or
  SKILL.md to fix the root cause, then mark the note as resolved.
---

# Error Notebook Protocol

## Phase 1: Check Before Using

Before using any skill, check if its directory has a `NOTES.md`.
If yes, read it — apply known fixes proactively.

## Phase 2: Log When Errors Happen

After encountering and resolving an error, append to that skill's
`NOTES.md` (create the file if it doesn't exist):

```
## [DATE] — [SHORT TITLE]
- **Status:** open
- **Error:** what went wrong
- **Root cause:** why
- **Fix applied:** what you did this time
- **Suggested code fix:** what should change in the skill to prevent this permanently
```

## Phase 3: Fix the Skill

When a note has a clear `Suggested code fix`, and the user asks to
improve the skill (or after seeing the same error pattern multiple times):

1. Update the skill's script to fix the root cause
2. Update the SKILL.md if instructions were misleading
3. Change the note's status from `open` to `resolved`:

```
- **Status:** resolved (v0.2.0) — [describe what was changed]
```

## Phase 4: Clean Up

Resolved notes are kept for history but cost minimal tokens.
The agent can summarize old resolved entries into a single line
if NOTES.md grows beyond ~30 entries.

## Key Principle

The goal is not to maintain a growing log — it's to make the
log unnecessary by fixing the underlying skills. Every open note
is a skill improvement waiting to happen.
