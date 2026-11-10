# Changes

## Unreleased

- Studies set an expected time per task (`time:` in the study manifest;
  explicit per-task values, an optional factor x a reference run, else a
  default; at least 15 minutes). Runs that keep changing outputs/ or computing
  are extended past it up to a ceiling (4x by default); stalled, looping or
  non-progressing runs are stopped, always after a notice in
  `TIME_REMAINING.txt`, and graded on their outputs as `stopped` runs. Runs
  record their budget, extensions, stop reason and machine.
  Runner version 2.1.0: finish studies prepared earlier with the older runner.
- `task draft rubric ID --data table.json` saves a task's Evaluation scoring
  table; the interactive wizard builds the table step by step.
- Benchmark runs send measured time, tokens and tool calls to the hub grader,
  and keep the scoring table's full result in each record's evidence.

## 0.1.0

- Shared task and skill contribution workflows across web, CLI and local agents.
- Saved drafts, withdrawal and reviewed revisions under the same published ID.
- File descriptions, environment attachments and completed task outputs.
- Private original input history and local-agent contribution sync.
- Current domain names and consistent search, download and submission commands.
- Outdated sample packages removed; contribution documentation simplified.

Benchmark functionality remains under development.
