# Guided intake — turning a vague idea into an admissible task

## The premise

People do not submit good tasks. They submit *"benchmark an agent on calibrating a
building model"* — real expertise, zero contract. The intake loop's job is to extract
the contract from the expert, one strict round at a time, and to keep every round.

The existing `review_agent.py` (v3, admissibility-over-scoring) is the right foundation
and stays. What is added here is **rounds, diffs, a completeness ledger, and mechanical
gates that the LLM cannot override**.

## The pipeline

```
D0 draft  ->  R1 review  ->  D1  ->  R2  ->  ...  ->  Dn complete
                                                       |
                                              mechanical gates G1..G9
                                                       |
                                              human verification
                                                       |
                                                    published (golden)
```

Every arrow is stored. A task's revision chain is a first-class object.

### Stage 1 — the first draft, deliberately low friction

Route 3 opens with five plain questions and nothing else:

1. What is the job, in your own words?
2. What does the person doing it start with? (files, data, a building)
3. What do they hand back when they are done?
4. How would you, the expert, know it was done correctly?
5. Roughly how long does this take you?

Free text. No YAML. No schema. Attach files if you have them. The point is to capture
expertise before the format scares it away — the format is *our* job.

### Stage 2 — the reviewer, strict by construction

Each round returns four things:

**a. Verdict** — `accepted` / `minor_revision` / `major_revision` / `rejected`, derived
from per-dimension statuses (`pass` / `concern` / `blocker`), never from a weighted
average. Kept from v3, which got this right: an LLM cannot defend 0.6 vs 0.7, but it can
defend "this is a blocker."

**b. Per-dimension findings.** The v3 dimension set, plus three new ones the task format
now makes checkable:

| Dimension | The question it asks |
|---|---|
| `is_real_task` | Is this genuine building-engineering work, not spam or a toy? |
| `task_clarity` | Could a competent engineer start without asking a question? |
| `deliverable_contract` | Are outputs specified to file, format, schema, unit level? |
| `well_posed_evaluation` | Are thresholds grounded in reference data or a reproducible protocol? |
| `freedom_declared` | **NEW** — is every choice that moves the number either free or pinned? |
| `anchor_coverage` | **NEW** — does every graded thing appear in the prompt, and vice versa? |
| `discrimination` | **NEW** — would the rubric fail a plausible wrong answer? |
| `inputs_sufficient` | Can the task be done from what is provided? |
| `domain_value` | Does passing it demonstrate real expertise? |
| `scope_honesty_safety` | No unauthorised data, no fabricated references |

**c. Concrete fixes.** 1–3 per non-passing dimension, each naming the exact offending
text and the specific repair. Not *"clarify the period"* but *"'recent weather' does not
name a period. Write: 2025-04-01 to 2025-04-30, local standard time."*

**d. A proposed rewrite.** The reviewer drafts the sharpened `prompt.md` and the missing
`TASK.yaml` fields as a diff the contributor can accept, edit, or reject. Accepting a
rewrite is recorded as such — it is a meaningful signal about where the expertise
actually came from.

Alongside every round, a **completeness ledger** shows the fields still missing, so the
contributor always sees distance-to-done rather than an opaque verdict.

### Stage 3 — round 2+ is diff-aware

Later rounds receive the previous review, the previous draft, and the diff. The reviewer
is instructed to check *whether each earlier finding was actually addressed*, and may not
raise new cosmetic issues once structural ones are resolved — otherwise reviewers
ratchet and contributors quit. Concretely: a dimension that passed in round *n* cannot
regress to `concern` in round *n+1* unless the relevant text changed.

### Stage 4 — gates the model cannot talk its way past

The reviewer's `accepted` only moves a task to *candidate*. Publication additionally
requires G1–G9 from `03-TASK_FORMAT.md` to pass mechanically, on the hub, on real files.
An LLM's opinion never publishes a task by itself.

### Stage 5 — human verification

A maintainer or a second domain expert confirms the reference is credible and the task
represents real work. Only then: `golden`.

## Three routes, one format

The same three routes serve both skills and tasks, and the reviewer runs on the server in
all three. Nothing is accepted through one route that would be rejected at another.

