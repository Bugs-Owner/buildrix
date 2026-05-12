# Contributing to Buildrix

This guide walks you through contributing a new skill, using the
**heat wave identification** skill as a real example.

---

## Setup (one time)

```bash
# 1. Clone the repo
git clone https://github.com/Bugs-Owner/buildrix.git
cd buildrix

# 2. Install the package (makes the `buildrix` CLI available)
pip install -e .

# 3. Login to the hub (create an account if needed)
buildrix config hub https://buildrixhub.onrender.com
buildrix login --register

# 4. Verify
buildrix whoami
buildrix info
```

---

## Contributing a Skill

### Step 1: Scaffold

```bash
buildrix new skill heat-wave-identification
```

This creates:
```
heat-wave-identification/
├── SKILL.md          # ← Edit this: metadata + instructions
├── config.yaml       # ← Fill in metadata
├── scripts/main.py   # ← Put your code here
├── tests/            # ← Add tests
├── references/       # ← Optional: docs, papers
└── assets/           # ← Optional: images, templates
```

### Step 2: Write the SKILL.md

The SKILL.md follows the [Agent Skills open standard](https://agentskills.io).
The YAML frontmatter at the top is what the agent sees first:

```yaml
---
name: heat-wave-identification
description: >-
  Identify and analyze heat wave periods from weather data for building
  performance assessment. Use when the user needs to find extreme heat
  events or assess cooling load implications.
license: Apache-2.0
metadata:
  author: your-name
  version: "0.1.0"
  domain: energy-modeling
  tags: [heat-wave, extreme-weather, cooling]
  depends_on: [weather-data-extraction]
---
```

Key things in the frontmatter:
- `description` — the agent reads this to decide when to activate your skill.
  Include keywords users are likely to say.
- `metadata.domain` — must match the hub's domain categories.
  Run `buildrix domains` to see valid options:
  `general`, `energy-modeling`, `control-optimization`, `semantic-modeling`,
  `lighting`, `code-compliance`, `thermal-comfort`
- `metadata.depends_on` — if your skill uses another skill, list it here

The markdown body contains instructions the agent follows. Write it like
you're training a new team member: when to use the skill, step-by-step
instructions, and concrete examples.

### Step 3: Write Your Scripts

This is where your domain expertise goes. For the heat wave skill:

```python
# scripts/heat_wave.py
def identify_heat_waves(df, method="percentile", percentile=90, min_duration=3):
    """Find consecutive days exceeding temperature threshold."""
    ...
```

Your skill can depend on other skills. The heat wave skill imports from
the weather skill to get data:

```python
# In the agent's workflow, it chains skills together:
# 1. weather-data-extraction fetches the temperature data
# 2. heat-wave-identification analyzes it for extreme events
```

### Step 4: Test Locally

Install your skill for local testing with Claude Code:

```bash
buildrix dev heat-wave-identification/
```

This copies the skill to `~/.claude/skills/` so Claude Code discovers it.
Open Claude Code and try:

> "Find heat waves in Phoenix for summer 2024"

Claude should use both the weather skill (to get data) and your heat wave
skill (to identify events).

### Step 5: Push to the Hub

```bash
# Push a single skill
buildrix push heat-wave-identification/

# Or push all skills at once
buildrix push skillset/ --all

# Update existing skills you own
buildrix push skillset/ --all --update
```

Output:
```
  Pushing 7 item(s)...

  [heat-wave-identification]
  ✅ 'heat-wave-identification' submitted (submitted)
  [weather-data-extraction]
  ✅ 'weather-data-extraction' updated (v0.1.0, submitted)

  Summary: 7 pushed, 0 failed
```

An LLM reviewer will evaluate your submission and provide feedback.
Once accepted, your skill appears on the hub for everyone to install.

---

## Contributing a Test Case

Test cases define a task + expected outputs, so skills can be benchmarked.

```bash
buildrix new testcase phoenix-heat-waves-summer-2024
```

Edit `TESTCASE.yaml`:

```yaml
name: "phoenix-heat-waves-summer-2024"
category: "data-extraction"
domain: "energy-modeling"
difficulty: "medium"

task:
  prompt: |
    Identify all heat wave events in Phoenix, AZ for June-September 2024.
    Use the 90th percentile method with a minimum duration of 3 days.
    Report each event's dates, duration, peak temperature, and CDH.

outputs:
  - path: "expected_outputs/heat_wave_events.csv"
    verification: "structural"
    required_columns: [start, end, duration_days, peak_temp_C]
    min_rows: 1
```

Add your reference output (what a correct result looks like) to
`expected_outputs/`. Then push:

```bash
buildrix push phoenix-heat-waves-summer-2024/
```

---

## How Skills Compose

One of the powerful ideas in Buildrix: skills build on each other.

```
User: "What were the extreme heat events in Syracuse last year?"
       │
       ▼
  ┌─────────────────────────────┐
  │ weather-data-extraction     │  ← Gets the raw temperature data
  │ (community skill)           │
  └─────────────┬───────────────┘
                │ DataFrame with hourly temps
                ▼
  ┌─────────────────────────────┐
  │ heat-wave-identification    │  ← YOUR contribution
  │ (your skill)                │
  └─────────────┬───────────────┘
                │ Events, report, CSV
                ▼
           User gets results
```

You didn't need to know how to fetch weather data — the community already
built that skill. You contributed your domain expertise (heat wave
identification), and the harness chains them together.

---

## Batch Operations

The CLI supports batch operations to save time:

```bash
# Install multiple skills at once
buildrix install weather-data-extraction heat-wave-identification energyplus-eppy

# Uninstall multiple
buildrix uninstall weather-data-extraction heat-wave-identification

# Push everything under skillset/
buildrix push skillset/ --all --update

# Delete multiple from the hub
buildrix delete old-skill-1 old-skill-2 --yes
```

---

## Skill Review Process

After you push, your submission goes through:

1. **Submitted** — your skill is on the hub, visible to reviewers
2. **In Review** — an LLM reviewer checks structure, quality, safety
3. **Needs Revision** / **Accepted** — you get feedback or it goes live

Review criteria:
- SKILL.md is complete (description, instructions, examples)
- Scripts are functional and documented
- Domain is relevant to building science
- No hardcoded secrets or unsafe operations
