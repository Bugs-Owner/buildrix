# Private local contribution history

Use this protocol whenever this skill helps develop or revise a task or skill.
Log visible Buildrix contribution exchanges only: the neutral initial prompt,
the contributor's original response, local clarification questions and replies,
proposed revisions, accepted changes, meaningful artifact edits, and hub
feedback relayed to the user. Send them automatically to the configured hub as
part of the contribution workflow; do not add per-message permission prompts.
Honor the user's scope and the harness's execution permissions. Do not upload
unrelated conversations, credentials or hidden reasoning, and do not scan a
harness's global chat history. These instructions do not submit a publication
without the user's existing authorization for that action.

The hub's normal LLM review remains required. Preserve the distinction between
human input, agent proposals and hub feedback. Record only known source metadata;
leave uncertain values unknown.

## Start

Save context.json with the actual harness and model when known; leave unknown
values empty. Do not infer a model from a filename or a default configuration.

```json
{
  "interface": "agent",
  "buildrix_skill_used": true,
  "skill_version": "1.2.0",
  "harness": "",
  "model": ""
}
```

For a new task, about.json can initially be `{}`. Create the draft without
presenting the criteria to the user; collect About details after initial capture.

```sh
buildrix task draft create --data about.json --context context.json
buildrix task draft start-session DRAFT_ID --context context.json --journal SESSION.jsonl
```

For a skill, preserve the user's own name/description in about.json when
creating it, then start the same journal with `skill` in place of `task`. Log
the user's original skill-development request as `role: human, purpose: message`
before helping author it. No task `capture-initial` command is needed for skills.

Keep the journal outside any skill/package folder that will be published.
Reuse it across pauses. The header binds it to one hub, draft and session;
context cannot change in place. A new harness/model gets a new journal on the
same draft. Use a single writer per journal.

## Initial task input: no coaching yet

Save the neutral question from SKILL.md to initial-question.txt, display that
same question to the user, and log it. Save the user's exact reply to
initial-request.txt; do not fix grammar or expand it.

```sh
buildrix task draft log-local DRAFT_ID --journal SESSION.jsonl --role assistant --purpose initial_prompt --text-file initial-question.txt
buildrix task draft capture-initial DRAFT_ID --journal SESSION.jsonl --text-file initial-request.txt --assistance unassisted
```

This saves the immutable initial request without an LLM call. Only after
`status: synced` may you expose guidance or help clarify. If a description was
already provided before this workflow, use that exact message. Use
`--assistance assisted` if the user had already received coaching, or `unknown`
if its origin is unclear. Do not replace a description that has already been given.
For an existing draft, read its saved input and continue; never overwrite it.

## Log the local conversation as it happens

Use a separate UTF-8 source file for each actual visible message. Before
processing a new human answer or editing the next artifact, record the exchange.
`log-local` writes and flushes the journal before attempting automatic upload.
Keep the returned event_id to link an answer to its question.

```sh
buildrix task draft log-local DRAFT_ID --journal SESSION.jsonl --role assistant --purpose clarification_question --text-file question.txt --dimension SECTION_ID
buildrix task draft log-local DRAFT_ID --journal SESSION.jsonl --role human --purpose clarification_answer --reply-to QUESTION_EVENT_ID --text-file reply.txt --dimension SECTION_ID
buildrix task draft log-local DRAFT_ID --journal SESSION.jsonl --role assistant --purpose revision_proposed --text-file revised-text.txt
```

Use `revision_accepted` for an actual human acceptance, `artifact_edited` for an
agent's concrete file change (include relative path and exact changed text or
diff), and `hub_feedback` for the feedback you actually relay. Use `message`
for relevant exchanges that do not fit those roles. Do not fabricate an answer
or acceptance to complete a pair. The same protocol uses `skill` for skills.
Upload the actual files with the normal package/upload commands as well.

Add `--journal SESSION.jsonl` to **every subsequent draft command**, including
file uploads, description edits, review, finalization and submission. The CLI
flushes queued exchanges before taking the action and attaches source metadata
to its hub event. Original human text and an agent's synthesis must have separate
local events. A synthesis can be sent with `draft describe` after initial
capture; it cannot replace the original input.

## Delivery and retry

`status: synced` means the hub acknowledged the events. `status: queued` means
the local journal is retained but upload failed; report it accurately. Retry:

```sh
buildrix task draft sync-local DRAFT_ID --journal SESSION.jsonl
```

Reuse the existing journal and IDs; do not re-log the same message merely to
retry delivery. A lost acknowledgment is safe to retry without double counting.
Stop repeated retries after the same error and retain the journal to resume
when connectivity/authentication is restored. Do not coach before the initial
capture is acknowledged, or call a hub review/final submission while sync is
failing. No extra approval is needed to retry the authorized history upload.

The private `draft log` / `history` API returns the contribution history to its
contributor and administrators. The skill records exchanges through this protocol;
the CLI does not automatically read a third-party harness's conversations.
