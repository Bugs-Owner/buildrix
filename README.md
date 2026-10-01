# Buildrix

Find, develop and share agentic AI skills and real building engineering tasks.

Use the [website](https://buildrixhub.onrender.com/), CLI or
[Buildrix skill](skills/buildrix/SKILL.md) inside your local agent.
Contributions use the same saved drafts and LLM review across all three.

**Version 0.1.0.** Task and skill workflows are available for testing.
Benchmarks execute locally or on compute nodes, with frozen studies, independent
trials, retained evidence and automatic result uploads. See the
[benchmark and cluster guide](docs/benchmark.md) for setup and trust limitations.

## Install and sign in

Requires Python 3.11 or newer.

```sh
python -m pip install git+https://github.com/Bugs-Owner/buildrix.git
buildrix auth register
```

Already registered? Use `buildrix auth login`.

## Find and download

```sh
buildrix skill search "load forecasting"
buildrix task search "load forecasting"
buildrix skill show SKILL_CODE
buildrix task show TASK_CODE
buildrix skill pull SKILL_CODE --dir ./skills --extract
buildrix task pull TASK_CODE --dir ./tasks --extract
```

Use the identifiers returned by search in place of `SKILL_CODE` and `TASK_CODE`.
Public search and downloads do not require login.

## Develop and submit

```sh
buildrix skill develop
buildrix task develop
```

The wizard guides you through the contribution, saves your progress and shows
reviewer comments. You can edit previous steps and answer new questions before
submitting.

For a skill, provide your SKILL.md and supporting files. To start from an
existing folder, use `buildrix skill submit ./my-skill`.

For a task, describe real work you have completed. Attach the inputs and your
completed outputs, explain how to use the files, document the environment and
reproducibility settings, and define how to evaluate the result.

See the [contribution guide](CONTRIBUTING.md) for the full workflow.

## Resume or revise

| Action | Skill | Task |
|---|---|---|
| List saved work | `buildrix skill drafts` | `buildrix task drafts` |
| Resume a draft | `buildrix skill develop --resume DRAFT_ID` | `buildrix task develop --resume DRAFT_ID` |
| Revise a publication | `buildrix skill revise SKILL_CODE` | `buildrix task revise TASK_CODE` |
| Withdraw unfinished work | `buildrix skill withdraw DRAFT_ID` | `buildrix task withdraw DRAFT_ID` |

Revisions keep the published ID and require a fresh LLM review. The current
publication stays available while you edit. Original input history is retained
privately for the contributor and administrators.

## Use your local agent

Install the complete [Buildrix skill folder](skills/buildrix/) in your
harness's skill directory. Then ask your agent to help find a contribution,
develop a skill or prepare a completed task for submission.

The skill guides setup, editing and hub review.
[Local contribution history](skills/buildrix/references/local-interactions.md)
syncs with the same saved draft.

## More guidance

- `buildrix skill --help` and `buildrix task --help` — available commands.
- [Command reference](skills/buildrix/references/cli.md) — draft automation.
- [Task guide](skills/buildrix/references/task-format.md) and [skill guide](skills/buildrix/references/skill-format.md).
- [Domains](spec/01-TAXONOMY.md) and [package formats](spec/00-OVERVIEW.md).
- [Development setup](CONTRIBUTING.md#contribute-code).

## Contributors

- **[Zixin Jiang (Bugs-Owner)](https://github.com/Bugs-Owner)** — project creator, engineering requirements, design and testing.
- **Claude Code (Anthropic)** — AI-assisted development.
- **Codex (OpenAI)** — AI-assisted development.

## License

Apache-2.0. Contributed tasks and skills carry their own licenses.
