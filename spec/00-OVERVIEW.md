# Buildrix v2 — design specification

Buildrix is an **agentic AI skill benchmark for building engineering**. It answers one
question with evidence: *does packaging domain expertise as an agent Skill make an AI
agent measurably better at real building-engineering work?*

Everything in this spec follows from that question.

## The four artifacts

| Artifact | What it is | Who makes it | Where it lives |
|---|---|---|---|
| **Skill** | A portable folder of procedural knowledge an agent loads at inference time | Contributor | Public registry |
| **Task** | One unit of real building-engineering work + a hidden, deterministic grader | Contributor (guided) | Public half in registry, grader private |
| **Run** | A *paired* execution of a task, with and without skills, on the contributor's machine | Anyone | Submitted to hub |
| **Result** | Server-side grade of a run, aggregated into the leaderboard | Hub | Public |

## Design principles

**Tasks come from real work, and their answers stay hidden.** Every task is an
executable unit carrying an instruction, its input data, and a reference answer that is
staged only after the agent has finished — never shipped with the question. A benchmark
whose answers travel with the task measures memorisation.

**Grading is evidence-driven, not impressionistic.** A result is scored against the
artifacts the agent actually produced, using the task's own metric. Self-reported numbers
are never trusted when Buildrix can recompute them.

**A skill benchmark without a matched control measures nothing.** Every run is paired:
the same task, model, harness and budget, executed with and without the skill. The
difference between the arms is the result; the arms are never compared across separate
runs.

**Negative transfer is a first-class result.** Skills sometimes make agents worse. Where
that happens it is reported as a headline number, not buried — a benchmark that only
surfaces improvements is an advertisement.

## What Buildrix adds

1. **A domain.** Building engineering is unusually well suited to deterministic grading:
   outputs are time series, energy totals, IDF files, compliance verdicts, and the field
   already has agreed error metrics (ASHRAE Guideline 14: NMBE, CVRMSE).
2. **Distributed execution.** Heavy compute (EnergyPlus, ResStock, LSTM training, the
   agent loop itself) runs on the contributor's machine. The server only grades. See
   `04-EVALUATION_PROTOCOL.md`.
3. **An intake loop that manufactures unambiguous tasks.** Humans submit vague tasks. A
   strict LLM reviewer plus a set of mechanical gates turns them into contracts.
   See `05-INTAKE_REVIEW.md`.

## Spec index

- `01-TAXONOMY.md` — the 8 domains
- `02-SKILL_FORMAT.md` — skill package contract
- `03-TASK_FORMAT.md` — task package contract
- `04-EVALUATION_PROTOCOL.md` — local runner, thin server, paired isolation, attestation
- `05-INTAKE_REVIEW.md` — multi-round guided submission
- `06-SITE_IA.md` — site structure and page-by-page content
