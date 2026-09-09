# Buildrix

**An open skill framework and benchmark for building-engineering AI agents.**

Buildrix exists to answer one question with evidence: *does packaging
building-engineering expertise as an agent skill make an agent measurably better
at real work?*

Skills are plain [Agent Skills](https://agentskills.io) folders, so they work in
Claude Code, OpenAI Codex, Gemini CLI, or anything else that reads the standard.
Tasks are real professional work with hidden, scripted graders. Every benchmark
run is **paired**: the same model, the same harness, the same budget, run once
with the skills and once with none. The difference between the two arms is the
result.

Hub: **[buildrixhub.onrender.com](https://buildrixhub.onrender.com/)**

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

One shape for everything: `buildrix <noun> <verb>`. The verbs mean the same
thing for a skill and for a task.

```
buildrix skill  new | check | submit | status | install | list | remove
                pull | update | dev | search | browse | delete
buildrix task   new | check | submit | status | get | list
buildrix bench  run | submit | status | list
buildrix auth   login | logout | whoami | register
buildrix domains [--task]
buildrix info
buildrix env    info | setup | clean
buildrix config hub <url>
```

| Verb | What it does | Where it runs |
|---|---|---|
| `new` | Scaffolds the folder layout | local |
| `check` | Runs every mechanical gate — the same code the hub runs | local |
| `submit` | Uploads, then prints the checks and the reviewer's comments | server |
| `status` | Current verdict, round number, and what is still missing | server |
| `install` / `get` | Pulls a published skill, or a task's public half | server |

The web forms on the hub call the same endpoints and render the same report, so
you can start in the browser and finish in the terminal, or the other way round.

The older flat commands (`login`, `install`, `push`, `browse`, …) still work and
print a one-line note pointing at the new form.

---

## Write a skill

```bash
buildrix skill new chiller-plant-mpc
# write the description, put your code in scripts/, a test in tests/
buildrix skill check ./chiller-plant-mpc
buildrix skill submit ./chiller-plant-mpc
```

```
skill-name/
├── SKILL.md            frontmatter + the seven required sections
├── requirements.txt    pinned dependencies
├── scripts/            your code
├── references/         long-form docs, loaded on demand
├── assets/             templates, lookup tables, small data
├── tests/              runnable checks
└── NOTES.md            what went wrong and what fixed it
```

A Buildrix skill is a valid Agent Skill **first**. Everything Buildrix needs on
top of the open standard lives inside the frontmatter's `metadata:` block, which
hosts ignore, so nothing here stops the folder working elsewhere:

```yaml
---
name: chiller-plant-mpc
description: >-
  Fits a grey-box thermal model of a chiller plant from operating data, then
  solves a day-ahead setpoint schedule under a price signal. Use when a task
  involves plant-level optimisation, MPC, or shifting cooling load in time.
license: Apache-2.0

metadata:
  buildrix_schema: "skill/2.0"
  version: "0.1.0"
  domain: operations-control
  requires: {python: ">=3.11,<3.14", packages: ["cvxpy==1.5.3"]}
  network: []                 # every host you contact; [] means offline
  determinism: deterministic  # checked, not taken on trust
---
```

`buildrix skill check` enforces eight rules: structure, frontmatter, a
description that says *when* to use the skill, the seven required sections, a
5,000-token body budget, no absolute paths or secrets, a 25 MB cap, and tests
that pass. With `--determinism` it runs the tests twice and compares.

Then the hub's reviewer reads the prose — the description and the limits, because
those decide whether an agent finds the skill and whether it misuses it.

---

## Write a task

```bash
buildrix task new ahu-fdd-fortnight
# write prompt.md, put your own answer in grader/reference/
buildrix task check ./ahu-fdd-fortnight
buildrix task submit ./ahu-fdd-fortnight
```

```
task-name/
├── PUBLIC  — goes to every runner
│   ├── TASK.yaml           the contract
│   ├── prompt.md           the only text the agent reads
│   ├── inputs/             what the agent starts with
│   ├── env/requirements.txt
│   ├── collect.py          workspace -> submission bundle
│   └── provenance.md
└── PRIVATE — stays on the server
    └── grader/
        ├── grade.py        grade(bundle, reference) -> {"overall": ...}
        ├── reference/      your own answer
        └── mutations/      three wrong-but-plausible answers
```

A task is a contract, not a description. Two rules make that mechanical:

- **Every check carries a phrase copied from `prompt.md`, word for word.** If the
  phrase is not in the prompt, the task does not publish. You cannot grade what
  you did not ask for.
- **Anything you tell the agent to do that no check covers gets flagged**, so
  either add a check or cut the sentence.

`buildrix task check` runs the gates against your own files:

```
  schema .................... pass   CONTROLS
  prompt .................... pass   45 words
  deliverables .............. pass   2 file(s)
  anchors ................... pass   3/3 found
  prompt coverage ........... pass
  gold (G3) ................. pass   1.00
  floor (G4) ................ pass   0.00
  discrimination (G5) ....... pass   3 case(s) fail as intended
  repeatable (G6) ........... pass

  verdict: ready to submit
```

G3 to G6 are the interesting ones. Your own answer has to score exactly 1.00, an
empty folder has to score 0.00, each wrong-but-plausible case you supplied has to
score below the pass mark, and grading the same folder twice has to give the same
number. G5 is the one that matters most: it proves the grader can tell a good
answer from a plausible bad one.

**There is no difficulty field.** Difficulty is the measured pass rate of an
agent working with no skills at all, over at least twenty trials on two model
setups, written back by the server with its confidence interval and trial count.

---

## Domains

Eight, closed, the same in the CLI, the server and the site:

| id | Domain |
|---|---|
| `performance-modeling` | Building Performance Modeling & Simulation |
| `design-retrofit` | Design, Retrofit & Decarbonization |
| `operations-control` | Building Operations, Control & Optimization |
| `fdd-commissioning` | Fault Detection, Diagnostics & Commissioning |
| `occupants-comfort` | Occupants, Comfort & Indoor Environmental Quality |
| `forecasting-analytics` | Energy Forecasting & Performance Analytics |
| `grid-integrated` | Grid-Interactive & Integrated Energy Systems |
| `data-semantics-twins` | Building Data, Semantics & Digital Twins |

Plus `general` for cross-cutting tooling — a skill may use it, a task may not.
`buildrix domains` prints the list; `--task` shows only the eight.

---

## The benchmark

Heavy compute runs on your machine. The server only grades.

```
YOUR MACHINE                                    SERVER
fetch the public task pack + a run token  --->  token issued, pack served
build the pinned environment
run arm A: agent, no skills        ) paired,
run arm B: agent, with skills      ) randomised order
collect.py -> bundle under 50 MB
sign the manifest, upload                 --->  verify, load the hidden grader,
                                                score in seconds, store the run
```

`buildrix bench` is not in this release. When it lands, one command runs both
arms — there is no flag for running only the treatment, and a run without its
control arm is refused on upload. Fairness is enforced by making the honest path
the only path.

Results are reported as the gap in pass rate with McNemar's exact test on paired
per-task outcomes, normalised gain, cost per task, and the count of tasks that
got **worse** with skills.

---

## Specification

The full written spec — skill format, task format, the run protocol, the review
loop, the domain taxonomy — lives alongside this repo in `spec/`:

| File | Covers |
|---|---|
| `00-OVERVIEW.md` | The four artifacts and the prior art we borrow from |
| `01-TAXONOMY.md` | The eight domains |
| `02-SKILL_FORMAT.md` | `skill/2.0` |
| `03-TASK_FORMAT.md` | `task/2.0` and the nine gates |
| `04-EVALUATION_PROTOCOL.md` | Local runner, thin server, paired isolation |
| `05-INTAKE_REVIEW.md` | The three submission routes and the reviewer |
| `06-SITE_IA.md` | The hub's structure |

---

## Prior art

**Agents' Last Exam** ([arXiv:2606.05405](https://arxiv.org/abs/2606.05405)) —
executable tasks from real professional work, hidden references, scripted
grading. Their finding that most agent failures come from missing domain
knowledge rather than broken tool use is the reason Buildrix exists.

**SkillsBench** ([arXiv:2602.12670](https://arxiv.org/abs/2602.12670)) — the
paired design, and the finding that skills help by wildly different amounts by
domain and sometimes make things worse. Both are reported here as first-class
results.

---

Apache-2.0.
