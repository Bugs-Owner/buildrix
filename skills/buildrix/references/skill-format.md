# Skill contribution

Use the local-interaction protocol in SKILL.md; add the active
`--journal SESSION.jsonl` to all draft commands with a draft ID below.

Read `buildrix skill draft meta` for current options and file roles.
Collect name, concise description, domain, version, license, human effort,
complexity, task familiarity and AI-agent familiarity. Use `draft create`
or `draft patch` with JSON. Uploads into an existing draft retain its About
fields, matching the website.

Author SKILL.md with when to use the method, inputs, steps, decision points,
outputs and checks. Reference supporting files by their real relative paths.
Include only files the method needs.

```sh
buildrix skill draft package DRAFT_ID --file ./skill-folder
buildrix skill draft review DRAFT_ID
```

The folder must contain SKILL.md. A zip is also accepted. Replacing a package
replaces its draft files and invalidates the previous review. Instruction
versions remain in the private log.

For the file-by-file workflow:

```sh
buildrix skill draft instructions DRAFT_ID --text-file SKILL.md
buildrix skill draft upload DRAFT_ID --file helper.py --data role.json
buildrix skill draft review DRAFT_ID
```

Use `{"kind":"script"}` in role.json for scripts/. Get other roles from meta.
Upload the full folder for nested paths. `draft requirements ID --data
requirements.json` sets Python/packages/external_tools/network/gpu metadata.

Relay specific feedback; revise the actual files and review again. Do not
replace the contributor's method just to pass a section checklist.

`draft download ID --out candidate.zip` downloads the draft package to a new
file. `buildrix skill validate candidate.zip` runs package checks; LLM review
is still required.

`buildrix skill revise SKILL_CODE --json` reopens the same contribution,
retains the previous published package and prepares a new version. Continue
editing and submit for fresh review.
