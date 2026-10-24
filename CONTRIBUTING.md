# Contributing to Buildrix

Contribute a real building engineering task you have already completed. Use the [browser](https://buildrixhub.onrender.com/#/docs), terminal,
or the [Buildrix skill](skills/buildrix/SKILL.md) inside your local agent.
All three use the same saved drafts and hub review.

## Install and sign in

```sh
python -m pip install git+https://github.com/Bugs-Owner/buildrix.git
buildrix auth register
```

If you already have an account, use `buildrix auth login`.

## Develop a task

```sh
buildrix task develop
```

Start with your own description of work you have completed, as
clearly as you would hand it to a teammate. The wizard then helps you clarify
the task, attach inputs and completed outputs, document the environment and
reproducibility settings, and fill in a scoring table: the dimensions you
score with their values for 100 and 0 and weights, then what must be delivered
and how good it must be. Answer new reviewer questions in the next reply; the
hub incorporates the clarification into the saved section. Then add your Human
knowledge on its own step: steps, rules of thumb, pitfalls, checkpoints,
references or code. The reviewer does not check it. Review the revised task
before submitting.

## Resume, revise or withdraw

```sh
buildrix task drafts
buildrix task develop --resume DRAFT_ID
buildrix task revise TASK_CODE
```

Replace `DRAFT_ID` and `TASK_CODE` with the identifiers shown by
Buildrix. Revisions keep the published ID, require LLM review and create a new
version when submitted. The current publication remains available while you edit.

To withdraw an unfinished task, use `buildrix task withdraw DRAFT_ID`. Original inputs and interaction history
remain private to the contributor and administrators.

## References

- [CLI commands](skills/buildrix/references/cli.md), or run `buildrix task --help`.
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
