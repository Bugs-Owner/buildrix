"""The grader for your-task-name.

This file and everything in reference/ stay on the server. They are loaded only
after the agent has stopped, so the answers never ship with the question.

One function, one contract:

    grade(bundle_dir, reference_dir) -> dict with "overall" in [0, 1]

`buildrix task check` runs it against four things and every one has to hold:

    G3  your own answer          scores exactly 1.00
    G4  an empty folder          scores exactly 0.00
    G5  each grader/mutations/*  scores below rubric.pass_threshold
    G6  the same folder twice    scores the same

Keep it deterministic: no clocks, no network, no randomness. If you need a
tolerance, take it from TASK.yaml rather than hard-coding a second copy here.
"""

from __future__ import annotations

from pathlib import Path

PASS_THRESHOLD = 0.75

# id -> weight. Must match rubric.criteria in TASK.yaml.
WEIGHTS = {
    "result_present": 0.20,
    "result_schema": 0.30,
    "values_vs_reference": 0.50,
}


def grade(bundle_dir: str, reference_dir: str) -> dict:
    bundle, reference = Path(bundle_dir), Path(reference_dir)

    scores: dict[str, float] = {}
    evidence: dict[str, str] = {}

    result = bundle / "outputs" / "result.csv"

    # ── result_present ──────────────────────────────────────────────────────
    scores["result_present"] = 1.0 if result.exists() else 0.0
    evidence["result_present"] = "found" if result.exists() else "outputs/result.csv missing"

    # ── result_schema ───────────────────────────────────────────────────────
    if not result.exists():
        scores["result_schema"] = 0.0
        evidence["result_schema"] = "no file to check"
    else:
        import pandas as pd

        df = pd.read_csv(result)
        wanted = {"timestamp", "value"}
        have = {_norm(c) for c in df.columns}
        missing = {c for c in wanted if c not in have}
        if missing:
            scores["result_schema"] = 0.0
            evidence["result_schema"] = f"missing column(s): {', '.join(sorted(missing))}"
        else:
            scores["result_schema"] = 1.0
            evidence["result_schema"] = f"{len(df)} rows, columns match"

    # ── values_vs_reference ─────────────────────────────────────────────────
    ref = reference / "result.csv"
    if not result.exists() or not ref.exists():
        scores["values_vs_reference"] = 0.0
        evidence["values_vs_reference"] = "nothing to compare"
    else:
        import pandas as pd

        got = pd.read_csv(result).rename(columns=_norm)
        want = pd.read_csv(ref).rename(columns=_norm)
        n = min(len(got), len(want))
        if n == 0 or "value" not in got:
            scores["values_vs_reference"] = 0.0
            evidence["values_vs_reference"] = "no comparable values"
        else:
            a = got["value"].to_numpy()[:n].astype(float)
            b = want["value"].to_numpy()[:n].astype(float)
            nmbe, cvrmse = _ashrae(a, b)
            ok_len = n >= 0.98 * len(want)
            passed = ok_len and abs(nmbe) <= 5.0 and cvrmse <= 15.0
            scores["values_vs_reference"] = 1.0 if passed else 0.0
            evidence["values_vs_reference"] = (
                f"NMBE {nmbe:+.1f}% (limit 5), CVRMSE {cvrmse:.1f}% (limit 15), "
                f"{n} of {len(want)} rows"
            )

    overall = sum(WEIGHTS[k] * scores.get(k, 0.0) for k in WEIGHTS)
    return {
        "overall": round(overall, 6),
        "passed": overall >= PASS_THRESHOLD,
        "criteria": scores,
        "evidence": evidence,
    }


# ── helpers ─────────────────────────────────────────────────────────────────

def _norm(name: str) -> str:
    """Loose column matching: case, spaces, underscores and unit suffixes."""
    s = str(name).strip().lower().replace(" ", "_")
    for suffix in ("_[c]", "_[degc]", "_degc", "_c", "_[kwh]", "_kwh", "_[w]", "_w"):
        if s.endswith(suffix):
            s = s[: -len(suffix)]
            break
    return s.strip("_")


def _ashrae(actual, expected):
    """NMBE and CVRMSE in percent, per ASHRAE Guideline 14."""
    import numpy as np

    mean = float(np.mean(expected))
    if mean == 0:
        return 0.0, 0.0
    err = actual - expected
    nmbe = 100.0 * float(np.sum(err)) / (len(expected) * mean)
    cvrmse = 100.0 * float(np.sqrt(np.mean(err ** 2))) / mean
    return nmbe, cvrmse
