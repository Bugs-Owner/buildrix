# Task contribution

Read this reference only after saving the initial human request without coaching.
Use `buildrix task draft meta` as the source of current options. Add the active
`--journal SESSION.jsonl` to all draft commands with a draft ID below.

- Objective: result, scope and task-defining constraints.
- Inputs & Resources: starting files or HTTPS links; what each one is and how
  the task uses it, clear enough for someone new to the project, with the units
  and conventions needed to read it correctly.
- Detailed Instruction: the experienced contributor's procedure and checks.
- Environment & Access: OS, software, versions, free/licensed tools, access and
  compute. Attach a Python environment configuration when relevant. Do not ask
  users to repeat package versions the reviewer can read from that file.
- Reproducibility: random seeds, partitions, input lengths, relevant model
  parameters and software settings. Collect applicable conditions.
- Deliverables: expected outputs and the contributor's actual completed output
  files, with contents and usage notes.
- Evaluation: dimensions, metrics, thresholds, interval/repetitions, weights
  and a final-score equation or equivalent rule. Collect per-metric results
  and the final score for the outputs attached in Deliverables. Distinguish
  self-reported results from independently checked results.

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
kind `human_reference`, both notes required. Evaluation has no upload.

`draft asset-notes ID --asset ASSET_ID --data notes.json` edits notes.
`draft remove-file ID --asset ASSET_ID` removes a draft attachment.
File changes invalidate the affected review; review before finalizing.

## Clarification and completion

`draft answer` sends a fresh reply. `draft edit` replaces a section.
Both take `ID --dimension SECTION_ID --text-file FILE` and request LLM review.
`draft describe` on an existing draft retains the initial request and logs a
new description revision.

`draft review ID --dimension SECTION_ID` reviews existing text and files.
Omit the dimension to recheck the task. `draft get ID` returns questions and
submission blockers.

Finish with `draft finalize ID`, inspect the revised task, then
`draft submit ID --consent`. Legacy local task-folder checks do not replace
the shared submission review.
