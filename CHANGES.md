# Changes

## 0.3.0 - September 2026

The v2 formats, and one command shape for everything.

### Commands

`buildrix <noun> <verb>`, with the verbs meaning the same thing for both nouns:

```
buildrix skill  new | check | submit | status | install | list | remove | ...
buildrix task   new | check | submit | status | get | list
buildrix bench  run | submit | status | list        (stub in this release)
buildrix auth   login | logout | whoami | register
```

`check` is local and runs exactly the code the hub runs; `submit` and `status`
are the only commands that need the network. Every flat command from 0.2
(`login`, `install`, `push`, `browse`, ...) still works and prints a one-line
note pointing at the new form.

### Formats

- **`skill/2.0`** — a valid Agent Skill first: everything Buildrix needs lives
  under the frontmatter's `metadata:` block, and no top-level keys are invented.
  Seven required sections. `config.yaml` is gone, because two files holding the
  same metadata always drift.
- **`task/2.0`** — what 0.2 called a test case. Public half (TASK.yaml,
  prompt.md, inputs/, env/, collect.py) and private half (grader/, reference/,
  mutations/). Every check carries a phrase copied from the prompt, word for
  word, and the checker verifies it is really there.
- **Difficulty is gone as a field.** It is the measured no-skill pass rate,
  written back by the server with its confidence interval and trial count.

### New modules

| Module | What it does |
|---|---|
| `buildrix/domains.py` | The eight domains, in one place. Legacy ids map forward. |
| `buildrix/spec.py` | Every limit the checkers enforce, as a named constant. |
| `buildrix/report.py` | One report format for local checks and server reviews. |
| `buildrix/checks/skill.py` | The eight skill rules, including a determinism double-run and a scan for task answers. |
| `buildrix/checks/task.py` | The gates, including G3 gold = 1.00, G4 empty = 0.00, G5 every wrong-but-plausible case fails, G6 repeatable. |

### Hub client

`submit_skill`, `skill_review`, `submit_task`, `task_review`, `list_tasks` and
`domains`. Task calls try `/api/tasks` and fall back to `/api/testcases`, so the
CLI works either side of the server rewrite. Reviews are normalised from both
the new `review` payload and the old `llm_review_*` columns.

### Templates

`templates/skill/` and `templates/task/` are complete and runnable: a working
`scripts/main.py` with tests that pass a fresh `skill check`, and a task with a
grader that documents its own contract. `templates/testcase/` is removed.

### Other

- Domain list reduced from 16 to the eight benchmark domains plus `general`.
  `buildrix.config.VALID_DOMAINS` now re-exports it.
- CLI output is ASCII-only, so it renders on a stock Windows console.

---

<details><summary>Earlier notes (May 2026)</summary>

# Buildrix Updates — May 2026

This bundle covers four changes you asked for. Files in this directory are
drop-ins (or near-drop-ins, with the exception of `index_patch.js` which is
a focused patch since the source file is dense). Where a file is named like
`*_patch.py` or `*_additions.py`, treat it as "apply to existing source"
rather than "replace".

## 1. Nav and middle-block reorder → Challenges, Skills, Tests

Why: it mirrors the contributor funnel. People arrive, see a problem, build
a skill, and validate it. This is also the order you'll want to argue for
in the paper's flywheel section.

**Files**
- `index_patch.js` — edits 1–5.

## 2. Skill taxonomy expanded to 16 domains

Why: current 7 domains miss large parts of AEC (HVAC, envelope, BIM, sensor
ops, embodied carbon, structural, cost). For the paper, a richer taxonomy
is a feature — sparsely-populated categories *are themselves* a finding
("here's where the community has gaps"). Categories follow the building
life-cycle: weather → modeling → systems → controls → comfort → operations
→ verification.

**Files**
- `config.py` — drop-in replacement for `buildrix/config.py`.
- `index_patch.js` — edit 1 (`DOMAINS` constant).

