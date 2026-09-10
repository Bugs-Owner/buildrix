# Benchmark

## The four conditions

Run for every Task instance, each in its own clean workspace:

| Condition | What the agent has |
|---|---|
| `task` | The canonical Task prompt and nothing else. The control. |
| `task_instruction` | Task + the contributor's Detailed Instruction. |
| `task_skill` | Task + the Skill package. The number a Skill is judged on. |
| `task_instruction_skill` | Both. Shows whether the Skill still adds anything once the procedure is known. |

Held identical across all four: the same agent and model, the same Task and
instance, the same environment and inputs, the same reproducibility settings,
the same compute and time limits. The **only** declared difference is which of
the Skill and the Detailed Instruction was staged.

## How a run is graded

Grading happens on the hub, because that is the only place the reference answer
exists. The runner ships the artifacts the agent produced, with a readable slice
of each text file; the hub scores them in two layers:

1. **Mechanical facts** — does each declared deliverable exist, is it non-empty,
   does the CSV carry the required columns. Computed, then handed to the grader
   as findings so it never guesses at a file listing.
2. **Judgement** — correctness against the reference, the Task's own success
   criteria, and whether the fixed reproducibility conditions held.

The judgement is a language model with its known failure modes closed off:
self-reported metrics are not evidence, a missing deliverable scores zero and
cannot be argued up, every score must quote what it scored, the score anchors
are defined in words, and the grader is never told which condition it is
scoring. A hub with no model configured falls back to the contract check and
says it cannot tell a correct answer from a well-formatted wrong one.

Relay the grader a run reports. `buildrix benchmark pull` and
`GET /api/benchmark/grader` both show it.

## Reported numbers

Each Task is scored by its own evaluator and its own native metric — CVRMSE, F1,
kWh error, whatever the Task actually measures. There is no artificial universal
metric. What *is* comparable across Tasks is the **lift**:

```
Instruction Lift  = task_instruction        − task
Skill Lift        = task_skill              − task
Combined Lift     = task_instruction_skill  − task
```

A negative lift is a real, publishable result. Skills sometimes make agents
worse, and hiding that would make the benchmark worthless.

## Integrity

- **Clean isolated workspace per condition.** No file, cache, context, memory or
  output crosses between them — including skill-written state like a NOTES.md,
  which would otherwise carry learning from one condition to the next.
- **Automatic upload.** The runner submits when execution finishes. There is no
  `benchmark submit` command, because a contributor who could choose which runs
  to send would send the flattering ones.
- **No partial groups.** A submission missing any condition is rejected whole.
  Partial acceptance is itself a selection bias.
- **Scores recomputed on the hub** from the per-run evidence, never trusted as
  submitted totals.
- **Single-use nonce** issued before the run, so a result cannot be minted after
  the fact or replayed.
- **Provenance recorded**: Task and version, Skill version and digest, model,
  harness, environment fingerprint, condition, run config, evaluator version,
  outputs and metrics.
- **Hidden Task assets stay hidden.** Grading that needs the reference happens on
  the hub, after the agent has stopped.

## Matching

`buildrix benchmark match --skill <path-or-name>` asks the hub which Tasks are
worth the compute. It weighs whether the Skill's workflow produces what the Task
asks for, whether it can run on the inputs the Task supplies, whether the
environments are compatible, and whether the domains line up — not tag overlap.

Bands: `strong` (run it) · `possible` (plausible) · `weak` (skip). A list where
everything is a strong match would be useless; the point is to spend compute
where it will show a difference.
