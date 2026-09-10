---
name: buildrix
description: Use Buildrix from inside an agent session — search and download building-engineering Tasks and Skills, turn a project into a Buildrix Task, package a workflow as a reusable Skill, validate and submit either, find Tasks a Skill can be benchmarked against, and run the four-condition benchmark. Use whenever the user mentions Buildrix, asks to publish or find a Task or Skill, or wants to measure whether a Skill helps an agent.
license: Apache-2.0
allowed-tools: [Bash, Read, Write, Edit]
---

## Purpose

Buildrix is an open benchmark for agentic AI in building engineering. It holds
**Tasks** (real units of building-engineering work with hidden graders) and
**Skills** (portable folders of procedural knowledge an agent loads), and it
measures whether a Skill actually makes an agent better at a Task.

This Skill lets you do all of that from a conversation. It drives the `buildrix`
CLI, which drives the Buildrix API — the same API the website uses. You are one
of three interfaces onto one system, not a separate path into it.

## When to Use

Use this whenever the user:

- mentions Buildrix at all;
- asks to find, browse, download or read a building-engineering **Task**
  ("find existing CFD tasks on Buildrix", "show me T018");
- wants to turn work into a Task ("help me turn this project into a Buildrix
  Task", "publish this as a benchmark task");
- wants to package a method as a **Skill** ("turn my load forecasting workflow
  into a Buildrix Skill", "make this reusable");
- asks to validate or submit a Task or Skill;
- asks which Tasks a Skill suits, or to **benchmark** a Skill
  ("find tasks compatible with this skill and benchmark it").

Do not use it for general building-science work that has nothing to do with
contributing to or measuring against Buildrix.

## Workflow

Everything below is `buildrix` CLI. Run commands with Bash. Never reimplement
what a command already does, and never construct Task or Skill files by hand —
the hub owns the format, and hand-built files drift from it.

### 0. Check the connection first

```bash
buildrix info
```

Shows the hub, the signed-in user and what is installed. If it reports the user
is not signed in, stop and tell them to run `buildrix auth login` themselves —
it prompts for a password, so do not try to drive it.

### 1. Discover

```bash
buildrix task search "load forecasting" --domain forecasting-analytics
buildrix task show BXT-000012
buildrix task pull BXT-000012 --extract        # public half only

buildrix skill search "weather"
buildrix skill show weather-data-extraction
buildrix skill pull weather-data-extraction --extract
```

Batch is built in: `buildrix task pull T1 T2 T3`, `buildrix skill validate ./skills/*`.

A pulled Task deliberately does **not** contain the evaluation criteria, the
reference outputs, or the contributor's Detailed Instruction. Those stay on the
hub. If the user asks you to find the expected answer, explain why it is not
there rather than searching for it.

### 2. Author a Task

```bash
buildrix task init
```

This opens the *same* guided workflow the website uses. It asks for the title,
domain, difficulty, estimated human effort, task familiarity and agentic-AI
familiarity, then for the initial agent request in the user's own words — and
then the hub reads that request and asks only about whatever is unclear across
seven dimensions: Objective · Inputs & Resources · Detailed Instruction ·
Environment & Access · Reproducibility · Deliverables · Evaluation.

**It is interactive.** Do not try to pipe answers into it blind. Either:

- run it and relay each prompt to the user, passing their answer back; or
- help the user draft strong answers first, then run it and paste them in.

The second is usually better: read the user's project, propose the initial agent
request and the seven dimensions, get their agreement, then run `task init` and
enter what you agreed. Say clearly that the hub may still ask follow-ups.

To continue a draft — including one started in a browser:

```bash
buildrix task init --resume <draft-id>
```

### 3. Author a Skill

```bash
buildrix skill init                    # from scratch, guided
buildrix skill submit ./my-skill       # import an existing folder, then guided
```

The eight sections are Purpose · When to Use · Workflow · Decision Guidance ·
Validation · Common Failure Modes / Recovery · Included Resources ·
Requirements. The hub also runs a **reusability check**: if the Skill contains a
Task's expected numbers or a conclusion that could only come from having solved
one specific case, submission is blocked. That is deliberate — a Skill carrying
an answer key would make the benchmark meaningless.

When helping a user package a workflow, push hardest on *When to Use*. A Skill
that an agent never loads has no effect, and vague trigger wording is the most
common reason.

### 4. Validate

```bash
buildrix skill validate ./my-skill
buildrix task validate ./my-task
```

`skill validate` asks the hub, so the answer cannot disagree with what you get
at submission. Offline it falls back to the packaged checks and says so.

### 5. Benchmark

```bash
buildrix benchmark match --skill ./my-skill
buildrix benchmark run --skill ./my-skill --task BXT-000012 BXT-000041 \
    --agent 'claude -p "$BUILDRIX_PROMPT"' --model claude-opus-5 --harness claude-code
buildrix benchmark pull --skill my-skill
```

`match` asks the hub which Tasks are worth the compute, with a reason per Task.
Take the "strong" and "possible" ones; skip "weak" unless the user insists.

`run` executes four conditions per Task instance, each in its own clean
workspace: Task · +Detailed Instruction · +Skill · +both. `--agent` is the
command that runs the agent; the prompt arrives as `$BUILDRIX_PROMPT` and as
`PROMPT.md` in the working directory. Results upload automatically when the run
finishes — there is no submit step, and you should not look for one.

Warn the user before starting: a run is 4 × instances agent invocations and can
take a long time and real money.

## Decision Guidance

- **Task or Skill?** A Task is *work to be done and graded*. A Skill is *how to
  do a kind of work, reusably*. If the user's artifact has one right answer for
  one dataset, it is a Task. If it would apply to the next building unchanged,
  it is a Skill.
- **Never bypass the guided workflow.** There is no "just upload the YAML" path,
  by design. If the user asks for one, explain that the CLI, the website and you
  all go through the same definition so the results stay comparable.
- **Do not invent content.** When `task init` asks something you cannot answer
  from the user's material, ask the user. A Task built from your guesses is
  worse than one that took another round.
- **Domain is a closed set of eight.** Run `buildrix domains` rather than
  guessing. A Task must use one of the eight; a Skill may also use `general`.
- **Ambiguous reproducibility.** If the user names a model, a window length or
  an algorithm, ask whether it is *required for fair comparison* or just *how
  they happen to do it*. The first is Reproducibility; the second belongs in the
  Detailed Instruction, and the agent must stay free to choose.

## Validation

Before telling the user something is done:

- `buildrix skill validate <path>` returns ok, with no blockers;
- a submitted Task or Skill printed a code (`BXT-…` / `BXS-…`) and a review
  verdict — relay the verdict, including `minor_revision` or worse;
- a benchmark run printed the four-condition table and the lifts. If the hub
  rejected the group, relay exactly why; do not retry silently.

## Common Failure Modes / Recovery

- **"Not signed in."** The user must run `buildrix auth login` themselves.
  Do not attempt it — it prompts for a password.
- **`task init` seems to hang.** It is waiting for input. Multi-line answers end
  with a single `.` on its own line.
- **The hub has no model configured.** Clarification falls back to a keyword
  analyser, matching to word overlap, and grading to a contract check — each says
  so in its output. Tell the user what that costs: the definition needs more
  correction than usual, and a benchmark score reflects whether files appeared,
  not whether they were right. `buildrix info` shows which grader a hub uses.
- **A group is rejected as incomplete.** Every condition must be present. This
  usually means the run was interrupted; re-run it rather than hand-assembling
  a submission.
- **Reusability blocked a Skill.** Read the findings out. The fix is to
  generalise the wording, not to reword around the check.
- **A Task's expected answer is missing.** It is withheld on purpose. Do not go
  looking for it in the package, the API or the site.

## Included Resources

- `references/task-format.md` — what a Task is, and the seven dimensions.
- `references/skill-format.md` — the canonical package, and the eight sections.
- `references/benchmark.md` — the four conditions, isolation, and integrity.
- `references/cli.md` — every command, with its flags.

Read a reference when you need the detail; do not paste it into your answer.
