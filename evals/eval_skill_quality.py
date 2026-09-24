"""
Rubric-based eval for the *skill document itself* (not the agent's output —
we have no LLM access in this environment to grade free-text agent runs
against, so this eval scores the instructions an agent would follow).

Each rubric item encodes a real failure mode observed while building this
toolkit (see README.md). A skill that doesn't mention a failure mode can't
reliably prevent it, so "does the skill instruct the agent to do X" is a
legitimate, if partial, proxy for "will the agent do X."

This is intentionally a *different kind* of eval than test_mcp_tools.py's
precision/recall (which grades code against ground truth). Grading a
prose instruction document needs a rubric instead. Both are shown in the
report because a toolkit needs both kinds of evals: one for its tools,
one for the instructions steering the agent that uses them.
"""
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL_DIR = os.path.join(HERE, "..", "skills", "game-data-analysis")

RUBRIC = [
    {
        "id": "profiles_before_analyzing",
        "description": "Instructs profiling (nulls/dtypes/dupes) before drawing conclusions",
        "pattern": r"profile|null|dtype|duplicate",
        "why_it_matters": "Without this, a bad ETL run (nulls) gets reported as a real metric drop.",
    },
    {
        "id": "checks_date_continuity",
        "description": "Instructs checking for missing/gapped dates",
        "pattern": r"gap|missing day|date range|continuity",
        "why_it_matters": "A silent gap in daily data looks identical to 'nothing happened' if unchecked.",
    },
    {
        "id": "specifies_anomaly_method",
        "description": "Names a specific anomaly-detection method to use (not just 'look for anomalies')",
        "pattern": r"v2_robust|IQR|robust|method\s*=",
        "why_it_matters": "'Look for anomalies' with no method = the agent invents its own, unverified approach.",
    },
    {
        "id": "warns_against_naive_method",
        "description": "Explicitly warns against the naive/baseline method and explains why",
        "pattern": r"v1_zscore|naive|z-score|do not use|don't use",
        "why_it_matters": "Without this, nothing stops the agent from picking the worse method by default.",
    },
    {
        "id": "cross_references_other_metrics",
        "description": "Instructs checking co-occurring anomalies across metrics on the same date",
        "pattern": r"other column|co-occur|same date|incident",
        "why_it_matters": "Reporting a DAU drop and a crash spike as two findings instead of one incident.",
    },
    {
        "id": "distinguishes_trend_from_point_anomaly",
        "description": "Distinguishes a sustained trend from a single-day anomaly",
        "pattern": r"trend|sustained|multi-day",
        "why_it_matters": "A trend needs root-cause investigation; a point anomaly needs a sanity check. Conflating them wastes the reader's time.",
    },
    {
        "id": "requires_baseline_in_output",
        "description": "Requires reporting the local baseline alongside any anomaly value",
        "pattern": r"baseline|vs\.?\s*(the\s*)?(local|neighboring|neighbouring)",
        "why_it_matters": "\"Revenue was $5,767\" means nothing without \"vs ~$1,000-1,400 normally.\"",
    },
    {
        "id": "defines_structured_output_format",
        "description": "Specifies a concrete report structure/template, not just 'write a summary'",
        "pattern": r"```|## Summary|## Anomalies|report format|structure the output",
        "why_it_matters": "Unstructured summaries are inconsistent between runs and hard for a PM to scan quickly.",
    },
]


def score_skill(path: str) -> dict:
    with open(path) as f:
        text = f.read()

    results = []
    for item in RUBRIC:
        matched = bool(re.search(item["pattern"], text, re.IGNORECASE))
        results.append({**item, "passed": matched})

    passed = sum(1 for r in results if r["passed"])
    return {
        "path": os.path.relpath(path, os.path.join(HERE, "..")),
        "score": passed,
        "max_score": len(RUBRIC),
        "items": results,
    }


def run() -> dict:
    v1 = score_skill(os.path.join(SKILL_DIR, "v1_SKILL.md"))
    v2 = score_skill(os.path.join(SKILL_DIR, "SKILL.md"))
    return {"v1": v1, "v2": v2}


def _print_report(data: dict):
    for label, result in data.items():
        print(f"\n=== {label} ({result['path']}) : {result['score']}/{result['max_score']} ===")
        for item in result["items"]:
            mark = "PASS" if item["passed"] else "FAIL"
            print(f"  [{mark}] {item['id']}: {item['description']}")


def test_v2_skill_beats_v1_on_rubric():
    """pytest entry point: the improved skill must score strictly higher."""
    data = run()
    assert data["v2"]["score"] > data["v1"]["score"], (
        f"v2 score ({data['v2']['score']}) did not beat v1 score ({data['v1']['score']})"
    )


if __name__ == "__main__":
    _print_report(run())
