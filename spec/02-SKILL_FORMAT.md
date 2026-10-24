# Skill packages

The website no longer takes skill contributions. Contributors submit tasks
only. This page describes the skill folder format for local use and for older
skills.

A skill contains SKILL.md and the supporting files its method needs.
SKILL.md describes when to use the skill, required inputs, the procedure,
outputs and checks. Link supporting files using their relative paths.

Common folders include `scripts/`, `references/`, `assets/` and `tests/`.
Include only folders and files your method uses.

For local scaffolding, use `buildrix skill new my-skill`.
Package validation is available through `buildrix skill validate ./my-skill`.
