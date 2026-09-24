"""
Runs every eval in this suite and writes a single before/after markdown
report to evals/results/report.md — this is the artifact you'd actually
attach to a PR description: "here's proof it got better."

Run: python evals/run_evals.py
"""
import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import test_mcp_tools as anomaly_eval  # noqa: E402
import eval_skill_quality as skill_eval  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
REPORT_PATH = os.path.join(HERE, "results", "report.md")


def build_report() -> str:
    v1_anom = anomaly_eval.evaluate_method("v1_zscore")
    v2_anom = anomaly_eval.evaluate_method("v2_robust")
    skills = skill_eval.run()

    lines = []
    lines.append("# Eval Report: game-data-analysis skill + gulliver-liveops MCP server")
    lines.append(f"\nGenerated: {datetime.now(timezone.utc).isoformat(timespec='seconds')}Z")
    lines.append(f"\nDataset: `data/liveops_daily.csv` (120 days, 10 labeled anomalies, "
                 f"1 non-anomalous 7-day marketing campaign as a distractor)")

    # --- Eval 1: anomaly detection ---
    lines.append("\n## Eval 1 — Anomaly detection method: v1_zscore (before) vs v2_robust (after)")
    lines.append("\n| Column | v1 Precision | v1 Recall | v1 F1 | v2 Precision | v2 Recall | v2 F1 |")
    lines.append("|---|---|---|---|---|---|---|")
    for col in v1_anom["per_column"]:
        a, b = v1_anom["per_column"][col], v2_anom["per_column"][col]
        lines.append(
            f"| {col} | {a['precision']:.2f} | {a['recall']:.2f} | {a['f1']:.2f} "
            f"| {b['precision']:.2f} | {b['recall']:.2f} | {b['f1']:.2f} |"
        )
    a, b = v1_anom["overall"], v2_anom["overall"]
    lines.append(
        f"| **overall** | **{a['precision']:.2f}** | **{a['recall']:.2f}** | **{a['f1']:.2f}** "
        f"| **{b['precision']:.2f}** | **{b['recall']:.2f}** | **{b['f1']:.2f}** |"
    )
    delta = b["f1"] - a["f1"]
    lines.append(f"\n**Overall F1 change: {a['f1']:.2f} -> {b['f1']:.2f} ({delta:+.2f})**")
    lines.append(
        "\nWorst case for v1: the `dau` column scores F1=0.00 (0 true positives). "
        "The 7-day marketing campaign inflates the global mean/std enough that "
        "z-score both flags every campaign day as a false positive AND misses "
        "the 2 real injected anomalies (their z-scores now fall under the "
        "widened 3-std threshold). v2_robust's local window isn't affected by "
        "a shift 40+ days away, so it gets `dau` perfectly right."
    )

    # --- Eval 2: skill rubric ---
    lines.append("\n## Eval 2 — Skill document quality: v1_SKILL.md (before) vs SKILL.md (after)")
    lines.append(f"\nRubric score: v1 = {skills['v1']['score']}/{skills['v1']['max_score']}, "
                 f"v2 = {skills['v2']['score']}/{skills['v2']['max_score']}")
    lines.append("\n| Rubric item | v1 | v2 | Why it matters |")
    lines.append("|---|---|---|---|")
    for v1_item, v2_item in zip(skills["v1"]["items"], skills["v2"]["items"]):
        v1_mark = "✅" if v1_item["passed"] else "❌"
        v2_mark = "✅" if v2_item["passed"] else "❌"
        lines.append(f"| {v1_item['description']} | {v1_mark} | {v2_mark} | {v1_item['why_it_matters']} |")

    # --- Pass/fail gate ---
    lines.append("\n## CI gate")
    anomaly_pass = v2_anom["overall"]["f1"] >= v1_anom["overall"]["f1"]
    skill_pass = skills["v2"]["score"] > skills["v1"]["score"]
    lines.append(f"- Anomaly F1 did not regress: {'PASS' if anomaly_pass else 'FAIL'}")
    lines.append(f"- Skill rubric score improved: {'PASS' if skill_pass else 'FAIL'}")

    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    report = build_report()
    os.makedirs(os.path.dirname(REPORT_PATH), exist_ok=True)
    with open(REPORT_PATH, "w") as f:
        f.write(report)
    print(report)
    print(f"\n(also written to {os.path.relpath(REPORT_PATH)})")
