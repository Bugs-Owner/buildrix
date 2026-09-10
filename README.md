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
├── task       search · show · pull · init · validate · submit · archive
├── skill      search · show · pull · init · validate · submit · archive
├── benchmark  match · run · pull
└── auth · domains · info · env · config
```

Two motions, and they mean the same thing for a Task and for a Skill:

```
Discover:  search → show → pull
Develop:   init → validate → submit
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

## Contribute a Task

```bash
buildrix task init
```

Collects the title, domain, difficulty, estimated human effort, task familiarity
and agentic-AI familiarity — then asks the one question that matters:

> **How would you ask an AI agent to work on this task?**

Write it the way you actually would. That text is stored verbatim and never
rewritten. The hub reads it and reports the state of each of seven dimensions:

| Dimension | The question it answers |
|---|---|
| Objective | What should the agent accomplish? |
| Inputs & Resources | What does it receive? |
| Detailed Instruction | How would an experienced human work through this? |
| Environment & Access | What tools, software and compute may it use? |
| Reproducibility | What must be fixed for results to be comparable? |
| Deliverables | What comes back, with what file names and columns? |
| Evaluation | How is success decided? |

Each carries a state — `clear` · `needs_clarification` · `not_provided` ·
`not_applicable` — never a score. You are asked **only** about what is unclear,
so a detailed request can go straight to final review and a vague one takes
several rounds. Every question, answer and revision is kept.

Two separations the format depends on:

- **The Detailed Instruction is not the prompt.** It is a required Task artifact
  and it is deliberately excluded from the canonical prompt, because the
  benchmark runs `Task` and `Task + Detailed Instruction` as separate conditions.
- **Reproducibility is not the solution method.** A model or a window length you
  name is only a Task condition when the comparison would be unfair without it.
  Otherwise it belongs in the Detailed Instruction and the agent stays free to
  choose. When it is ambiguous, you are asked.

See [`spec/03-TASK_FORMAT.md`](spec/03-TASK_FORMAT.md) and
[`examples/testcases/`](examples/testcases/).

---

## Contribute a Skill

```bash
buildrix skill init                 # from scratch, guided
buildrix skill submit ./my-skill    # import an existing folder, then guided
buildrix skill validate ./my-skill
```

### The package

```
my-skill/
├── skill.yaml       Buildrix metadata and technical requirements
├── SKILL.md         the agent-facing Skill itself
├── scripts/         optional — code the agent runs
├── references/      optional — long-form docs, loaded on demand
├── examples/        optional — worked examples
├── assets/          optional — templates, lookup tables, small data
└── tests/           optional — runnable checks
```

Only `skill.yaml` and `SKILL.md` are required. A Skill may be pure instruction,
or may carry knowledge, workflows, scripts, tools, models, references, decision
logic, validation procedures and error recovery.

Metadata lives in exactly one place each, so nothing can drift:

```yaml
# SKILL.md frontmatter — the open Agent Skills standard, all a host reads
---
name: load-forecasting
description: >-
  Fits and evaluates short-horizon building load forecasts from meter and
  weather data. Use when a user asks to forecast building electricity demand
  or benchmark a load-prediction model.
license: Apache-2.0
---
```

```yaml
# skill.yaml — everything Buildrix-specific, and nowhere else
schema: skill/2.0
name: load-forecasting
version: 1.2.0
domain: forecasting-analytics
determinism: seeded
requires:
  python: ">=3.11,<3.14"
  packages: ["pandas==2.2.2"]
  external_tools: []
  gpu: false
network: []
```

`name` is the one field in both, and validation fails if they disagree. A legacy
package with Buildrix fields under frontmatter `metadata:` is still read
correctly; submitting through Buildrix writes the canonical `skill.yaml`.

### SKILL.md

```markdown
## Purpose                            what capability this gives an agent
## When to Use                        the phrases a user would actually type
## Workflow                           numbered steps, each with its command
## Decision Guidance                  the judgement calls, with thresholds
## Validation                         how the agent checks its own result
## Common Failure Modes / Recovery    what breaks, and what to do
## Included Resources                 the bundled files, by relative path
```

The first three are required. `When to Use` is the highest-leverage section:
most Skills fail because an agent never loads them.

### The reusability check

The hub judges whether a Skill is genuinely reusable or is one Task's answer
written out longhand. A `hardcoded_answer` verdict — an expected output value, a
reference file's contents, a conclusion that could only come from having solved
a specific Task — **blocks submission**. A Skill carrying an answer key would
make the benchmark meaningless.

See [`spec/02-SKILL_FORMAT.md`](spec/02-SKILL_FORMAT.md) and
[`examples/skills/`](examples/skills/).

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

One Skill teaches an agent to use all of the above — searching, authoring,
validating, submitting, matching and benchmarking — by driving this CLI rather
than reimplementing anything.

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
