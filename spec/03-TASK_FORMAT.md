# Task packages

Use `buildrix task develop` to prepare a real engineering task you have
completed. The hub stores its description, structured definition, attachments
and reviewed revisions.

The contribution covers the objective, inputs, detailed instruction,
environment, reproducibility, deliverables and evaluation. See the
[task contribution guide](../skills/buildrix/references/task-format.md)
for the current requirements and file commands.

Download a published task with:

```sh
buildrix task pull TASK_CODE --dir ./tasks --extract
```

Use the task identifier returned by search. Downloads respect your account's
access to the attached files.

`buildrix task new my-task` creates a local working scaffold.
Local folder checks do not replace guided submission and LLM review.
