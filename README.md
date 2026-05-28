# Buildrix

**Open skill framework for building science AI agents.**

Build, share, and benchmark reusable AI skills for architecture, engineering, and construction (AEC) workflows. Skills work with Claude Code, OpenAI Codex, Gemini CLI, and any tool supporting the [Agent Skills](https://agentskills.io) open standard.


<img width="2538" height="1508" alt="overall_demo_fast" src="https://github.com/user-attachments/assets/6d0594c6-10a1-46b9-bacb-14e958c406e3" />


Community hub: **[buildrixhub.onrender.com](https://buildrixhub.onrender.com/)** — browse skills, test cases, challenges, and leaderboard.

---

## Quick Start

```bash
# Install
git clone https://github.com/Bugs-Owner/buildrix.git
cd buildrix
pip install -e .

# Connect to the hub
buildrix config hub https://buildrixhub.onrender.com
buildrix login --register

# Browse what's available
buildrix browse
buildrix domains

# Install a skill and use it with Claude Code
buildrix install weather-data-extraction
# → installed to ~/.buildrix/skills/ and linked to ~/.claude/skills/
```

Open Claude Code and ask: *"Extract April 2025 weather data for Syracuse, NY"* — Claude discovers and uses the skill automatically.

---

## CLI Reference

### Account

```bash
buildrix register                        # Create a hub account
buildrix login                           # Log in
buildrix logout                          # Log out
buildrix whoami                          # Show current user
buildrix config hub <url>                # Set hub URL
buildrix info                            # Hub stats + connection info
```

### Install & Manage Skills

```bash
buildrix install <name> [name2 ...]      # Install from hub (batch OK)
buildrix uninstall <name> [name2 ...]    # Remove (batch OK)
buildrix dev <skill-dir>                 # Link a local skill for development
buildrix list                            # List installed skills
```

### Discover Skills

```bash
buildrix browse                          # List all hub skills
buildrix browse --domain energy-modeling # Filter by domain
buildrix browse --sort most_downloaded   # Sort options: newest, oldest, most_liked, most_downloaded, most_saved
buildrix search <query>                  # Search by keyword
buildrix domains                         # Show valid domain categories
```

### Push & Update

```bash
buildrix push <dir>                      # Push a single skill
buildrix push <dir1> <dir2> ...          # Push multiple skills
buildrix push skillset/ --all            # Auto-discover and push all skills in a directory
buildrix push skillset/ --all --update   # Update all existing skills you own
buildrix delete <name> [name2 ...] --yes # Delete from hub (batch OK)
```

### Scaffold

```bash
buildrix new skill <name>                # Create a skill from template
buildrix new testcase <name>             # Create a test case from template
```

---

## Available Skills

| Skill | Domain | Description |
|-------|--------|-------------|
| `weather-data-extraction` | energy-modeling | Site-specific weather data via Open-Meteo — GHI, temperature, humidity, wind |
| `heat-wave-identification` | energy-modeling | Identify extreme heat events (WMO, NWS, percentile methods) |
| `energyplus-simulation` | energy-modeling | Run EnergyPlus IDF files, collect results to Parquet/CSV |
| `energyplus-eppy` | energy-modeling | Read/modify IDF files with eppy — envelope, HVAC, schedules |
| `resstock-building-generation` | energy-modeling | Generate residential IDFs from NREL ResStock distributions |
| `timeseries-forecast` | energy-modeling | LSTM forecasting for building data (GPU-accelerated) |
| `error-notebook` | general | Self-improvement protocol — track and fix agent errors |

Install any of them: `buildrix install weather-data-extraction heat-wave-identification`

---

## Domain Categories

Skills are organized into building-science domains that match the hub:

- `general` — cross-cutting tools and utilities
- `energy-modeling` — energy simulation, weather data, load analysis
- `control-optimization` — HVAC controls, MPC, optimization
- `semantic-modeling` — BIM, IFC, ontologies
- `lighting` — daylighting, glare, lighting design
- `code-compliance` — building codes, standards checking
- `thermal-comfort` — PMV/PPD, adaptive comfort, ASHRAE 55

Set the domain in your SKILL.md frontmatter: `domain: energy-modeling`

---

## Creating a Skill

```bash
buildrix new skill my-skill-name
```

This generates:

```
my-skill-name/
├── SKILL.md           # Agent instructions + YAML frontmatter
├── config.yaml        # Structured metadata
├── scripts/main.py    # Your code
├── tests/             # Unit tests
├── requirements.txt   # Dependencies
├── references/        # Papers, docs
├── assets/            # Templates, data
├── NOTES.md           # Agent error log
├── CHANGELOG.md       # Version history
└── LICENSE            # Apache 2.0
```

Edit `SKILL.md` and `config.yaml`, implement your logic in `scripts/`, test locally with `buildrix dev my-skill-name/`, then push with `buildrix push my-skill-name/`.

## Creating a Test Case

```bash
buildrix new testcase my-test-case
```

Test cases define a task with human-expert reference outputs, used for benchmarking skills. Add input data to `inputs/`, reference outputs to `expected_outputs/`, then `buildrix push my-test-case/`.

---

## How Skills Compose

Skills chain together — you contribute domain expertise, the community handles the rest:

```
User: "What were the extreme heat events in Syracuse last year?"
       │
       ▼
  ┌─────────────────────────────┐
  │ weather-data-extraction     │  ← fetches raw temperature data
  └─────────────┬───────────────┘
                │
                ▼
  ┌─────────────────────────────┐
  │ heat-wave-identification    │  ← finds events, computes CDH
  └─────────────┬───────────────┘
                │
                ▼
           User gets results
```

---

## Project Structure

```
buildrix/
├── buildrix/              # CLI package
│   ├── cli.py             # Command definitions
│   ├── hub_client.py      # Hub API client
│   ├── config.py          # Local config (~/.buildrix/)
│   ├── skill_manager.py   # Install/uninstall logic
│   └── scaffold.py        # Template scaffolding
├── skillset/              # Community skills (pushed to hub)
├── templates/             # Skill & test case templates
├── examples/              # Working examples
├── pyproject.toml
└── requirements.txt
```

## Community

- **Browse skills & challenges:** [Buildrix Hub](https://buildrixhub.onrender.com/)
- **Report issues:** [GitHub Issues](https://github.com/Bugs-Owner/buildrix/issues)
- **Hub source:** [github.com/Bugs-Owner/buildrixhub](https://github.com/Bugs-Owner/buildrixhub)
- **Contribute:** See [CONTRIBUTING.md](CONTRIBUTING.md)

## License

Apache 2.0
