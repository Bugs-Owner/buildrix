"""Schema identifiers and hard limits for the Buildrix formats.

Everything the checkers enforce is a named constant here, so the CLI, the hub
and the documentation cannot drift apart.
"""

from __future__ import annotations

SKILL_SCHEMA = "skill/2.0"
TASK_SCHEMA = "task/2.0"

# -- skill/2.0 ---------------------------------------------------------------

#: Required H2 headings in SKILL.md, in this order.
SKILL_SECTIONS = [
    "Overview",
    "When to use",
    "Inputs",
    "Workflow",
    "Outputs",
    "Examples",
    "Limits",
]

SKILL_BODY_TOKEN_LIMIT = 5_000      # progressive disclosure: overflow -> references/
SKILL_MAX_BYTES = 25 * 1024 * 1024  # packed size
DESCRIPTION_MIN = 40
DESCRIPTION_MAX = 1024

#: A description has to say *when* to use the skill, not only what it does.
#: One of these has to appear for the trigger check to pass.
TRIGGER_PHRASES = [
    "use when", "use this when", "use for", "trigger", "reach for this when",
    "call this when", "apply when", "whenever",
]

DETERMINISM_VALUES = ["deterministic", "seeded", "stochastic"]

# -- task/2.0 ----------------------------------------------------------------

#: Check kinds a rubric criterion may declare.
CHECK_KINDS = [
    "file_exists",
    "schema",
    "numeric_compare",
    "timeseries_compare",
    "set_compare",
    "physical_bounds",
    "file_semantic",
    "python_assert",
    "llm_judge",
]

#: Only these are scored by a language model, and their combined weight is
#: capped by ``rubric.llm_judge_weight_cap``.
JUDGED_KINDS = ["llm_judge"]

DEFAULT_JUDGE_CAP = 0.25
DEFAULT_PASS_THRESHOLD = 0.75
WEIGHT_SUM_TOLERANCE = 1e-6

#: Contributor-declared wrong-but-plausible cases. Fewer than this and the
#: grader has not been shown to discriminate.
MIN_MUTATIONS = 3

#: Submission bundle cap. Bigger workspaces are reduced by ``collect.py``.
BUNDLE_MAX_BYTES = 50 * 1024 * 1024

# -- run protocol ------------------------------------------------------------

MIN_TRIALS = 3          # per arm, for a submittable paired run
BASELINE_MIN_TRIALS = 20  # before the server writes a difficulty figure
