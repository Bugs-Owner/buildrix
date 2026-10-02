# Contributing to Buildrix

Contribute a reusable building engineering skill or a real task you have already
completed. Use the [browser](https://buildrixhub.onrender.com/#/docs), terminal,
or the [Buildrix skill](skills/buildrix/SKILL.md) inside your local agent.
All three use the same saved drafts and hub review.

## Install and sign in

```sh
python -m pip install git+https://github.com/Bugs-Owner/buildrix.git
buildrix auth register
```

If you already have an account, use `buildrix auth login`.

## Develop a skill or task

```sh
buildrix skill develop
buildrix task develop
```

For a skill, supply your SKILL.md and the supporting files used by your workflow.
The wizard collects metadata, shows LLM reviewer comments and lets you revise
before submission. You can also start with an existing package:

```sh
buildrix skill submit ./my-skill
```

For a task, start with your own description of work you have completed, as
clearly as you would hand it to a teammate. The wizard then helps you clarify
the task, attach inputs and completed outputs, document the environment and
reproducibility settings, and fill in a scoring table: what must be delivered,
the dimensions you score with their bounds, weights and passing lines, and what
your own output achieved. Answer new reviewer
questions in the next reply; the hub incorporates the clarification into the
saved section. Review the revised task before submitting.

## Resume, revise or withdraw

```sh
buildrix skill drafts
buildrix task drafts
buildrix skill develop --resume DRAFT_ID
buildrix task develop --resume DRAFT_ID
buildrix skill revise SKILL_CODE
buildrix task revise TASK_CODE
```

Replace `DRAFT_ID`, `SKILL_CODE` and `TASK_CODE` with the identifiers shown by
Buildrix. Revisions keep the published ID, require LLM review and create a new
version when submitted. The current publication remains available while you edit.

To withdraw an unfinished contribution, use `buildrix skill withdraw DRAFT_ID`
or `buildrix task withdraw DRAFT_ID`. Original inputs and interaction history
remain private to the contributor and administrators.

## References

- [CLI commands](skills/buildrix/references/cli.md), or run `buildrix skill --help` and `buildrix task --help`.
- [Skill submission guide](skills/buildrix/references/skill-format.md).
- [Task submission guide](skills/buildrix/references/task-format.md).
- [Local agent interaction logging](skills/buildrix/references/local-interactions.md).
- [Current scaffolding](templates/) for developing packages locally.

## Contribute code

```sh
git clone https://github.com/Bugs-Owner/buildrix.git
cd buildrix
python -m pip install -e ".[dev]"
python -m pytest
```

Keep web, CLI and local-agent submissions consistent. Describe the user-visible
change and relevant validation in your pull request. Hub changes belong in
[buildrixhub](https://github.com/Bugs-Owner/buildrixhub).
