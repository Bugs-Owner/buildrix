# Benchmark execution and study protocol

Buildrix runs agents and engineering software on your workstation or compute
node. The hub stores published inputs, matches skills to tasks, grades submitted
evidence and serves results. It does not launch agents or simulations.

## Start a study

Install the Buildrix CLI and sign in to the hub. Install Codex and/or Claude Code
in the execution environment. Set `OPENAI_API_KEY` or `ANTHROPIC_API_KEY` for the
provider being tested. The runner deliberately does not copy personal CLI login
files, configuration, plugins, skills or memory. A CLI subscription login alone
does not configure this runner's API authentication.

Copy [study.example.yaml](../examples/benchmark/study.example.yaml), replace the
model IDs, published task codes and local skill path, then run:

```sh
buildrix benchmark prepare --manifest study.yaml --output bundle
buildrix benchmark batch --bundle bundle --output results
```

Preparation snapshots public task packages, instruction treatments, skills,
models, time limits, trial count and execution settings. It registers each group
with the hub before any agent starts. The author receives the same public input
package as every other benchmark runner; private reference answers stay on the
hub. Updating a task after preparation prevents grading against the new answer
key under the old snapshot.

`batch` saves evidence after every condition and automatically grades/uploads
complete groups. The console shows progress, not scores or agent output. The
local operator can still inspect all local evidence. This is deliberate
transparency, not a secrecy or anti-cheating mechanism.

For a single comparison using the same durable runner:

```sh
buildrix benchmark run --provider codex --model YOUR_MODEL_ID \
  --skill ./my-skill --task TASK_CODE --output experiment-001
```

Omit `--skill` for a task-only comparison. This runs one trial; use a study for
repeated measurements. `--agent` remains a legacy custom-shell adapter without
the built-in adapters' home isolation or durable study evidence; use `--provider`
for research runs. No command starts a paid model merely to test configuration.

## Experimental comparisons

| Condition | Task and inputs | Expert instructions | Skill |
| --- | --- | --- | --- |
| `task` | Yes | No | No |
| `task_instruction` | Yes | Yes | No |
| `task_skill` | Yes | No | Yes |
| `task_instruction_skill` | Yes | Yes | Yes |

Task-only studies use the first two conditions. Every declared task instance
and trial receives all applicable conditions. The seeded execution order is
shuffled to reduce order effects; it does not seed a provider's model sampling.
There is no resumed conversation, shared output directory or shared agent home
between conditions. Repeated independent calls are still subject to provider
nondeterminism, server-side prompt caching and model changes.

Compare within the same task version, skill version, model, harness version,
container image, budget and grader. The seed, snapshot hashes and study digest
are saved. Pin CLI versions in the image and use explicit model snapshot IDs
where available. A model alias does not guarantee fixed model weights.

Report baseline performance, instruction lift (`instruction - task`), skill
lift (`skill - task`), combined lift (`both - task`), and skill benefit beyond
instructions (`both - instruction`). Retain failures, timeouts and interrupted
attempts in the denominator. Do not average unrelated raw engineering metrics
or pool different models and protocols into a single scientific ranking.

## Match skills without new labels

```sh
buildrix benchmark match --skill ./my-skill
```

The existing matcher reads the skill's purpose/workflow and the tasks' actual
requirements. In a study pair, `match: true` selects its `strong` matches from
the service's candidate window (currently at most 120 published tasks, up to
50 returned). The complete match response, rationale and analyser identifier
are frozen in the bundle. No matches causes preparation to fail; it does not
silently choose unrelated tasks. Use explicit `tasks` for a curated coverage
set. Freeze selection before observing outcomes. Matching is a relevance
judgement, not evidence that a skill will help.

## Isolation and compute environments

`native` runs installed CLIs with a fresh home, caches, configuration locations
and subprocess. It strips inherited environment variables except OS launch
essentials and the tested provider's API key. It is suitable for development
with trusted packages. It does **not** hide the rest of the host filesystem,
enforce CPU/RAM limits, or prevent access to ancestor instructions.

For research runs, prefer a clean image with the tools and dependencies required
by the selected tasks. The runner supports:

* `docker`: a new container per condition, only its workspace mounted, no hub
  credentials or personal home, CPU/RAM/PID limits and dropped capabilities.
  Studies require an image reference pinned with `@sha256:...`.
