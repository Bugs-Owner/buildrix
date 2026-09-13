# Skill packages

A skill contains SKILL.md and the supporting files its method needs.
SKILL.md describes when to use the skill, required inputs, the procedure,
outputs and checks. Link supporting files using their relative paths.

Common folders include `scripts/`, `references/`, `assets/` and `tests/`.
Include only folders and files your method uses.

Start with `buildrix skill develop`, or import an existing folder with
`buildrix skill submit ./my-skill`. The hub collects contribution metadata
and reviews the uploaded instructions and files.

For local scaffolding, use `buildrix skill new my-skill`.
Package validation is available through `buildrix skill validate ./my-skill`;
it does not replace submission review.

See the [skill contribution guide](../skills/buildrix/references/skill-format.md)
for uploads, file roles and revisions.
