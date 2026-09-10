# Skill format

A Buildrix Skill is **a valid Agent Skill first**. It must work unchanged when
dropped into `~/.claude/skills/`, a Codex skills directory, or any other host
that follows the open Agent Skills convention.

## Layout

```
my-skill/
├── skill.yaml       Buildrix metadata and technical requirements
├── SKILL.md         the agent-facing Skill itself
├── scripts/         optional — code the agent runs
├── references/      optional — long-form docs, loaded on demand
├── examples/        optional — worked examples
├── assets/          optional — templates, lookup tables, small data
└── tests/           optional — runnable checks
```

Nothing is required beyond `skill.yaml` and `SKILL.md`. A Skill may be pure
instruction, or may ship scripts, models, references, decision logic, validation
procedures and error recovery. Keep the format light: very different
building-engineering Skills have to fit in it.

## Where metadata lives

Exactly one place each, so nothing can drift:

- **SKILL.md frontmatter** — only the open Agent Skills fields: `name`,
  `description`, `license`, optionally `allowed-tools`. This is all a
  non-Buildrix host reads.
- **skill.yaml** — everything Buildrix-specific: `schema`, `version`, `domain`,
  `tags`, `authors`, `determinism`, `requires` (python, packages,
  external_tools, gpu), `network`, `provenance`.

`name` is the one field in both, and validation fails if they disagree.

A legacy package with Buildrix fields under frontmatter `metadata:` and no
`skill.yaml` is still read; submitting through Buildrix writes the canonical
`skill.yaml`.

## SKILL.md sections

In this order. The first three are required.

```markdown
## Purpose                            what capability this gives an agent
## When to Use                        the phrases a user would actually type
## Workflow                           numbered steps, each with its command
## Decision Guidance                  the judgement calls, with thresholds
## Validation                         how the agent checks its own result
## Common Failure Modes / Recovery    what breaks, and what to do
## Included Resources                 the bundled files, by relative path
```

`When to Use` is the highest-leverage section. Most Skills fail because an agent
never loads them, and vague trigger wording is why.

## What validation enforces

- `name` is kebab-case and matches between the two files
- `description` exists and says both what it does and when to use it
- `domain` is one of the eight, or `general`
- the three required sections are present
- SKILL.md is under ~5000 tokens — longer material goes to `references/`
- no credentials anywhere; no absolute paths (use `{skill_dir}`)
- the package is under 25 MB
- referenced bundled files actually exist

## The reusability check

The hub also judges whether the Skill is *reusable* or is one Task's answer
written out longhand:

- `reusable` — would work on the next case unchanged
- `task_specific` — sound method, written for exactly one building or dataset;
  a warning, not a blocker
- `hardcoded_answer` — contains what looks like a benchmark result, an expected
  output value, or a conclusion that could only come from having solved a
  specific Task. **This blocks submission.**

The fix is always to generalise the content, never to reword around the check.
