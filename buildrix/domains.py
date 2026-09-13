"""The eight application domains shared by Buildrix skills and tasks."""

from __future__ import annotations

# (id, label, short label used on radar axes)
DOMAINS: list[tuple[str, str, str]] = [
    ("performance-modeling",   "Building Performance Simulation",        "MODELING"),
    ("design-retrofit",        "Design, Retrofit & Decarbonization",                "RETROFIT"),
    ("operations-control",     "Building Control & Optimization",       "CONTROLS"),
    ("fdd-commissioning",      "FDD & Commissioning",      "FDD"),
    ("occupants-comfort",      "Occupants, Comfort & IEQ", "COMFORT"),
    ("forecasting-analytics",  "Energy Forecasting & Performance Analytics",        "ANALYTICS"),
    ("grid-integrated",        "Grid Integrated Energy Systems",      "GRID"),
    ("data-semantics-twins",   "Building Data, Semantics & Digital Twins",          "DATA"),
]

#: Valid domains for a skill (the eight application domains).
SKILL_DOMAINS: list[str] = [d[0] for d in DOMAINS]

#: Valid domains for a task (the eight only).
TASK_DOMAINS: list[str] = [d[0] for d in DOMAINS]

LABELS: dict[str, str] = {d[0]: d[1] for d in DOMAINS}
SHORT: dict[str, str] = {d[0]: d[2] for d in DOMAINS}

# Domain ids retired in the v2 taxonomy, mapped to their closest replacement.
# Kept so an old skill or task still resolves instead of failing outright.
LEGACY_ALIASES: dict[str, str] = {
    "weather-climate":       "performance-modeling",
    "energy-modeling":       "performance-modeling",
    "envelope":              "performance-modeling",
    "hvac-mechanical":       "operations-control",
    "controls-optimization": "operations-control",
    "thermal-comfort-ieq":   "occupants-comfort",
    "lighting-daylighting":  "occupants-comfort",
    "sensor-operations":     "fdd-commissioning",
    "grid-demand-response":  "grid-integrated",
    "semantic-modeling":     "data-semantics-twins",
    "bim-geometry":          "data-semantics-twins",
    "structural":            "data-semantics-twins",
    "embodied-carbon-lca":   "design-retrofit",
    "cost-construction":     "design-retrofit",
    "code-compliance":       "design-retrofit",
}


def normalize(domain: str) -> str:
    """Return the canonical id for ``domain``, mapping retired ids forward."""
    d = (domain or "").strip().lower()
    return LEGACY_ALIASES.get(d, d)


def is_valid(domain: str, *, kind: str = "skill") -> bool:
    """True when ``domain`` is usable by a skill (default) or a task."""
    allowed = TASK_DOMAINS if kind == "task" else SKILL_DOMAINS
    return normalize(domain) in allowed


def label(domain: str) -> str:
    return LABELS.get(normalize(domain), domain)


def short(domain: str) -> str:
    return SHORT.get(normalize(domain), (domain or "?")[:9].upper())


def listing(kind: str = "skill") -> str:
    """A printable table of the valid domains."""
    rows = [(d, LABELS[d], SHORT[d]) for d in (TASK_DOMAINS if kind == "task" else SKILL_DOMAINS)]
    width = max(len(r[0]) for r in rows)
    return "\n".join(f"  {r[0]:<{width}}  {r[1]}" for r in rows)
