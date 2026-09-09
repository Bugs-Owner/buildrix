---
# ─── portable core: read by Claude Code, Codex, and any Agent Skills host ───
name: your-skill-name
description: >-
  [What it does, in one or two sentences.] Use when [the situation that should
  trigger it — write the words a user would actually type]. This paragraph is
  all an agent sees before deciding whether to load the skill, so write it for
  that reader. 40–1024 characters.
license: Apache-2.0
# allowed-tools: [Bash, Read, Write]        # optional; omit for the host default

# ─── Buildrix block: ignored by hosts, required by the registry ─────────────
metadata:
  buildrix_schema: "skill/2.0"
  version: "0.1.0"
  domain: performance-modeling      # one of the eight — `buildrix domains`
  tags: []                          # free text, e.g. [mpc, chiller, ashrae-140]
  authors:
    - name: "[Your Name]"
      affiliation: ""
      orcid: ""
      github: ""
  requires:
    python: ">=3.11,<3.14"
    packages: []                    # pinned, e.g. ["pandas==2.2.2"]
    external_tools: []              # e.g. [{name: EnergyPlus, version: "24.2.0"}]
  network: []                       # every host you contact; [] means offline
  determinism: deterministic        # deterministic | seeded | stochastic
  provenance:
    derived_from: []
    data_licenses: []
---

# Your Skill Name

## Overview

Two or three sentences: what this does, and why it matters for building work.

## When to use

Concrete triggers, in the words a user would say:

- "..."
- "..."

Do not use this for [the neighbouring case that belongs to a different skill].

## Inputs

What the agent has to collect before running anything.

| Input | Form | Notes |
|---|---|---|
| ... | CSV, 15-minute or finer | columns: ... |

## Workflow

1. **Prepare the data.**
   ```bash
   python {skill_dir}/scripts/main.py prepare --input <path> --out clean.csv
   ```
2. **Run the main step.**
   ```bash
   python {skill_dir}/scripts/main.py run --data clean.csv --out outputs/
   ```
3. **Check the result** against the bounds in Limits below before reporting it.

`{skill_dir}` is the folder this file is in. Never write an absolute path.

## Outputs

- `outputs/result.csv` — ...
- `outputs/report.md` — ...

## Examples

**"[an exact user prompt]"**

The agent collects [inputs], runs step 2, and reports [what].

## Limits

- Real bounds, with numbers. "Needs enough data" is not a bound; "needs four
  weeks at 15-minute resolution" is.
- What this cannot do, and which skill to reach for instead.
- Where the method comes from, and how accurate it is.
