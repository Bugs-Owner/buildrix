# Buildrix

**An open skill framework and benchmark for building-engineering AI agents.**

Buildrix exists to answer one question with evidence: *does packaging
building-engineering expertise as an agent skill make an agent measurably better
at real work?*

Skills are plain [Agent Skills](https://agentskills.io) folders, so they work in
Claude Code, OpenAI Codex, Gemini CLI, or anything else that reads the standard.
Tasks are real professional work with hidden, scripted graders. Every benchmark
runs **four conditions** — the agent alone, with the expert's procedure, with the
Skill, and with both — so the effect of a Skill is measured against a control
rather than asserted.

Hub: **[buildrixhub.onrender.com](https://buildrixhub.onrender.com/)**

> **Pre-release — v0.5.0 `preview`.** Buildrix is under active development and the
> Task and Skill formats are still moving. A format change may mean re-submitting
> rather than migrating, and there is no compatibility promise between 0.x
> releases. **1.0.0** will be the first release where the formats are frozen and
> breaking one requires a major version bump.

---

## One standard, three interfaces

```
Web ──────────┐
CLI ──────────┼── Buildrix backend / API ── Task · Skill · Benchmark
Buildrix Skill┘
```

Task definition, Skill authoring, validation, matching and grading are
implemented **once, on the server**. The website, this CLI and the official
Buildrix Skill are three surfaces onto it. None of them has its own copy of the
format, so none of them can drift — and a Task or Skill is identical whichever
way it was made. You can start a draft in the browser and finish it in the
terminal, because it is the same draft.

The CLI and the Buildrix Skill do **not** get a shortcut past the guided
workflow. If the website asks you to clarify Objective, Inputs, Instruction,
Environment, Reproducibility, Deliverables and Evaluation, so does
`buildrix task init`.

---

## Install

```bash
git clone https://github.com/Bugs-Owner/buildrix.git
cd buildrix
pip install -e .

buildrix config hub https://buildrixhub.onrender.com
buildrix auth login --register
```

---

## The commands

```
buildrix
├── task       search · show · pull · develop · submit · revise · drafts · history · withdraw
├── skill      search · show · pull · develop · submit · revise · drafts · history · withdraw
├── benchmark  match · run · pull
└── auth · domains · info · env · config
```

Two motions, and they mean the same thing for a Task and for a Skill:

```
Discover:  search → show → pull
Develop:   develop → review → submit → revise
```

Batch is built in rather than bolted on — anything that takes one name takes
several, and paths accept globs:

```bash
buildrix skill pull skill-a skill-b skill-c
buildrix task pull task-a task-b
buildrix skill validate ./skills/*
```

The older commands (`skill new`, `skill check`, `skill install`, `task get`,
`login`, `push`, …) still work.

---

## Contribute a task or skill

Use the terminal wizard, or resume a draft started on the website:

```sh
buildrix task develop
buildrix skill develop
buildrix task develop --resume DRAFT_ID
buildrix skill develop --resume DRAFT_ID
```

Both collect domain, human effort, complexity, task familiarity and AI-agent
familiarity. Tasks collect a title; skills collect a name, description, version
and license. The hub supplies the same choices and guidance as the website.

Describe a real task you have completed as clearly as you would hand it to a
teammate. The task wizard shows one section at a time: Objective, Inputs &
Resources, Detailed Instruction, Environment & Access, Reproducibility,
Deliverables and Evaluation. You can return to earlier steps. New replies are
reviewed and incorporated into the saved section.

Attach inputs and your completed output files, with descriptions of their
contents and how to use them. Datasets need feature definitions and units.
Environment configuration files do not need separate notes. Files above 50 MB
can use an HTTPS shared link. Evaluation collects metrics, thresholds, weights,
the final scoring rule, and your results for the completed outputs you attached.

Skills use your actual SKILL.md and supporting files. Write the instructions or
upload a folder, request LLM feedback, and revise the files. You can also start
with `buildrix skill submit ./my-skill`. SKILL.md is required; the hub builds
Buildrix metadata from About the skill, and accepts existing skill.yaml metadata
when importing a package. Supporting files retain their relative paths.

### Revisions and history

```sh
buildrix task drafts
buildrix skill drafts
buildrix task revise TASK_CODE
buildrix skill revise SKILL_CODE
buildrix task history DRAFT_ID
buildrix skill history DRAFT_ID
```

Revising reopens the contribution under the same ID. The current publication
and its files stay intact while you edit. Resubmission creates a new version
and runs LLM review again. Prior versions and original inputs are retained.

Raw input history is available to the contributor and administrators.
Published descriptions use separate, lightly edited display text. Unfinished
contributions can be withdrawn with `buildrix KIND withdraw DRAFT_ID`;
their logs remain. An in-progress revision can be left saved to resume later.

### Agent conversations and automation

The JSON command interface uses the same draft endpoints, without an interactive
terminal. Read `buildrix KIND draft meta` for current choices and
`buildrix KIND draft --help` for actions.

```sh
buildrix task draft create --data about.json
buildrix task draft describe DRAFT_ID --text-file human-request.txt
buildrix task draft answer DRAFT_ID --dimension objective --text-file reply.txt
buildrix task draft get DRAFT_ID
buildrix task draft finalize DRAFT_ID
buildrix task draft submit DRAFT_ID --consent

buildrix skill draft create --data about.json
buildrix skill draft package DRAFT_ID --file ./my-skill
buildrix skill draft review DRAFT_ID
buildrix skill draft submit DRAFT_ID --consent
```

Use UTF-8 files to preserve the contributor's actual words. Resolve returned
questions and validation blockers before submitting. `--consent` records
agreement to retaining the contribution history and aggregate research use.
Use `revise CODE --json` to reopen a submitted contribution without a wizard.

See the [complete contribution command reference](skills/buildrix/references/cli.md),
[task guide](skills/buildrix/references/task-format.md) and
[skill guide](skills/buildrix/references/skill-format.md).

---

## Benchmark

```bash
buildrix benchmark match --skill ./my-skill
buildrix benchmark run --skill ./my-skill --task BXT-000012 BXT-000041 \
  --agent 'claude -p "$BUILDRIX_PROMPT"' \
  --model claude-opus-5 --harness claude-code
buildrix benchmark pull --skill my-skill
```

### `match`

Asks the hub which Tasks are worth spending compute on, weighing whether the
Skill's workflow produces what the Task asks for, whether it can run on the
inputs the Task supplies, and whether the environments are compatible — not tag
overlap. Bands are `strong` · `possible` · `weak`, each with a reason.

The website's Skill page calls the same service, so the ranking is identical.

### `run`

Four conditions per Task instance, each in its own clean workspace:

| Condition | What the agent has |
|---|---|
| Agent | The canonical Task prompt and nothing else. The control. |
| + Detailed Instruction | Plus the contributor's procedure. |
| + Skill | Plus the Skill package. |
| + Instruction + Skill | Both. |

Held identical: the same agent and model, the same Task and instance, the same
environment and inputs, the same reproducibility settings, the same compute and
time limits. The only declared difference is which of the Skill and the Detailed
Instruction was staged. Nothing crosses between conditions — not files, caches,
context, memory, outputs, or skill-written state.

Live progress, then the result:

```
Benchmark complete

Agent                        52
+ Detailed Instruction       68
+ Skill                      81
+ Instruction + Skill        85

Instruction Lift             +16
Skill Lift                   +29
Combined Lift                +33
```

Each Task keeps its own evaluator and native metric. The **lift** between
conditions is what compares across Tasks. A negative lift is a real result and
is reported as one.

### How a run is graded

Grading happens **on the hub**, because that is the only place the reference
answer exists. The runner ships the artifacts the agent produced — with a
readable slice of each text file, so a header or a summary travels but a 4 GB
simulation directory does not — and the hub decides what they are worth, in two
layers:

1. **Mechanical facts.** Does each declared deliverable exist, is it non-empty,
   does the CSV carry the columns the Task asked for? Computed, not judged, and
   handed to the grader as findings so it never guesses at a file listing.
2. **Judgement.** Everything a file listing cannot settle: correctness against
   the reference, the Task's own success criteria, and whether the fixed
   reproducibility conditions were respected.

The judgement is a language model, with the ways an LLM judge goes wrong closed
off in code, not just asked for in the prompt:

- **Self-report is not evidence.** An agent writing "CVRMSE was 11%" proves
  nothing; a criterion supported only by the submission's own prose is capped.
- **Missing is zero.** A deliverable the mechanical layer found absent cannot be
  argued upwards.
- **Every score quotes what it scored.** One that does not is capped as
  unsupported.
- **Calibrated anchors.** 0.0 / 0.25 / 0.5 / 0.75 / 1.0 are defined in words, so
  "good" means the same thing across Tasks and across runs.
- **Blind to the condition.** The grader is never told whether the Skill or the
  Detailed Instruction was present — knowing which arm it is scoring is the
  fastest way to manufacture the lift the benchmark exists to measure.

With no model configured the hub falls back to the contract check alone and says
plainly that it cannot tell a correct answer from a well-formatted wrong one.
`GET /api/benchmark/grader` reports which grader a hub is using.

`--agent` is the command that runs your agent; the prompt arrives as
`$BUILDRIX_PROMPT` and as `PROMPT.md` in the working directory. Without
`--agent` the run is a dry run: it exercises isolation, evaluation and upload,
produces no work, and is recorded privately so it cannot be mistaken for a
measurement.

### Integrity

- **Runs upload automatically** when execution finishes. There is deliberately
  no `benchmark submit` — a contributor who could choose which runs to send
  would send the flattering ones.
- **No partial groups.** A submission missing any condition is rejected whole;
  partial acceptance is itself a selection bias.
- **Scores are recomputed on the hub** from the per-run evidence.
- **A single-use nonce** is issued before the run, so a result cannot be minted
  after the fact or replayed.
- **Full provenance** is recorded: Task and version, Skill version and digest,
  model, harness, environment fingerprint, condition, run config, evaluator
  version, outputs and metrics.
- **Hidden Task assets stay hidden.** A pulled Task has no evaluation criteria,
  no reference outputs and no Detailed Instruction.

See [`spec/04-EVALUATION_PROTOCOL.md`](spec/04-EVALUATION_PROTOCOL.md).

---

## The official Buildrix Skill

The Buildrix skill guides an agent through search, download, contribution,
review, submission and revision using the shared CLI. It preserves original
human replies and resumes the same drafts as the website.

For tasks, it first saves the contributor's exact initial description before
showing criteria or helping revise it. It then logs local clarification
exchanges in a durable journal and automatically syncs them to the hub's private
history. Local exchanges and hub reviewer feedback are counted separately;
skill version and harness provenance are recorded as client-reported metadata.
See the [local interaction protocol](skills/buildrix/references/local-interactions.md).

```bash
cp -r skills/buildrix ~/.claude/skills/
buildrix auth login
```

Then work in words:

> "Find existing CFD tasks on Buildrix."
> "Help me turn this project into a Buildrix Task."
> "Turn my load forecasting workflow into a Buildrix Skill."
> "Validate and submit this Skill."
> "Find tasks compatible with this Skill and benchmark it."

Source: [`skills/buildrix/`](skills/buildrix/), with references for the
[Task format](skills/buildrix/references/task-format.md),
[Skill format](skills/buildrix/references/skill-format.md),
[benchmark](skills/buildrix/references/benchmark.md) and
[CLI](skills/buildrix/references/cli.md).

---

## Repository

| Path | What is in it |
|---|---|
| `buildrix/` | The CLI and package |
| `skills/buildrix/` | The official Buildrix Skill |
| `examples/skills/` | Example Skills to copy from |
| `examples/testcases/` | An example Task |
| `templates/` | Scaffolding used by `skill new` / `task new` |
| `spec/` | The format contracts and the evaluation protocol |

```bash
pip install -e ".[dev]"
python -m pytest
```

---

## Domains

Eight, closed. A Task uses one of them; a Skill may also use `general` for
cross-cutting tooling.

`performance-modeling` · `design-retrofit` · `operations-control` ·
`fdd-commissioning` · `occupants-comfort` · `forecasting-analytics` ·
`grid-integrated` · `data-semantics-twins`

```bash
buildrix domains --task
```

See [`spec/01-TAXONOMY.md`](spec/01-TAXONOMY.md).

---

## Licence

Apache-2.0. Contributed Tasks and Skills carry their own licence, defaulting to
CC-BY-4.0 for Tasks and Apache-2.0 for Skills. Submissions and their revision
history are retained and may be used in aggregate for research on the benchmark.
