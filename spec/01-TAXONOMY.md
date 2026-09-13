# Domains

Choose the closest domain for a task or skill. Use tags for more specific topics.

| Domain | ID |
|---|---|
| Building Performance Modeling & Simulation | `performance-modeling` |
| Design, Retrofit & Decarbonization | `design-retrofit` |
| Building Operations, Control & Optimization | `operations-control` |
| Fault Detection, Diagnostics & Commissioning | `fdd-commissioning` |
| Occupants, Comfort & Indoor Environmental Quality | `occupants-comfort` |
| Energy Forecasting & Performance Analytics | `forecasting-analytics` |
| Grid-Interactive & Integrated Energy Systems | `grid-integrated` |
| Building Data, Semantics & Digital Twins | `data-semantics-twins` |

Skills may also use `general` for cross-cutting tools. Tasks use one of the
eight domains above.

Run `buildrix domains` or `buildrix domains --task` for the current choices.
The hub exposes the taxonomy through `GET /api/domains`.
