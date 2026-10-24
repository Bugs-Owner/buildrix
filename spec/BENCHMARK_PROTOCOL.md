# Buildrix benchmark protocol, version 1

Every benchmark round follows this protocol so results stay comparable across
rounds. Agents may answer differently from run to run; the settings may not.
Repeat runs show that spread. Change a setting only by publishing a new
protocol version, and never mix versions in one comparison.

## What stays fixed

| Setting | Version 1 value |
|---|---|
| Models | Claude Haiku 5.5, Sonnet 5.5, Opus 5.5 (Claude Code); GPT-5.6 Luna, Terra, Sol (Codex) |
| Reasoning levels | low, medium, high for every model |
| Agent tools | Claude Code 2.1.309 and Codex 0.152.0, run headless |
| Login | Subscription login, one account per provider |
| Conditions | `task` (the task alone) and `task_instruction` (task plus the contributor's human knowledge) |
| Time limit | 60 minutes of wall-clock time per run |
| Compute per run | 4 CPU cores, 16 GB memory, no GPU, on MIT ORCD Engaging (`mit_preemptable`, requeue on preemption) |
| Software the agent sees | The fixed read-only scientific Python in `tools/`, then the two agent tools, then system tools |
| Workspace | A fresh copy of the task's `inputs/` and brief; deliverables go in `outputs/` |
| Open-ended search | At most five candidate approaches, best one chosen on validation data (stated in each task) |
| Trials | 1 per task, model, level and condition in a full round; repeats add trials, they do not change the above |
| Seed | 42, which fixes the run order |
| Grader | The hub grader (`claude-opus-5-5`, reply budget 16,000 tokens) against each task's own scoring table and hidden reference |
| Task versions | Frozen when the study is prepared; the study records each task's digest |

## How a round runs

1. **Prepare.** `buildrix benchmark prepare` freezes the task packages and the
   settings above into a bundle with a digest. A bundle that changes after
   this step will not run.
2. **Run.** `buildrix benchmark batch --offline`, sharded across Slurm array
   jobs. Each job resumes where it stopped if the cluster preempts it.
3. **Rerun only infrastructure failures.** Runs stopped by preemption or by a
   provider usage limit are set aside and rerun with the same settings. Runs
   that hit the time limit, crash or hand back nothing count as the agent's
   result and are never rerun.
4. **Grade.** `buildrix benchmark sync` sends each group to the hub grader and
   uploads it. Grading errors are retried; they never change a score.
5. **Report.** Scores are the share of each task's scoring criteria met,
   averaged over tasks. Timed-out runs stay in the average with whatever they
   delivered.

## Recording

Each run keeps its prompt, transcript, outputs, tool versions, wall time and
token use. The study manifest, the Slurm script and this protocol version are
stored with the results.
