# Buildrix

**The open skill framework for building science AI agents.**

Build, share, and benchmark AI skills for architecture, engineering, and
construction (AEC) workflows. Compatible with Claude Code, OpenAI Codex,
Gemini CLI, and any tool supporting the
[Agent Skills](https://agentskills.io) open standard.

> Community hub: [buildrix-hub](https://YOUR-RENDER-URL.onrender.com)
> (browse skills, test cases, challenges, leaderboard)

---

## Quick Start

```bash
# 1. Clone the repo
git clone https://github.com/YOUR-USERNAME/buildrix.git
cd buildrix

# 2. Install dependencies
pip install -r requirements.txt

# 3. Try the example skill (weather data extraction)
cd examples/skills/weather-data-extraction
python scripts/weather_helper.py "Syracuse, NY" 30
```

## Use with Claude Code

```bash
# Copy a skill into your Claude Code skills directory
cp -r examples/skills/weather-data-extraction ~/.claude/skills/

# Now in Claude Code, just ask:
# "Extract April 2025 weather data for Syracuse, NY"
# Claude will automatically discover and use the skill.
```

## Project Structure

```
buildrix/
├── examples/
│   ├── skills/                      # Working skill examples
│   │   └── weather-data-extraction/ # First community skill
│   └── testcases/                   # Example test cases
│       └── syracuse-weather-april-2025/
├── templates/
│   ├── skill/                       # Copy this to start a new skill
│   │   └── SKILL.md
│   └── testcase/                    # Copy this to start a new test case
│       └── TESTCASE.yaml
├── buildrix/                        # CLI tool (coming soon)
└── requirements.txt
```

## Creating a Skill

1. Copy the template: `cp -r templates/skill/ my-new-skill/`
2. Edit `SKILL.md` — follow the [Agent Skills spec](https://agentskills.io/specification)
3. Add your scripts to `scripts/`
4. Test locally
5. Submit to the [Buildrix Hub](https://YOUR-RENDER-URL.onrender.com)

## Creating a Test Case

1. Copy the template: `cp -r templates/testcase/ my-test-case/`
2. Edit `TESTCASE.yaml` — define inputs, expected outputs, verification
3. Add reference data to `expected_outputs/`
4. Submit — an LLM reviewer will evaluate and provide feedback

## Skill Format

Skills follow the [Agent Skills open standard](https://agentskills.io):

```
skill-name/
├── SKILL.md        # Required: YAML frontmatter + markdown instructions
├── scripts/        # Optional: helper code
├── references/     # Optional: documentation, data
└── assets/         # Optional: templates, images
```

This means your skills work across Claude Code, Codex CLI, Gemini CLI,
GitHub Copilot, Cursor, VS Code, and 30+ other tools.

## Community

- **Browse skills & challenges:** [Buildrix Hub](https://YOUR-RENDER-URL.onrender.com)
- **Report issues:** [GitHub Issues](https://github.com/YOUR-USERNAME/buildrix/issues)
- **Contribute:** See examples/ for reference, then submit your own

## License

Apache 2.0
# buildrix