## 3. Test-case format, rubric, and LLM reviewer

Why: this is the heart of your platform's contribution, and it currently
has the most placeholder behavior. The redesign borrows explicitly from CS
benchmarking practice:

- **SWE-bench / HumanEval** — verbatim prompts, pinned versions, gold
  solutions, programmatic checkers.
- **MLPerf** — every benchmark ships a *pinned environment* (OS, library
  versions) so results reproduce.
- **HELM** — scoring is a *weighted set of metrics*, not a scalar.
- **BIG-bench** — tasks have a draft → reviewed → golden lifecycle.

The new TESTCASE.yaml v2 has 8 sections: identity, categorization, task,
inputs, environment, reference, rubric, review. Every field has a
docstring; the goal is that a different engineer reading the YAML cold can
reproduce both the task and the scoring.

The LLM reviewer is acceptable on a free server because the heavy lifting
happens at Anthropic / OpenAI — your server only does an HTTPS POST and
stores the result. The reviewer answers a strict JSON schema (6-item
checklist + verdict + comments). If JSON parsing fails it retries once.

Promotion to golden requires a human (reviewer or admin role). LLM verdict
is necessary but not sufficient — that distinction matters in the paper.

**Files**
- `TESTCASE.yaml` — new v2 template. Replace
  `templates/testcase/TESTCASE.yaml` with this.
- `models_testcase_patch.py` — extended TestCase model + one-shot SQL
  migration.
- `testcases_v2_additions.py` — new endpoints: POST /testcases/v2,
  POST /testcases/{id}/review, POST /testcases/{id}/verify,
  POST /testcases/{id}/reject, GET /testcases/{id}/yaml.
- `review_agent.py` — drop-in replacement for
  `app/services/review_agent.py`. Adds OpenAI fallback and a robust JSON
  parser.
- `index_patch.js` — edits 6–7 (new submission form + handler).

### Config additions

In `app/config.py`, add three settings (keep names matching the env vars
on Render):

```python
anthropic_api_key:    str = ""              # already present
openai_api_key:       str = ""              # NEW
review_model:         str = "claude-sonnet-4-20250514"   # already present
openai_review_model:  str = "gpt-4o-mini"   # NEW
```

Set whichever provider's key you have. The reviewer auto-picks Anthropic
if both are set; pass `?provider=openai` to override per-call.

### Migration

Run the SQL block in `models_testcase_patch.py` once after deploying the
new model. SQLite tolerates the ALTER TABLE statements one at a time;
Postgres should too — wrap in try/except IntegrityError so re-runs are
no-ops.

## 4. Symmetric CLI: pull and update

Why: the verb table reads cleaner — push/pull for hub I/O, install/uninstall
for local lifecycle, update as the "re-pull installed" shortcut. Easier to
explain in the paper too:

| Side  | Create | Read              | Update         | Remove    |
|-------|--------|-------------------|----------------|-----------|
| Hub   | push   | search, browse, pull | push --update | delete    |
| Local | install | list, info        | update         | uninstall |

**Files**
- `cli_additions.py` — argparse stubs + `cmd_pull` + `cmd_update`. Append
  to `buildrix/cli.py` and register them in the `commands` dict in
  `main()`. Also includes a `download_skill_archive` method to paste into
  `HubClient` for raw downloads.

---

## Suggested rollout order

1. Apply the config additions (`openai_api_key`, `openai_review_model`).
2. Run the DB migration (idempotent).
3. Replace `review_agent.py`. Restart the API.
4. Append the new endpoints to `testcases.py`. Restart.
5. Apply the index.html patches. Hard-refresh the browser.
6. Replace `buildrix/config.py` and append CLI additions. Bump CLI
   version. Push to PyPI (or wherever).
7. Drop the new `TESTCASE.yaml` template into the buildrix package.

Hold a sanity check between each step — every change is independent of the
others except (3 ↔ 4 ↔ 6) which together implement the new test-case
pipeline.

</details>
