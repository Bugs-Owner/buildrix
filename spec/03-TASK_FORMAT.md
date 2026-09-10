# Task package contract — `task/2.0`

A task is **a contract, not a description**. If a grader can check it, the prompt must
have said it; if the prompt said it, the grader should check it. Everything below exists
to make that biconditional mechanically verifiable.

Terminology change: what v1 called a *test case* is now a **task**. One word, matching
the site nav.

## Public / private split

```
task-slug/
├── PUBLIC  — shipped to every runner
│   ├── TASK.yaml           the contract
│   ├── prompt.md           verbatim agent instruction, the only NL input at run time
│   ├── inputs/             staged into the agent workspace before the run
│   ├── env/requirements.txt (+ optional setup.sh)
│   ├── collect.py          workspace -> submission bundle (reduction, never grading)
│   └── provenance.md       who built it, from what, how long it took, confidence
└── PRIVATE — never leaves the hub
    └── grader/
        ├── grade.py        evaluate(bundle_dir, ref_dir) -> Score
        └── reference/      the expert gold outputs
```

The reference and grader are staged **only after** the agent has finished, and only on
the hub. This is non-negotiable: a benchmark whose answers ship with the question
measures memorisation.

`collect.py` exists so a 4 GB EnergyPlus output directory becomes a 2 MB submission. It
is public, deterministic, and must not itself score anything — it selects, aggregates,
and hashes.

## TASK.yaml

```yaml
schema: "task/2.0"

identity:
  id: syracuse-weather-april-2025          # kebab-case slug, immutable
  title: "Syracuse April 2025 weather extraction"
  version: "1.0.0"
  license: CC-BY-4.0
  authors: [{name: Jane Doe, affiliation: Syracuse University, orcid: "0000-..."}]

taxonomy:
  domain: performance-modeling             # closed enum, one of eight
  tags: [weather, solar, api, new-york]
  human_minutes: 18                        # expert self-report, used for cost framing
  # No difficulty field. Difficulty is the measured no-skill baseline pass rate,
  # written back by the server. See "Difficulty" below.

# -- what the agent is told --------------------------------------------------
task:
  prompt_file: prompt.md                   # verbatim, never paraphrased at run time
  workspace_layout: |                      # what the agent finds on disk
    inputs/site.json
    outputs/            (empty, agent writes here)

# -- the interface contract --------------------------------------------------
deliverables:
  - path: outputs/weather_data.csv
    format: csv
    required: true
    naming: normalized                     # normalized | strict  (see below)
    schema:
      index: {name: timestamp, type: datetime, tz: America/New_York, freq: 1h}
      columns:
        - {name: temp_air,   unit: degC, type: float, range: [-40, 55]}
        - {name: rh,         unit: pct,  type: float, range: [0, 100]}
        - {name: ghi,        unit: W/m2, type: float, range: [0, 1400]}
        - {name: wind_speed, unit: m/s,  type: float, range: [0, 60]}
      rows: {min: 700, max: 745}
  - path: outputs/summary.md
    format: markdown
    required: true

# -- the run environment -----------------------------------------------------
environment:
  os: any                                  # any | linux | windows | macos
  python: ">=3.11,<3.14"
  requirements: env/requirements.txt       # fully pinned
  external_tools: []                       # e.g. [{name: EnergyPlus, version: "24.2.0"}]
  network:
    policy: allowlist                      # allowlist | offline
    hosts: [archive-api.open-meteo.com]
  gpu: false

# -- identical budget for BOTH arms of a paired run --------------------------
budget:
  wall_clock_s: 900
  max_tokens: 250000
  max_tool_calls: 120

# -- ambiguity control: state what is free and what is fixed -----------------
freedom:
  free: ["any HTTP client or library", "any file-writing approach"]
  fixed:
    - requirement: "Data source must be the Open-Meteo ERA5 archive endpoint"
      reason: "Different reanalysis products differ by >1 degC; the tolerance below is
               only meaningful against a pinned source."
variance_controls:
  seeds: []                                # required if determinism != deterministic
  pinned:
    - "Evaluation period: 2025-04-01 00:00 to 2025-04-30 23:00, local standard time"
    - "Open-Meteo archive, retrieved 2026-05-02 (frozen copy held in grader/reference)"

# -- how it is scored --------------------------------------------------------
rubric:
  pass_threshold: 0.75
  llm_judge_weight_cap: 0.25               # hard cap; a task may set 0
  criteria:
    - id: csv_present
      weight: 0.10
      check: file_exists
      args: {path: outputs/weather_data.csv}
      prompt_anchor: "Save the hourly data to outputs/weather_data.csv"

    - id: csv_schema
      weight: 0.25
      check: schema
      args: {path: outputs/weather_data.csv}   # schema taken from deliverables
      prompt_anchor: "dry-bulb temperature, relative humidity, global horizontal
                      irradiance and wind speed"

    - id: values_match_reference
      weight: 0.45
      check: timeseries_compare
      args:
        path: outputs/weather_data.csv
        reference: weather_data.csv
        columns: [temp_air, ghi]
        metrics: {nmbe_pct: 5.0, cvrmse_pct: 15.0}   # ASHRAE Guideline 14 style
      prompt_anchor: "for the full month of April 2025"

    - id: summary_complete
      weight: 0.20
      check: llm_judge
      args:
        path: outputs/summary.md
        must_contain: [location, date range, per-variable min/max/mean with units,
                       date and value of peak GHI]
      prompt_anchor: "write a brief Markdown summary at outputs/summary.md"

# -- contributor-declared degradations, proving the grader discriminates -----
mutation_tests:
  - {name: drop_ghi_column,    expect_below: 0.75}
  - {name: shift_all_temps_5C, expect_below: 0.75}
  - {name: half_the_month,     expect_below: 0.75}

provenance:
  origin: "Real project — 2025 campus retrofit study, Syracuse University"
  expert: {role: "Building energy modeler, 8 yrs", minutes: 18, confidence: high}
  reference_method: "Open-Meteo hourly archive, spot-checked against NSRDB 2025-04-15,
                     agreement within 4%."
```

