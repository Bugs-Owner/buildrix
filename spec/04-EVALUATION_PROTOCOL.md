# Evaluation protocol — heavy work local, grading on the hub

## The constraint

The hub runs on a small instance. EnergyPlus batches, ResStock sampling, LSTM training
and the agent loop itself must never touch it. But the reference answers must never
leave it, or the benchmark is worthless.

Both constraints are satisfied by cutting at the same seam the task format already cuts:

```
CONTRIBUTOR MACHINE                                HUB
─────────────────────────────────────────────      ─────────────────────────────
fetch public task pack            ───────────>   nonce issued, pack served
build pinned environment
run Arm A: agent, NO skills       ) paired,
run Arm B: agent, WITH skills     ) interleaved
collect.py  ->  bundle (<= 50 MB)
sign manifest
upload bundle + manifest          ───────────>   verify manifest & fingerprints
                                                 stage private grader + reference
                                                 grade.py  (seconds, pandas-scale)
                                                 store run, update leaderboard
                             <───────────────    per-criterion scores + evidence
```

The hub's whole job is a schema check, a hash check and a few dataframe comparisons.
That is a $7/month workload no matter how many EnergyPlus-years the community burns.

## The runner

```bash
buildrix bench run --suite core-v1 \
                   --model claude-opus-5 \
                   --harness claude-code \
                   --skills weather-data-extraction,heat-wave-identification \
                   --trials 3
```

One command runs **both arms**. There is no flag to run only the treatment arm, and
there is no way to hand-assemble a submission — a run without its matched control is
rejected on upload. This is the single most important design decision in the protocol:
fairness is enforced by making the honest path the only path.

### Per trial

1. Draw arm order from the trial seed (order is randomised; a fixed A-then-B order
   would confound with API-side drift over the run).
2. **Arm A — control.** Fresh workspace. Zero Buildrix skills on disk. Host skill
   directory redirected to an empty temp dir so ambient user skills cannot leak in.
3. **Arm B — treatment.** Byte-identical workspace, plus the declared skill set.
4. Everything else identical and asserted identical: model id, harness version,
   temperature/seed, `budget` (wall-clock, tokens, tool calls), network allowlist,
   allowed tool set, staged `inputs/`, environment fingerprint.
5. Each trial gets a clean container (or venv + temp dir when Docker is absent). No
   caches shared between arms or trials — including skill-written state such as
   `NOTES.md`, which would otherwise carry learning from arm to arm.
6. `collect.py` reduces each workspace to a bundle; transcripts are hashed.

### The isolation assertion

The runner computes `env_fingerprint = sha256(os, cpu, python, package set, harness
version, model id, budget, task pack digest, network policy)` for both arms and refuses
to package the submission unless the two fingerprints are **identical** and the only
declared difference is `skills_digest`. That assertion, and its inputs, ship inside the
manifest so the hub re-checks it.

## Attestation

1. **Before** the run, the runner requests a `run_nonce` bound to `(user, suite, model,
   harness, expiry)`. Nonces are single-use and short-lived; you cannot mint a run
   after the fact or replay a good one.
2. The manifest records: nonce; task-pack and skill digests; harness and buildrix
   versions; model id; per-trial wall-clock, token counts and tool-call counts; arm
   order seed; a Merkle root over the trial transcripts; the machine fingerprint.
3. Upload = bundles + manifest (+ transcripts, optional but see trust tiers).
4. The hub verifies nonce validity, bundle hashes against the manifest, both arms
   present for every trial, budgets respected, fingerprint equality, and timestamps
   inside the nonce window. Any failure rejects the whole submission — never just the
   offending trial, because partial acceptance is itself a selection bias.

## Evidence level — shown on every leaderboard row

| Level | What it means |
|---|---|
| `self-reported` | Manifest verified, transcripts not attached. Default. |
| `transcripts` | Full trajectories uploaded; anyone can audit the run. |
| `reproduced` | ≥ 2 independent submitters, overlapping confidence intervals. |
| `server-verified` | Maintainers re-ran it themselves. |

The leaderboard defaults to `reproduced` and above; a toggle shows everything.

**We say this plainly in the docs:** a self-reported run is not tamper-proof. What makes
the number trustworthy is not the client, it is (a) the paired design — faking a delta
means faking *both* arms coherently, including token counts and timings, (b) attestation
binding the run to a pre-issued nonce, (c) transcripts being auditable, and (d) spot
reproduction. Claiming more than that would be dishonest, and a benchmark that
overclaims its integrity gets torn apart in review.

## Metrics

Per suite, per model-harness configuration:

- **Pass rate**, arm A and arm B, with bootstrap CI over tasks.
- **Δ pass rate** (the headline), with a **paired** significance test — McNemar's exact
  test on per-task paired outcomes. Paired data demands a paired test; an unpaired
  t-test over two independent groups is the wrong statistic and reviewers will say so.
- **Normalised gain** `Δ / (1 − baseline)` — how much of the available headroom the
  skills actually captured. Comparable across domains with different baselines.
- **Negative transfer**: the count and the list of tasks where skills *hurt*. SkillsBench
  found this on 16 of 84 tasks; it is a real phenomenon and we surface it as a headline
  number rather than burying it.
- **Cost**: tokens, wall-clock and estimated $ per task, both arms. A skill that adds
  6 points of pass rate for 3× the tokens is a different product from one that adds 6
  points for free.
- **Context efficiency**: Δ pass rate per 1k tokens of skill context.
- Per-domain breakdown for all of the above — this is what the leaderboard radar shows.

## Suites

A **suite** is a frozen, versioned list of task ids + the model/harness matrix.
`core-v1` is the headline. Suites are immutable once published; new tasks land in
`core-v2`. Without this, leaderboard rows from different weeks are not comparable.

## Server-side cost control

- Bundle cap 50 MB (gzip), rejected above.
- Grading is queued, one worker, few-second jobs.
- `llm_judge` calls are the only external spend; capped per criterion, cached by bundle
  hash, and a task with no prose deliverable makes zero LLM calls.
- Transcripts are stored as compressed blobs in object storage, not in the database.

## Reference implementation status

`buildrixhub/app/services/benchmark_runner.py` currently assumes the *server* executes
the agent. That inverts under this spec: the module becomes `grading_service.py` (stage
grader, run checks, persist), and the execution path moves into the `buildrix` package
as `buildrix.bench`. The rubric-weighting code carries over almost unchanged.
