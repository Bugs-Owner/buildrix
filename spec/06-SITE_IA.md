# Site information architecture

## Visual language

The original cyberpunk identity stays: near-black ground (`#07080c`), cyan accent
(`#00f0ff`), magenta for the treatment arm and for anything blocking, amber for warnings,
neon yellow only inside the wordmark gradient, scanline overlay. The cyan/magenta pair is
colour-vision-safe on this ground (checked: ΔE 19.6 under deuteranopia, 45.9 under normal
vision), so it doubles as the chart palette.

**Motion**, carried over from the original page:

- a 80 px grid drifting one cell every 34 s, radially masked so it fades below the fold
- three slow radial glows breathing on an 18 s cycle
- one cyan scan line sweeping down every 11 s
- the wordmark filled with an animated cyan → white → neon gradient, 9 s loop
- headline numbers counting up on load, and a live feed line in the status panel

All of it is disabled under `prefers-reduced-motion`.

**Type**: Orbitron for the wordmark and headings, as before. Body text moved from Chakra
Petch to **Inter** — the same choice the reference benchmark sites make — because it holds
up far better at paragraph sizes. JetBrains Mono stays for data, labels and code.

"Simple is beautiful" applies to the structure, not the theme. Fewer sections, shorter
sentences, one idea per block, no theme switch.

## Navigation

```
BUILDRIX                    Skills  Tasks  Leaderboard | Contributors  GitHub  [Sign in]
```

- Everything sits top right. Skills, Tasks and Leaderboard are styled the same as
  Contributors and GitHub, separated by a thin rule.
- The wordmark is the home link. There is no Home item.
- No theme toggle.
- Sub-pages go **back one level**, not to the front page: "← Skills" from add-a-skill,
  "← Tasks" from add-a-task.

## Home

The tagline stays as it is:

> **Buildrix** — Develop and benchmark agentic AI skills for real-world building challenges.

The hero is a two-column band. Left: the wordmark, the tagline, and a row of
counters that say the work is real - **skills, golden tasks, contributors,
organizations** - counting up on load. Right: the demo capture of an agent working
through a building task, framed with a notched corner and a live-capture label.
No status box.

Then three sections, alternating sides. Each is a question, a one-line answer, evidence
and a door. Nothing else — the contribution routes belong on the sub-pages, and the
section text stays high-level. No progress reports, no "n of 8 covered".

| § | Question | Answer | Evidence | Goes to |
|---|---|---|---|---|
| 01 | What has been built | Reusable skills | Radar: skills per domain + difficulty spread | Skills |
| 02 | How it is evaluated | Human-verified golden tasks | Radar: tasks per domain + difficulty spread | Tasks |
| 03 | Whether skills help | Measured against a control | Dumbbell: pass rate per domain, control to treatment | Leaderboard |

**One series per radar.** The two-series "now versus target" version was confusing
and the target was not information anyone needed. Each axis carries its real
category name over two lines with the count beneath it, and below the radar sits a
five-bar strip showing how the domain's skills or tasks spread across
**difficulty 1 to 5**, ramped cyan (L1) to magenta (L5).

Section 03 is a dumbbell: one row per domain, an open dot for the control arm, a
filled dot for the treatment arm, the line between them as the gain. A domain where
skills lost ground shows as a dot to the left of the control - no separate colour
needed, since "with skills" already includes the cases where skills hurt.

All three figures share one 470 x 430 frame and one set of font sizes, so the three
panels line up down the page.

**The figures are controls, not pictures.** Each radar carries a difficulty row -
`all L1 L2 L3 L4 L5` - and the five-bar strip beneath it is clickable too, so a
visitor can ask "what do we have at level 5?" and see that shape immediately. The
caption names the active filter. The benefit chart carries a model row (all configs,
or one model and harness) and an order toggle (by domain, or ranked by gain), and
re-plots in place.

Navigation does not rely on default anchor behaviour: a capturing click handler
intercepts `a[href^="#/"]` and sets the hash itself, because some embedders swallow
the default. `route()` also catches its own errors and renders them, so a scripting
mistake shows a message instead of silently leaving the previous page on screen.

## Skills

1. **What is here** — the radar, beside a ranked **most installed** list.
2. **Recently added** — a slow horizontal reel of skill cards. Pauses on hover, honours
   `prefers-reduced-motion`.
3. **Find one** — search, plus domain filters.
4. **The grid** — cards: name, domain, one line, installs, likes, measured gain. Sorts by installs, likes or gain.
5. Two doors: **Add a skill** and **Request a skill**.

**Skill detail**: rendered SKILL.md, the frontmatter as a table, file tree, install
command, and the validator report (format, determinism double-run, leakage scan, token
cost, declared hosts).

## Tasks

Same shape: the radar, beside **hardest right now** — tasks ranked by how rarely an agent
passes them with no skills — then search and the grid. The grid sorts by hardest, most
attempted, or expert time.

**Task detail**: the verbatim prompt, the deliverable contract, the checks *shown next to
the prompt phrase each one came from*, environment and budget, baseline pass rate with
its trial count, and the revision history under "how this task was sharpened".

## Submitting — three routes, both artifact types

Skills and tasks each get an "add" page that opens with the same three routes:

| Route | For whom |
|---|---|
| **1 · the package** | `buildrix <skill|task> new` → `check` → `submit`. All gates run locally first, then the server reviews. |
| **2 · upload** | A zip that already follows the format. Same checks run on upload, report in the browser. |
| **3 · step by step** | Six sections of plain questions, each with a real example in grey. The form writes the files. |

Below the routes, the step-by-step form is laid out as six numbered layers, each with a
one-line reason for why it is asked. Single column, so the sequence reads in order.

**Task form**: 1 where it comes from · 2 the job (the exact prompt) · 3 what is given ·
4 what comes back · 5 how correctness is decided · 6 ground rules.

**Skill form**: 1 identity · 2 what it does and when to use it · 3 how it works ·
4 code and dependencies · 5 outputs · 6 limits.

Both pages then show **what comes back**, side by side: the browser report and the same
report as the CLI prints it. Findings quote the offending words, a suggested rewrite can be
accepted, edited or ignored, and a status block gives the verdict, the round number and
what is still missing. The reviewer runs on the server for skills and tasks alike.

## Leaderboard

Not populated yet, so it ships as a labelled layout with a banner saying every figure is
sample data. Row per model × harness × skill set: control, with-skills, gap, confidence
interval, McNemar *p*, count of tasks that got worse, tokens and dollars per task, and an
evidence level. Default view shows reproduced runs.

## Account

One short form, only what an author list needs: name, email, affiliation, country, and
optionally ORCID and GitHub. Plus one consent line about submissions and their revision
history being kept for research. No position, no bio, no domain, no third-party sign-in.

## Contributors

Everyone who published a skill or contributed a task, with what they did and in which
domain. This is the standing record that becomes an author list — so credit follows
published skills and accepted tasks only. Submitting a benchmark run is not authorship.