* `apptainer`: a local SIF image hashed during preparation, fresh contained
  filesystem/PID/environment state, host home and configured host bind paths
  disabled, and a single workspace bind. Slurm enforces CPU/RAM allocations;
  the manifest's `cpus`/`memory_mb` are not enforced by this backend.

The image must have `/bin/sh`, a writable `/tmp`, the tested CLI on PATH and
the task toolchain. Run as a non-root user. Avoid baked-in personal settings,
skills, reference solutions or credentials. The runner creates an empty home
under `/tmp`. Docker images should have no custom ENTRYPOINT.

Provider network access remains enabled. Tasks prohibiting internet use need
an operator-managed egress proxy/firewall allowing only the provider API; this
runner does not claim to enforce that restriction. Native mode and containers
on participant-owned hardware are not remote attestation.

## Slurm and disconnected workers

Prepare on a machine that can reach the hub, then place the frozen bundle and
results directory on storage accessible to the job. Run one group at a time
per shard; multiple shards can run in a Slurm array. Use the same output directory
for every shard. [run.slurm](../examples/benchmark/run.slurm) is a starting point;
set the cluster's partition/account/resources and array size.

```sh
buildrix benchmark batch --bundle bundle --output results --offline \
  --shard-index 0 --shard-count 4
buildrix benchmark sync --output results
```

Offline here means no **hub** calls; the agent still needs its provider network.
Each shard processes jobs whose index modulo shard count equals shard index.
File locks prevent simultaneous workers from running the same job. Keep shard
count fixed during a study. Completed records are reused. A record left in
`started` state after interruption becomes `interrupted`, without an automatic
retry that could bias results. If the agent returns an error, its available
outputs are retained and graded alongside the failure status.

`sync` retries all pending groups, including ones whose grading or upload
failed. It checks for an existing hub receipt before retrying an upload.
Registration currently expires after seven days; finish and sync within that
window. Expired assignments retain their local evidence but cannot be uploaded
with a newly minted nonce. Start a new study and report the abandoned one.

## Evidence and reporting

Each job saves `group.json` and `measurements.csv`. Each condition saves its
prompt, raw JSONL transcript, stderr, `record.json` and complete regular output
files in `outputs.zip`. The bundle saves matching decisions and frozen inputs.
Keep these directories for the report; they are never mounted into container
workspaces. Protect the evidence as research data: an agent can put input data
or a provider credential into its own transcript or output.

Usage distinguishes input, output, cache-read and cache-write tokens. Claude's
provider-reported cost is saved when available. Codex cost remains `null` when
the CLI does not report it; it is not guessed from mutable pricing. Missing
usage is `null` in the usage object and CSV, not a measured zero. Tool counts
use each harness's event vocabulary and are not necessarily comparable across
harnesses. Wall time includes agent execution; host CPU/RAM utilization and
provider billing reconciliation are not currently collected.

The hub currently grades text excerpts (up to 8,000 bytes per file, 40 files)
against its reference/rubric and stores criterion scores and supporting evidence.
It does not execute a deterministic domain evaluator over the complete output
archive. Large tables, binary models and numerical simulation accuracy need a
separate task-specific evaluation of the saved outputs before publication of
scientific claims. Grading cost is separate from agent cost and is not included
in the runner's usage totals.

## What can be trusted

The hub validates complete comparisons, rejects duplicate records, atomically
consumes nonces, and verifies signed receipts against the submitted artifacts.
Receipts prevent changing the **hub's assessment** after grading. They cannot
prove that an agent generated the artifacts or that a participant did not
inspect a result, fabricate a transcript or abandon a poor run.

Results distinguish `community_reported`, `community_graded`, and
`operator_graded`. Only the server's administrator role can receive the last
label; a client flag cannot grant it. Operator grading still needs an audited
execution protocol before treating it as a trusted research result. Hiding
stdout, forbidding parameters and auto-uploading improve workflow consistency,
but cannot create a cheat-proof leaderboard on an untrusted computer.

For an official study, operate the workers yourself, freeze the protocol and
coverage, audit images, track abandoned jobs, and retain all evidence. Community
runs can expand exploratory coverage and suggest which comparisons to reproduce.

Adapter references: [Codex non-interactive execution](https://developers.openai.com/codex/noninteractive),
[Claude Code CLI](https://code.claude.com/docs/en/cli-reference),
[Apptainer execution options](https://apptainer.org/docs/user/latest/cli/apptainer_exec.html).