## The two mechanisms that kill ambiguity

### 1. `prompt_anchor` — every graded thing was stated

Every rubric criterion carries a substring that **must appear in `prompt.md`**. The
validator checks this literally. If you want to grade something, you have to have asked
for it, in the words the agent actually reads. This one field eliminates the most common
unfairness in agent benchmarks: grading an unstated requirement.

The reverse direction is the reviewer's job (`05-INTAKE_REVIEW.md`): any *imperative
sentence in the prompt that no criterion checks* is flagged as either dead text to cut,
or a missing criterion.

### 2. `naming: normalized` by default

Column and file matching is normalised (case, spaces, underscores, unit suffixes,
`°C` / `degC` / `C`) unless the task explicitly sets `strict`. We are measuring building
engineering, not the agent's ability to guess your header spelling. `strict` is reserved
for tasks where the exact identifier *is* the deliverable — an IDF field name, a Brick
class, a code clause citation.

## Check kinds

Deterministic checks come first and carry the weight. `llm_judge` is capped.

| check | Use |
|---|---|
| `file_exists` | deliverable produced |
| `schema` | columns, dtypes, units, ranges, row counts, index frequency |
| `numeric_compare` | scalars/tables vs reference: `abs_tol`, `rel_tol` |
| `timeseries_compare` | NMBE / CVRMSE / RMSE / MAE thresholds — ASHRAE Guideline 14 vocabulary |
| `set_compare` | unordered sets: equipment lists, violated code clauses, detected faults; reports precision/recall/F1 |
| `physical_bounds` | conservation, monotonicity, non-negativity, energy-balance closure |
| `file_semantic` | domain parsers: IDF / IFC / gbXML / JSON-LD object-level diff |
| `python_assert` | arbitrary grader code for what the above don't cover |
| `llm_judge` | prose deliverables only, weight ≤ `llm_judge_weight_cap` |

`grade.py` returns:

```python
Score(overall=0.86, passed=True,
      criteria={"csv_present": 1.0, "csv_schema": 1.0,
                "values_match_reference": 0.82, "summary_complete": 0.60},
      evidence={"values_match_reference": "CVRMSE 11.4% (<=15), NMBE -2.1% (<=5)"})
```

Evidence strings go back to the contributor and onto the public task page. A score with
no evidence is not admissible.

## Admission gates — mechanical, run before any human looks

| Gate | Rule |
|---|---|
| G1 schema | `TASK.yaml` validates against `task/2.0` |
| G2 anchors | every criterion's `prompt_anchor` occurs in `prompt.md` |
| G3 gold | `grade(reference) == 1.0` |
| G4 floor | `grade(empty workspace) == 0.0` |
| G5 discrimination | every `mutation_tests` entry scores below `pass_threshold` |
| G6 determinism | `grade(bundle)` twice gives identical scores |
| G7 weights | criteria weights sum to 1.0; `llm_judge` share ≤ cap |
| G8 budget | the expert's own run fits inside `budget` |
| G9 baseline | a no-skill agent baseline exists (≥ 3 trials) |

G5 is the gate nobody else runs, and it is the one that matters most: it proves the
rubric can tell a good answer from a plausible-looking bad one. Asking the contributor
for three ways a wrong answer could still look right costs them five minutes and catches
the failure that quietly ruins benchmarks.

G9 seeds the difficulty measure, which is why contributors never declare difficulty
themselves.

## Difficulty — measured, not labelled

There are no tiers, and no easy/medium/hard field. Buckets like that are arbitrary: the
boundaries are unjustifiable, they hide the variance, and they go stale silently.

Instead, every task carries the measured **no-skill baseline pass rate**, written back by
the server from at least 20 trials across at least 2 model configurations:

```yaml
# written by the server, not by the contributor
baseline:
  pass_rate: 0.08
  ci95: 0.04
  trials: 24
  configs: ["claude-opus-5/claude-code", "gpt-5.5/codex-cli"]
  measured_at: "2026-09-01"
```

It is one continuous number, comparable across tasks and domains, with its uncertainty
attached and its provenance stated. Sorting and filtering use it directly. It is
recomputed each release, and the history stays public, so a task models have learned to
solve visibly loses its value in the suite instead of keeping a stale "expert" label.

`human_minutes` sits beside it as the human-effort measure. The two together say more
than any bucket: *18 minutes for an expert, 71% for an agent with no skills.*

## Qualitative tasks

Some real work — design rationale, compliance narrative, retrofit recommendation memos —
has no numeric gold. These are admitted as `strength: qualitative`, must still pass
G1/G2/G4/G6/G7, use `llm_judge` against an explicit assertion list, and are reported as a
**separate track**: never mixed into the headline deterministic pass rate, never promoted
to `golden`.
