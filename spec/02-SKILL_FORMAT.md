# Skill package contract — `skill/2.0`

## Principle

**A Buildrix skill is a valid Agent Skill first, and a Buildrix skill second.** It must
work unchanged when dropped into `~/.claude/skills/`, an OpenAI Codex skills directory,
or any other host that follows the open Agent Skills convention. Everything Buildrix
needs beyond the open standard lives inside the frontmatter's `metadata:` map, which
every host is required to ignore. We never invent a top-level key.

That single rule is what makes "everyone submits exactly the same format" achievable:
the format is not ours, we only constrain it.

## Directory layout

```
skill-name/
├── SKILL.md            REQUIRED  frontmatter + instructions
├── requirements.txt    if scripts import anything outside the stdlib
├── scripts/            executable code the agent runs
├── references/         long-form docs, loaded on demand (progressive disclosure)
├── assets/             templates, lookup tables, small data
├── tests/              runnable checks; `buildrix skill check` executes them
└── NOTES.md            optional running log of agent errors and fixes
```

Nothing else at the top level. No `config.yaml` — the v1 template's parallel metadata
file is dropped, because two sources of metadata always drift.

## Frontmatter

```yaml
---
# ---- open Agent Skills standard: portable, understood by every host ----
name: weather-data-extraction
description: >-
  Extracts and analyses historical weather data for building-science work — dry-bulb
  temperature, humidity, GHI/DNI/DHI, wind — for any location worldwide. Use when a task
  needs site-specific meteorological input for energy simulation, HVAC sizing, solar
  assessment, or climate analysis. No API key required.
license: Apache-2.0
allowed-tools: [Bash, Read, Write]        # optional; omit to allow the host default

# ---- everything below is Buildrix-only and ignorable by hosts ----
metadata:
  buildrix_schema: "skill/2.0"
  version: "1.2.0"                        # semver; bump on every published change
  domain: performance-modeling            # closed enum, see 01-TAXONOMY.md
  tags: [weather, solar, tmy, open-meteo]
  authors:
    - name: Jane Doe
      affiliation: Syracuse University
      orcid: 0000-0002-1825-0097
      github: janedoe
  requires:
    python: ">=3.11,<3.14"
    packages: ["requests==2.32.3", "pandas==2.2.2"]
    external_tools:
      - {name: EnergyPlus, version: "24.2.0", provisioning: managed}   # managed|user|none
  network:                                # declared egress. [] means fully offline
    - archive-api.open-meteo.com
  determinism: deterministic              # deterministic | seeded | stochastic
  context_cost_tokens: 1180               # measured by `buildrix skill check`, not claimed
  provenance:
    derived_from: []                      # skills or papers this builds on
    data_licenses: ["Open-Meteo: CC-BY-4.0"]
---
```

### Field rules

- **`name`** — kebab-case, ≤ 64 chars, must equal the directory name, unique in the
  registry. Namespacing is by author on the hub, not in the name.
- **`description`** — 40–1024 chars, third person, and must contain **both** *what it
  does* and *when to use it*. This string is the only thing most agents see at
  discovery time; a vague description is the single most common cause of a skill
  never firing. The validator rejects descriptions with no trigger nouns, and the
  reviewer scores it explicitly.
- **`domain`** — exactly one of the 8 (or `general` for cross-cutting tooling).
  Multi-domain skills pick the primary one and put the rest in `tags`.
- **`determinism`** — `deterministic` is asserted, then *checked*: the validator runs
  `tests/` twice and diffs the outputs.
- **`context_cost_tokens`** — measured, written back by the validator. It matters:
  a skill that costs 20k tokens of context has to earn it, and the leaderboard reports
  gain per 1k tokens of skill context alongside raw gain.

## Body structure

Required H2 sections, in this order. The renderer and the reviewer both rely on them:

```markdown
## Overview            what it does, 2–3 sentences
## When to use         concrete trigger phrases a user would actually say
## Inputs              what the agent must collect before running
## Workflow            numbered steps with runnable code
## Outputs             exact files produced, with paths and formats
## Examples            ≥1 verbatim user prompt → what happens
## Limitations         what it cannot do, accuracy bounds, when to use something else
```

Optional: `## Data sources`, `## References`, `## Troubleshooting`.

## Hard rules the validator enforces

| # | Rule | Why |
|---|---|---|
| 1 | `SKILL.md` body ≤ 5 000 tokens | Progressive disclosure. Overflow goes to `references/` and gets linked, not pasted. |
| 2 | No absolute paths; the skill root is referenced as `{skill_dir}` | Portability across hosts and OSes. |
| 3 | No credentials, tokens, or keys; secret-scan on every file | Public registry. |
| 4 | Network egress limited to declared hosts | The benchmark runner enforces this at runtime; undeclared egress fails the run. |
| 5 | **No task leakage** — no file may contain a task's reference outputs | A skill that memorises answers would make the whole benchmark meaningless. Enforced by hashing every skill file against the hidden reference index, plus rejecting `*expected_output*` / `*reference*` payload files. |
| 6 | `tests/` must exist and pass | A skill nobody can run is not a skill. |
| 7 | Packed size ≤ 25 MB | Big data belongs behind a declared `network` host or in a task's `inputs/`. |
| 8 | Declared `determinism` verified by double-run | Stops silent stochasticity from polluting paired runs. |

## Two stages, same as a task

A skill submission goes through the mechanical rules above, then the **reviewer**, which
runs on the server. It reads the description and the limits, because those are the two
things that decide whether an agent finds the skill and whether it misuses it:

| Reviewer dimension | The question it asks |
|---|---|
| `description_triggers` | Does the description say *when* to use it, not only what it does? Would the words a user actually types match it? |
| `workflow_runnable` | Are the steps numbered, with the command or call for each one? |
| `outputs_declared` | Are the written files named exactly, so a task can depend on them? |
| `limits_specific` | Are the bounds real numbers, not "needs enough data"? |
| `provenance_honest` | Is the method attributed, and are the accuracy claims defensible? |

Verdicts use the same vocabulary as tasks — `pass` / `concern` / `blocker`, rolled up to
`accepted` / `minor_revision` / `major_revision` / `rejected` — and the comments come back
identically in the browser and in the terminal.

## Commands

Same verbs for skills and tasks, so there is nothing extra to remember:

```bash
buildrix skill new <name>         # scaffold the layout
buildrix skill check <dir>        # all 8 rules + token cost + test double-run (local)
buildrix skill submit <dir>       # upload, then print the checks and the review
buildrix skill status <name>      # current verdict, round, and what is still missing
buildrix skill install <name>     # fetch + link into the host's skills directory
buildrix skill install <name> --format codex|claude|gemini|plain
buildrix skill list | remove <name>
```

`check` runs the same code path the server runs on upload, so nothing is rejected only
after submitting. `submit` and `status` are the only commands that need the network.
