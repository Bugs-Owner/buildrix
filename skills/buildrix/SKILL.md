---
name: buildrix
description: Find, download, develop, submit and revise building engineering tasks on Buildrix. Use for the Buildrix task catalog or a saved Buildrix task draft. The CLI shares metadata, files, LLM review and private input history with the website.
license: Apache-2.0
---

# Buildrix contributions

Help the user turn real engineering work into a clear task.
Contributors submit tasks only. Use the Buildrix CLI and its shared draft API. Benchmark design and execution
are outside this contribution workflow.

## Connect and discover

Run `buildrix info` to check the configured hub. Search, show and public
downloads do not require login. If a write returns an authentication error,
ask the user to run `buildrix auth login`; do not collect their password.

```sh
buildrix task search "load forecasting"
buildrix task show TASK_CODE
buildrix task pull TASK_CODE --dir ./tasks --extract
```

Use returned IDs to tell apart tasks with the same name. Downloads
respect the account's access. Do not claim to have inspected a file or link
unless you actually have.

## Start or resume

For a human terminal session, use `buildrix task develop`. The wizard supports
earlier-step edits, saved drafts and LLM feedback. For an agent conversation, use the JSON commands below
instead of piping guessed answers into a wizard.

For agent-assisted contributions, first read [local interaction logging](references/local-interactions.md).
Start a journal and use `--journal SESSION.jsonl` on subsequent commands with a draft ID.
The CLI saves exchanges locally and syncs them automatically without a separate
permission question. This is private contribution history, not public page copy.

`buildrix task drafts` finds saved work, including web drafts. `draft get ID`
reads it. Resume the same journal when available; start a new session if the
harness changes. Keep the original draft ID and original input.

## Preserve the original input

For a new task, capture the initial human description **before any assistance**.
Do not show review criteria, dimensions, examples, suggested wording or a
checklist; do not ask technical follow-up questions or inspect project files to
help compose this first response. Delay reading task-format.md and `draft meta`
until it is saved. Ask only:

> Describe a real building engineering task you have completed, as clearly and fully as you would hand it to a teammate.

Log that prompt and the exact human reply using the local logging protocol.
`draft capture-initial` saves it on the hub without calling a reviewer. Wait for
`status: synced` before coaching. Preserve spelling, whitespace and omissions;
never replace this initial input with an agent-written version.

If the user already supplied their initial description, preserve that message
instead of asking for a replacement description. If coaching or criteria were already
given, record assistance as `assisted` (or `unknown` when uncertain); do not
claim it was unassisted. A resumed draft keeps its existing initial request.

After capture, read `draft meta` and the task reference.
Collect the same About fields as the website: title, domain, human effort,
complexity, task familiarity, AI-agent familiarity, whether AI helped, and
related stakeholders. `stakeholders` is a list of ids from `draft meta`
(at least one). If it includes `other`, also set `stakeholders_other` to who
they are. Save these in UTF-8 JSON and use
`draft patch ID --data about.json --journal SESSION.jsonl`. Do not invent
engineering facts, reference results, scores or familiarity.

Send later replies exactly as the user gave them. You may propose wording
within the user's request, but distinguish a proposal
from the user's original account. Never pass generated text as a verbatim human
response. The hub stores the original input and each revision, and prepares
separate polished display text.

## Develop a task

Read [task contribution](references/task-format.md).

```sh
buildrix task draft describe DRAFT_ID --text-file clarified-task.txt --journal SESSION.jsonl
buildrix task draft answer DRAFT_ID --dimension SECTION_ID --text-file reply.txt --journal SESSION.jsonl
```

Use the criteria to clarify locally first. Log each visible question, exact
human reply, proposed revision and meaningful file edit as it happens. Keep
agent-authored wording separate from human messages. Then send the clarified
task for hub review and resolve the returned questions.

Show the overall comment and one open section at a time. Log the feedback you
relay, collect missing facts, and send the revised answer for review. The hub incorporates
the clarification in context. Do not append the whole conversation or mark
sections clear yourself. Let the user go back, edit a section or file note,
or pause. Use the returned text and remaining questions.

Attach the real inputs, environment configurations and completed human outputs.
Evaluation is a scoring table, not another file upload: stages and scoring
dimensions with their values for 100 and 0 and weights, then what must be
delivered and a passing condition per dimension. Save it with
`draft rubric DRAFT_ID --data table.json`; see `references/task-format.md`.

### Human knowledge

After the reviewed sections are clear, collect Human knowledge on its own step.
It is what the user knows about doing the task well: steps, rules of thumb,
pitfalls, checkpoints, when to stop or retry, references, code. There is no
format. The reviewer never asks about it, so do not coach it into a checklist.
A few lines of text, or at least one file, is enough.

```sh
buildrix task draft knowledge DRAFT_ID --text-file knowledge.txt --journal SESSION.jsonl
buildrix task draft upload DRAFT_ID --file ./checklist.pdf --data knowledge-file.json --journal SESSION.jsonl
```

For a file, use dimension `detailed_instruction`, kind `knowledge` and a
`description`; no usage note is needed. Benchmarks compare agents on the task
alone and on the task plus this knowledge.

Once complete, run `draft finalize DRAFT_ID`. Show the revised task and files.
For an authorized wording change, use `draft prompt DRAFT_ID --text-file
revised-task.txt`.

## Submit and revise

When the user has authorized submission and agreed to history retention and
aggregate research use:

```sh
buildrix task draft submit DRAFT_ID --consent --journal SESSION.jsonl
```

Report the returned status and review result. Saved, queued, failed and accepted
are distinct outcomes; an unavailable review is not a pass.

```sh
buildrix task revise TASK_CODE --json
```

Continue with the returned draft ID. The published version stays intact while
editing. Resubmission keeps the ID, records a new version and runs review again.
Do not create a duplicate task to revise an existing one.

`buildrix task history DRAFT_ID` returns private original input logs for the
contributor and administrators. `withdraw DRAFT_ID` withdraws an
unfinished task while retaining its log. Leave an in-progress revision
saved to resume later.

See [command reference](references/cli.md) for the complete command surface.
