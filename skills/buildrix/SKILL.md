---
name: buildrix
description: Find, download, develop, submit and revise building engineering tasks and reusable skills on Buildrix. Use for the Buildrix contribution catalog or a saved Buildrix draft. The CLI shares metadata, files, LLM review and private input history with the website.
license: Apache-2.0
---

# Buildrix contributions

Help the user turn real engineering work into a clear task or reusable skill.
Use the Buildrix CLI and its shared draft API. Benchmark design and execution
are outside this contribution workflow.

## Connect and discover

Run `buildrix info` to check the configured hub. Search, show and public
downloads do not require login. If a write returns an authentication error,
ask the user to run `buildrix auth login`; do not collect their password.

```sh
buildrix task search "load forecasting"
buildrix task show TASK_CODE
buildrix task pull TASK_CODE --dir ./tasks --extract
buildrix skill search "weather"
buildrix skill show SKILL_CODE
buildrix skill pull SKILL_CODE --dir ./skills --extract
```

Use returned IDs to distinguish contributions with the same name. Downloads
respect the account's access. Do not claim to have inspected a file or link
unless you actually have.

## Start or resume

For a human terminal session, use `buildrix task develop` or
`buildrix skill develop`. These wizards support earlier-step edits, saved
drafts and LLM feedback. For an agent conversation, use the JSON commands below
instead of piping guessed answers into a wizard.

For agent-assisted contributions, first read [local interaction logging](references/local-interactions.md).
Start a journal and use `--journal SESSION.jsonl` on subsequent commands with a draft ID.
The CLI saves exchanges locally and syncs them automatically without a separate
permission question. This is private contribution history, not public page copy.

`buildrix KIND drafts` finds saved work, including web drafts. `draft get ID`
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

After capture, read `draft meta` and the relevant contribution reference.
Collect the same About fields as the website: title/name, description for
skills, domain, human effort, complexity, task familiarity and AI-agent
familiarity; skills also need version and license. Save these in UTF-8 JSON and
use `draft patch ID --data about.json --journal SESSION.jsonl`. Do not invent
engineering facts, reference results, scores, license status or familiarity.

Send later replies exactly as the user gave them. You may propose wording or
help author skill files within the user's request, but distinguish a proposal
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
Evaluation is a scoring table, not another file upload: required deliverables,
scoring dimensions with bounds, weights and passing lines, and the user's own
values. Save it with `draft rubric DRAFT_ID --data table.json`; see
`references/task-format.md`.

Once complete, run `draft finalize DRAFT_ID`. Show the revised task and files.
For an authorized wording change, use `draft prompt DRAFT_ID --text-file
revised-task.txt`.

## Develop a skill

Read [skill contribution](references/skill-format.md). Help author the actual
SKILL.md and supporting files; preserve referenced relative paths.

```sh
buildrix skill draft package DRAFT_ID --file ./my-skill --journal SESSION.jsonl
buildrix skill draft review DRAFT_ID --journal SESSION.jsonl
```

Log the same local questions, human replies, proposed text and file changes for
skills. Show feedback one point at a time. Revise the files, upload to the same draft
and request review again. The reviewer evaluates the uploaded method; it does
not silently replace it with a generated skill.

## Submit and revise

When the user has authorized submission and agreed to history retention and
aggregate research use:

```sh
buildrix task draft submit DRAFT_ID --consent --journal SESSION.jsonl
buildrix skill draft submit DRAFT_ID --consent --journal SESSION.jsonl
```

Report the returned status and review result. Saved, queued, failed and accepted
are distinct outcomes; an unavailable review is not a pass.

```sh
buildrix task revise TASK_CODE --json
buildrix skill revise SKILL_CODE --json
```

Continue with the returned draft ID. The published version stays intact while
editing. Resubmission keeps the ID, records a new version and runs review again.
Do not create a duplicate contribution to revise an existing one.

`buildrix KIND history DRAFT_ID` returns private original input logs for the
contributor and administrators. `withdraw DRAFT_ID` withdraws an
unfinished contribution while retaining its log. Leave an in-progress revision
saved to resume later.

See [command reference](references/cli.md) for the complete command surface.
