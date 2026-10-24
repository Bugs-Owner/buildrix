# Contribution commands

Contributors submit tasks. Human terminal workflow:

```sh
buildrix task develop
buildrix task develop --resume DRAFT_ID
buildrix task revise TASK_CODE
```

`init` remains an alias. `buildrix task submit ./folder` can use its
prompt.md as a task description; inputs and outputs still need attaching.

`buildrix auth register` creates an account. It also asks four short,
optional questions: occupation, career stage, age range and how often you use
AI agents. Press Enter to skip any of them.

Agent workflow: `buildrix task draft ACTION`. Responses are JSON. Use UTF-8
files for text and JSON so the shell does not alter them. Read all returned
errors, questions and validation blockers.

| Action | Arguments | Result |
|---|---|---|
| meta | | Current choices and section guidance |
| create | --data about.json | New draft |
| start-session | ID --context context.json --journal SESSION.jsonl | Register private local provenance |
| capture-initial | ID --text-file original.txt --assistance unassisted/assisted/unknown --journal SESSION.jsonl | Save original task input without review |
| log-local | ID --role human/assistant --purpose TYPE --text-file message.txt --journal SESSION.jsonl [--reply-to EVENT_ID] | Save and automatically sync one local exchange |
| sync-local | ID --journal SESSION.jsonl | Retry queued exchanges without duplicates |
| get | ID | Current state |
| patch | ID --data about.json | Edit About the task, including stakeholders |
| describe | ID --text-file text.txt | Task description |
| answer / edit | ID --dimension KEY --text-file text.txt | Reviewed reply / replacement |
| knowledge | ID --text-file knowledge.txt | Save Human knowledge (not reviewed) |
| rubric | ID --data table.json | Evaluation scoring table |
| upload | ID --file PATH --data notes.json | Attach file |
| link | ID --data link.json | HTTPS link for a large file |
| asset-notes | ID --asset ASSET_ID --data notes.json | Edit file notes |
| remove-file | ID --asset ASSET_ID | Remove attachment |
| review | ID [--dimension KEY] | LLM review |
| proposal | ID --dimension KEY --proposal-id ID --decision accepted/rejected | Decide a suggestion |
| finalize | ID | Revised task |
| prompt | ID --text-file text.txt | Edit revised task |
| reply | ID [--text-file reply.txt] [--file PATH] | Answer the submission review's open points |
| submit | ID --consent | Submit and report review |
| log | ID | Private input history |
| withdraw | ID | Withdraw unfinished task |

About the task (`create` / `patch`) takes `stakeholders`, a list of ids from
`meta` → `stakeholders`, such as `["engineer", "facility_manager"]`. Choose at
least one. When the list has `other`, add `stakeholders_other` with who they
are.

Human knowledge is stored under the dimension id `detailed_instruction`.
`edit --dimension detailed_instruction` saves it the same way as `knowledge`:
as written, with no review.

`buildrix task drafts` lists saved work. `history ID` and `withdraw ID`
are shortcuts. `revise CODE --json` reopens without launching a wizard.

Agent contributions use `--context context.json` at creation and
`--journal SESSION.jsonl` on all later draft actions. Journal actions require
the updated CLI; check `draft capture-initial --help` before starting. If these
commands are unavailable, update the CLI; do not substitute `draft describe`
for record-only initial capture. See [local logging](local-interactions.md).

Search/show/pull work on published tasks. Use an explicit download
directory. Drafts live on the hub: the same ID works on web, CLI and the agent
skill.
