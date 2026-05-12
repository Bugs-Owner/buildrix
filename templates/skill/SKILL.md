---
name: your-skill-name
description: >-
  [REQUIRED] A clear description of what this skill does and when to use it.
  Include keywords that agents and users will search for. Mention the
  building-science domain context. Max 200 characters recommended.
license: Apache-2.0
metadata:
  author: your-name-or-org
  version: "0.1.0"
  domain: general          # general | energy-modeling | control-optimization | semantic-modeling | lighting | code-compliance | thermal-comfort
  tags: []                 # e.g., [weather, solar, HVAC, EnergyPlus]
---

# Your Skill Name

[Brief overview — 2-3 sentences describing what this skill does and why it matters
for building science applications.]

## When to Use This Skill

- [Trigger condition 1 — what would the user say?]
- [Trigger condition 2]
- [Trigger condition 3]

## Capabilities

- [What can this skill do? — bullet list of features]
- [What data sources does it use?]
- [What outputs does it produce?]

## Instructions

### Step 1: Understand the Input

[What information does the agent need from the user? Location? Date range?
File path? Configuration parameters?]

### Step 2: Execute the Task

[What script to run and how. Include a complete code example:]

```python
import sys
sys.path.insert(0, "<skill_directory>/scripts")
from main import run

result = run(
    # parameter_1="value",
    # parameter_2="value",
    # output_dir="outputs",
)
```

### Step 3: Deliver Outputs

[What files are produced? What should the agent present to the user?]

- `outputs/result.csv` — [description]
- `outputs/report.md` — [description]
- `outputs/plot.png` — [description]

## Examples

**Example 1 — [Basic usage]:**
> "[Exact user prompt]"

→ [What the agent does, step by step]

**Example 2 — [Advanced usage]:**
> "[Exact user prompt]"

→ [What the agent does]

## Limitations

- [What this skill cannot do]
- [Known constraints — data availability, resolution, accuracy]
- [When the user should use a different approach]

## Data Sources

- [Where does this skill get its data? APIs, files, databases?]
- [Any API keys required?]
- [Rate limits or usage restrictions?]

## Dependencies

See `requirements.txt` in this skill's directory.

## References

See the `references/` directory for related papers, documentation, or data dictionaries.
