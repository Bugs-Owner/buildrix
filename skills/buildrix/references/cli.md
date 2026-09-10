# CLI reference

```
buildrix
├── task       search · show · pull · init · validate · submit · archive
├── skill      search · show · pull · init · validate · submit · archive
├── benchmark  match · run · pull
└── auth · domains · info · env · config
```

Two motions, both vocabularies:

```
Discover:  search → show → pull
Develop:   init → validate → submit
```

Batch is built in. Anything taking one name takes several, and paths accept
globs: `buildrix skill pull a b c`, `buildrix skill validate ./skills/*`.

## task

| Command | What it does |
|---|---|
| `buildrix task search [QUERY] [--domain D] [--difficulty D] [--limit N]` | Search published Tasks. |
| `buildrix task show TASK [TASK…]` | Full definition, prompt included. Withheld parts are marked. |
| `buildrix task pull TASK [TASK…] [--dir D] [--extract]` | Download the public package. |
| `buildrix task init [--resume ID]` | The guided definition — the same workflow as the website. |
| `buildrix task validate PATH [PATH…] [--no-grader]` | Run the task gates locally. |
| `buildrix task submit PATH [PATH…]` | Submit through the guided workflow. |
| `buildrix task archive DRAFT [DRAFT…]` | Archive a draft; its history is kept. |

## skill

| Command | What it does |
|---|---|
| `buildrix skill search [QUERY] [--domain D] [--limit N]` | Search published Skills. |
| `buildrix skill show SKILL [SKILL…]` | Description, SKILL.md and benchmark summary. |
| `buildrix skill pull SKILL [SKILL…] [--dir D] [--extract]` | Download the package. |
| `buildrix skill init [--resume ID]` | The guided authoring workflow. |
| `buildrix skill validate PATH [PATH…]` | Canonical rules, run on the hub; local fallback offline. |
| `buildrix skill submit PATH [PATH…]` | Import an existing folder, then finish it in the workflow. |
| `buildrix skill archive DRAFT [DRAFT…]` | Archive a draft. |

Also kept: `skill new` (scaffold), `skill check` (local gates), `skill install`,
`skill list`, `skill remove`, `skill update`, `skill dev`.

## benchmark

| Command | What it does |
|---|---|
| `buildrix benchmark match --skill PATH-OR-NAME [--domain D] [--limit N]` | Which Tasks are worth benchmarking this Skill against, with reasons. |
| `buildrix benchmark run --skill PATH --task T [T…] --agent CMD --model M [--harness H] [--timeout S] [--visibility public\|private]` | All four conditions per instance, then automatic upload. |
| `buildrix benchmark pull [--skill S] [--task T] [--model M] [--json]` | Read results: your Skill, a Task, or the public record. |

`--agent` is the command that runs your agent. The prompt arrives as
`$BUILDRIX_PROMPT` and as `PROMPT.md` in the working directory:

```bash
buildrix benchmark run --skill ./my-skill --task BXT-000012 \
  --agent 'claude -p "$BUILDRIX_PROMPT"' \
  --model claude-opus-5 --harness claude-code
```

Without `--agent` the run is a dry run: it exercises isolation, evaluation and
upload, produces no work, and is recorded privately so it cannot be mistaken for
a measurement.

## general

| Command | What it does |
|---|---|
| `buildrix auth login \| logout \| whoami \| register` | Account. `login` prompts for a password. |
| `buildrix domains [--task]` | The closed domain taxonomy. |
| `buildrix info` | Hub URL, signed-in user, installed skills, hub stats. |
| `buildrix config hub URL` | Point the CLI at a hub. |
| `buildrix env info \| setup \| clean` | The managed toolchain (EnergyPlus, OpenStudio, …). |
