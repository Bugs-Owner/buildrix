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

## Prior art we deliberately borrow from

**Agents' Last Exam** (Berkeley RDI, arXiv:2606.05405) — 1K+ tasks over 55 sub-fields,
sourced from real projects that working professionals actually completed; every task is
an executable unit carrying an instruction, its input data, and a **hidden reference**
staged only after the agent finishes; grading is by **deterministic script**, not by an
LLM judging whether output looks right. ALE reports that ~3/4 of failures come from
missing domain knowledge and wrong approach, not broken tool use — which is precisely
the gap a Skill is supposed to close, and precisely why Buildrix exists.

**SkillsBench** (arXiv:2602.12670) — the first **paired** evaluation of agent skills:
the same tasks run under no-skill / curated-skill / self-generated-skill conditions
across many model-harness configurations. Headline: curated skills raise pass rate by
~16pp on average, but the effect ranges from +4.5pp to +51.9pp by domain, and a
meaningful minority of tasks get *worse* with skills. Two lessons we hard-code:
1. A skill benchmark that does not run a **matched control arm** measures nothing.
2. **Negative transfer is a first-class result**, not an embarrassment — report it.

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
