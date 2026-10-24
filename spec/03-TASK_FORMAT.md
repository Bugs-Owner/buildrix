# Task packages

Use `buildrix task develop` to prepare a real engineering task you have
completed. The hub stores its description, structured definition, attachments
and reviewed revisions.

About the task asks for the title, domain, effort, complexity, your
familiarity, AI use and the related stakeholders: who could learn from this
task. Pick at least one. If you pick "Other", say who.

The reviewer checks six sections: objective, inputs, environment,
reproducibility, deliverables and evaluation. It asks questions until each one
is clear.

If the task invites open-ended search ("find the best model", "any approach"),
the reviewer asks under Reproducibility if the default limit is fine: each
agent compares at most five candidate approaches and keeps the best one,
picked on validation data. You can keep it, change the number or list the
candidates.

Then you add **Human knowledge** on its own step, before final review. This is
what you know about doing the task well: steps, rules of thumb, pitfalls,
checkpoints, when to stop or retry, references, code. There is no format, and
the reviewer does not check it. A few lines or one file is enough. Benchmarks
compare agents on the task alone and on the task plus your knowledge.

See the [task contribution guide](../skills/buildrix/references/task-format.md)
for the current requirements and file commands.

Download a published task with:

```sh
buildrix task pull TASK_CODE --dir ./tasks --extract
```

Use the task identifier returned by search. Downloads respect your account's
access to the attached files.

`buildrix task new my-task` creates a local working scaffold.
Local folder checks do not replace guided submission and LLM review.
