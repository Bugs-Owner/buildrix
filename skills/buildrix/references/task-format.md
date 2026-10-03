# Task contribution

Read this reference only after saving the initial human request without coaching.
Use `buildrix task draft meta` as the source of current options. Add the active
`--journal SESSION.jsonl` to all draft commands with a draft ID below.

- Objective: result, scope and task-defining constraints.
- Inputs & Resources: starting files or HTTPS links; what each one is and how
  the task uses it, clear enough for someone new to the project, with units and
  conventions only where the data does not make them clear.
- Detailed Instruction: the experienced contributor's procedure and checks.
- Environment & Access: OS, software, versions, free/licensed tools, access and
  compute. Attach a Python environment configuration when relevant. Do not ask
  users to repeat package versions the reviewer can read from that file.
- Reproducibility: random seeds, partitions, input lengths, relevant model
  parameters and software settings. Collect applicable conditions.
- Deliverables: expected outputs and the contributor's actual completed output
  files, with contents and usage notes.
- Evaluation: a scoring table, saved with `draft rubric` (below). 1 Score:
  how many stages and their weights; per stage, how many performance metrics,
  each named by the aspect it measures (Accuracy, Robustness), with how it is
  calculated (data, period, formula or equation, units), the value that scores
  100 (<= or >=), the value that scores 0, and a weight. 2 Success: each output
  that must be delivered, described by what it is and contains rather than by
  the user's file names; a passing condition and the user's own result per
  metric; optional yes/no conditions. `rubric_hint` in `draft get` is the
  reviewer's draft, for examples only. The hub's script checks weights and
  values.

Do not invent project facts. Separate goal/constraints from procedure; let the
hub route new clarifications to the appropriate section.

## Files and links

For an input, save this shape as file-notes.json, using the contributor's words:

```json
{
  "dimension": "inputs_resources",
  "kind": "input",
  "description": "Description of the file",
  "usage": "Meaning of fields, units and how to use them"
}
```

```sh
buildrix task draft upload DRAFT_ID --file ./data.csv --data file-notes.json
```

Upload each file with its own notes. Each upload supports up to 50 MB.
For larger files, use `draft link ID --data link.json` with the same fields
plus `filename` and `source_url` (HTTPS). Links are recorded; their contents
and accessibility are not automatically verified.

Environment files: dimension `environment_access`, kind `environment`;
description/usage are optional. Completed outputs: dimension `deliverables`,
kind `human_reference`; `description` (format and contents, and how to run it
for a model or tool) is required, `usage` optional. Several files of one kind
may share the same notes. Evaluation has no upload.

`draft asset-notes ID --asset ASSET_ID --data notes.json` edits notes.
`draft remove-file ID --asset ASSET_ID` removes a draft attachment.
File changes invalidate the affected review; review before finalizing.

## Scoring table

Save this shape as table.json, with the user's values:

```json
{
  "stages": [
    {"name": "", "weight": 1, "dimensions": [
      {"name": "Accuracy", "metric": "CVRMSE of hourly kw against measured December load",
       "better": "lower", "best": 0.28, "worst": 0.88, "weight": 0.7,
       "pass_line": 0.5, "own_value": 0.43},
      {"name": "Tokens", "metric": "Total tokens the run used",
       "better": "lower", "best": 50000, "worst": 300000, "weight": 0.3,
       "pass_line": 250000, "own_value": 100000}
    ]}
  ],
  "deliverables": [{"name": "forecast.csv", "requirement": "hourly timestamp and kw, December"}],
  "conditions": ["No missing hours in December"]
}
```

```sh
buildrix task draft rubric DRAFT_ID --data table.json
```

`better: lower` means score 100 at `<= best` and 0 at `>= worst`, linear in
between and capped; `higher` reverses the signs. `pass_line` is the passing
condition with the same sign as `best`; `own_value` is the user's own result
(self-reported; checked when the task is benchmarked). Weights within a stage add up to 1;
with several stages, name each and give stage weights that add up to 1.
`conditions` are optional extra yes/no requirements. When results span many
periods or cases, say how each dimension combines them and add a dimension for
the spread or worst case (worst day, 90th percentile, share of days passing). A run
succeeds only when everything is delivered and every condition is met. An
invalid table is refused with the reasons; fix and resend it. Evaluation text
is generated from the table, so `draft edit` does not apply to it.

## Clarification and completion

`draft answer` sends a fresh reply. `draft edit` replaces a section.
Both take `ID --dimension SECTION_ID --text-file FILE` and request LLM review.
`draft describe` on an existing draft retains the initial request and logs a
new description revision.

`draft review ID --dimension SECTION_ID` reviews existing text and files.
Omit the dimension to recheck the task. `draft get ID` returns questions and
submission blockers.

Finish with `draft finalize ID`, inspect the revised task, then
`draft submit ID --consent`. If the review asks for a revision,
`draft reply ID --text-file reply.txt [--file missing.csv]` answers its open
points in the user's words, with any file it asked for. The hub checks only
those points; what settles one is merged into the task, and the task is
accepted when none remain. A reply never raises new points. Legacy local task-folder checks do not replace
the shared submission review.