| Route | How it works | For whom |
|---|---|---|
| **1 · the package** | `buildrix task new <name>` → edit → `buildrix task check .` runs G1–G8 locally → `buildrix task submit .` uploads and prints the review | Anyone already working in a terminal. Nothing fails after sending, because the gates ran first. |
| **2 · upload** | Drop a `.zip` that already follows the format. The same validator runs server-side and the report comes back in the browser. | People who keep their tasks in their own repo. |
| **3 · step by step** | Six sections of plain questions, each with a real example in grey. The form writes `TASK.yaml`, `prompt.md` and the folder layout. | The domain expert with the knowledge and no interest in YAML. This is the route that needed the most design. |

### The six sections

Each field states why it is asked for, so nobody is filling in a form blind.

**A task**

| # | Section | Collects |
|---|---|---|
| 1 | Where it comes from | Title, domain, whose job it was, how long it took them |
| 2 | The job | The exact words the agent will read — this becomes `prompt.md` |
| 3 | What is given | Input files, and a description of what is in them |
| 4 | What comes back | Paths, formats, columns, units — the deliverable contract |
| 5 | How correctness is decided | The expert's own answer (kept private), what counts as right, and **three ways a wrong answer could still look right** |
| 6 | Ground rules | What is free, what is fixed, environment, time and token budget |

**A skill**

| # | Section | Collects |
|---|---|---|
| 1 | Identity | Name, domain, version, licence |
| 2 | What it does and when to use it | The one paragraph an agent reads before loading it |
| 3 | How it works | Inputs, then numbered steps with the code to run |
| 4 | Code and dependencies | Files, pinned packages, external tools, network hosts |
| 5 | Outputs | Exact paths, so a task can depend on them |
| 6 | Limits | Where it breaks, and where the method comes from |

Section 5 of the task form is what turns a description into a contract. Section 2 of the
skill form is what decides whether an agent ever loads the skill at all. Those two carry
the most explanatory text in the UI.

### Commands

```bash
buildrix skill  new | check | submit | status | install | list | remove
buildrix task   new | check | submit | status | get     | list
buildrix bench  run | submit | status | list
buildrix auth   login | logout | whoami
```

| Verb | What it does | Where |
|---|---|---|
| `new` | Scaffolds the folder layout | local |
| `check` | Runs every mechanical gate — the same code the server runs | local |
| `submit` | Uploads, then prints the checks and the reviewer's comments | server |
| `status` | Current verdict, round number, and what is still missing | server |
| `install` / `get` | Pulls a published skill, or a task's public half | server |

The web form and the CLI call the same endpoints and render the same report, so a
contributor can start in the browser and finish in the terminal, or the other way round.

### What comes back

Both surfaces show the same four things: the mechanical check results, the reviewer's
findings with the offending words quoted, a suggested rewrite, and the list of what is
still missing. In the terminal:

```
$ buildrix task submit ./ahu-fdd

  uploading...                  1.4 MB
  format ....................  pass
  anchors ...................  pass
  grader sanity .............  not run (no reference attached)
  reviewer ..................  major revision

  blocker  deliverables
    "a list of faults" is not a file
  blocker  correctness
    no reference to compare against

  status: draft · round 1 · revise and resubmit
  full report: buildrix task status ahu-fdd
```

## The revision corpus

Every round is retained: the text, the diff, the verdict, the per-dimension statuses,
the elapsed time, and whether a proposed rewrite was accepted. This gives Buildrix
something no other agent benchmark has: **paired task specifications of differing
quality, with identical hidden graders**.

The experiment that falls out of it: run D0 and Dn through the same runner against the
same grader. The gap measures how much agent failure is *specification ambiguity* rather
than *missing capability* — a confound every agent benchmark carries and none of them
quantify. It also cross-cuts the skill delta: if sharpening the prompt closes most of the
gap that skills close, that is a finding worth publishing.

Two practical notes on this:

- It needs no special presentation on the site. "See how this task was sharpened" is a
  legitimate, even attractive public feature — transparency about review is a selling
  point for contributors, and it makes the corpus a byproduct of a feature people want
  rather than something being harvested quietly.
- The submission terms should carry one line stating that submissions and their revision
  history are retained and may be used in aggregate for research on the benchmark. That
  is standard for any benchmark that publishes, it costs nothing, and it removes the only
  real risk in the plan.

## Call for skills

The old `challenges` feature is retired — as you predicted, a competitive research
audience will not post its good ideas. It is replaced by **Call for skills**: a
structured request for a capability that does not exist yet, tied to the taxonomy, with
a required "what would a good answer produce" field. Requests are cheap for the asker
and specific enough to act on. Existing challenge rows migrate here.
