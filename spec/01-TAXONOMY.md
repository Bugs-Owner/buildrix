# Domain taxonomy

Eight domains, closed set, one definition shared by the CLI, the server and the site.

| # | Domain | `id` |
|---|---|---|
| 01 | Building Performance Modeling & Simulation | `performance-modeling` |
| 02 | Design, Retrofit & Decarbonization | `design-retrofit` |
| 03 | Building Operations, Control & Optimization | `operations-control` |
| 04 | Fault Detection, Diagnostics & Commissioning | `fdd-commissioning` |
| 05 | Occupants, Comfort & Indoor Environmental Quality | `occupants-comfort` |
| 06 | Energy Forecasting & Performance Analytics | `forecasting-analytics` |
| 07 | Grid-Interactive & Integrated Energy Systems | `grid-integrated` |
| 08 | Building Data, Semantics & Digital Twins | `data-semantics-twins` |

Short labels for the radar axes, in this order: `MODELING`, `RETROFIT`, `CONTROLS`,
`FDD`, `COMFORT`, `ANALYTICS`, `GRID`, `DATA`.

## `general`

There is one extra value, `general`, for cross-cutting tooling — figure styling, error
logs, data wrangling helpers. Rules:

- A **skill** may use it.
- It is **not** an axis on the radar.
- A **task** may never use it. Every task sits in one of the eight.

## Rules

- `domain` is a closed enum. Adding one is a spec change with a version bump. Without
  that, per-domain results stop being comparable between releases.
- A skill or task picks exactly one domain. Anything else goes in `tags`.
- `tags` stays free text and is where granularity lives (`ashrae-140`, `ifc4`, `mpc`,
  `heat-pump`, `nyc-ll97`). Search indexes tags. The radar only ever reads `domain`.

## Migration

Every existing skill is being rebuilt, so there is no legacy mapping to carry. The
previous 7-item CLI list and 16-item site list are both retired. One source of truth,
imported everywhere:

```python
# buildrix/domains.py — the only place this list exists
DOMAINS = [
    ("performance-modeling",  "Building Performance Modeling & Simulation",         "MODELING"),
    ("design-retrofit",       "Design, Retrofit & Decarbonization",                 "RETROFIT"),
    ("operations-control",    "Building Operations, Control & Optimization",        "CONTROLS"),
    ("fdd-commissioning",     "Fault Detection, Diagnostics & Commissioning",       "FDD"),
    ("occupants-comfort",     "Occupants, Comfort & Indoor Environmental Quality",  "COMFORT"),
    ("forecasting-analytics", "Energy Forecasting & Performance Analytics",         "ANALYTICS"),
    ("grid-integrated",       "Grid-Interactive & Integrated Energy Systems",       "GRID"),
    ("data-semantics-twins",  "Building Data, Semantics & Digital Twins",           "DATA"),
]
GENERAL = ("general", "General tooling", None)   # skills only, never tasks
```

The server exposes it at `GET /api/domains` so the site never hard-codes a copy.
