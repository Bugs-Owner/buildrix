# Contribution commands

Human terminal workflow:

```sh
buildrix task develop
buildrix skill develop
buildrix task develop --resume DRAFT_ID
buildrix skill develop --resume DRAFT_ID
buildrix task revise TASK_CODE
buildrix skill revise SKILL_CODE
```

`init` remains an alias. `buildrix skill submit ./folder` imports a local
skill into the shared workflow. `buildrix task submit ./folder` can use its
prompt.md as a task description; inputs and outputs still need attaching.

Agent workflow: `buildrix KIND draft ACTION`, KIND = task or skill. Responses
are JSON. Use UTF-8 files for text and JSON so the shell does not alter them.
Read all returned errors, questions and validation blockers.

| Action | Arguments | Result |
|---|---|---|
| meta | | Current choices and section guidance |
| create | --data about.json | New draft |
| start-session | ID --context context.json --journal SESSION.jsonl | Register private local provenance |
| capture-initial | ID --text-file original.txt --assistance unassisted/assisted/unknown --journal SESSION.jsonl | Save original task input without review |
| log-local | ID --role human/assistant --purpose TYPE --text-file message.txt --journal SESSION.jsonl [--reply-to EVENT_ID] | Save and automatically sync one local exchange |
| sync-local | ID --journal SESSION.jsonl | Retry queued exchanges without duplicates |
| get | ID | Current state |
| patch | ID --data about.json | Edit About |
| describe | ID --text-file text.txt | Task description; skill instructions |
| answer / edit | ID --dimension KEY --text-file text.txt | Reviewed task reply / replacement |
| upload | ID --file PATH --data notes.json | Attach file |
| link | ID --data link.json | Task HTTPS link |
| asset-notes | ID --asset ASSET_ID --data notes.json | Task file notes |
| remove-file | ID --asset ASSET_ID | Remove attachment |
| review | ID [--dimension KEY] | LLM review; dimension is task-only |
| proposal | ID --dimension KEY --proposal-id ID --decision accepted/rejected | Decide a task suggestion |
| finalize | ID | Revised task |
| prompt | ID --text-file text.txt | Edit revised task |
| instructions | ID --text-file SKILL.md | Edit skill instructions |
| requirements | ID --data requirements.json | Skill environment metadata |
| package | ID --file FOLDER_OR_ZIP | Replace draft skill package |
| download | ID --out NEW_FILE.zip | Draft skill package |
| submit | ID --consent | Submit and report review |
| log | ID | Private input history |
| withdraw | ID | Withdraw unfinished contribution |

`buildrix KIND drafts` lists saved work. `history ID` and `withdraw ID`
are shortcuts. `revise CODE --json` reopens without launching a wizard.

Agent contributions use `--context context.json` at creation and
`--journal SESSION.jsonl` on all later draft actions. Journal actions require
the updated CLI; check `draft capture-initial --help` before starting. If these
commands are unavailable, update the CLI; do not substitute `draft describe`
for record-only initial capture. See [local logging](local-interactions.md).

Search/show/pull work on published contributions. Use an explicit download
directory. Drafts live on the hub: the same ID works on web, CLI and the agent
skill.
