"""
Unit tests for the MCP server tools themselves (correctness, safety), plus
the anomaly-detection eval that produces the before/after numbers used in
README.md and evals/results/report.md.

Run: pytest evals/test_mcp_tools.py -v
"""
import csv
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "mcp_server"))
import server  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
GROUND_TRUTH_PATH = os.path.join(HERE, "..", "data", "liveops_ground_truth.csv")


def load_ground_truth():
    gt = {}  # column -> set of true anomaly row indices
    with open(GROUND_TRUTH_PATH) as f:
        for row in csv.DictReader(f):
            gt.setdefault(row["column"], set()).add(int(row["row_index"]))
    return gt


# --- Tool correctness / safety tests -----------------------------------

def test_list_tables_finds_liveops_daily():
    result = server.list_tables()
    assert "liveops_daily" in result["tables"]


def test_profile_table_reports_no_nulls_on_clean_data():
    profile = server.profile_table("liveops_daily")
    assert profile["row_count"] == 120
    assert all(n == 0 for n in profile["null_counts"].values())
    assert profile["duplicate_rows"] == 0


def test_profile_table_unknown_table_returns_error_not_exception():
    result = server.profile_table("does_not_exist")
    assert "error" in result


def test_run_sql_allows_select():
    result = server.run_sql("SELECT date FROM liveops_daily LIMIT 5")
    assert result["row_count"] == 5


def test_run_sql_blocks_write_statements():
    for bad_query in [
        "DROP TABLE liveops_daily",
        "DELETE FROM liveops_daily",
        "UPDATE liveops_daily SET dau=0",
        "SELECT * FROM liveops_daily; DROP TABLE liveops_daily",
    ]:
        result = server.run_sql(bad_query)
        assert "error" in result, f"expected '{bad_query}' to be blocked"


def test_run_sql_blocks_sql_injection_via_identifier():
    import pytest
    with pytest.raises(ValueError):
        server.profile_table("liveops_daily; DROP TABLE liveops_daily;--")


# --- Anomaly detection: the actual "prove it got better" eval ----------

def _precision_recall_f1(predicted: set, actual: set) -> dict:
    tp = len(predicted & actual)
    fp = len(predicted - actual)
    fn = len(actual - predicted)
    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0
    return {"tp": tp, "fp": fp, "fn": fn, "precision": precision, "recall": recall, "f1": f1}


def evaluate_method(method: str) -> dict:
    """Runs the given anomaly-detection method on every column and scores
    it against the labeled ground truth. This is the function imported by
    evals/run_evals.py to build the before/after report."""
    ground_truth = load_ground_truth()
    per_column = {}
    all_tp = all_fp = all_fn = 0

    for column in ["dau", "revenue_usd", "avg_session_length_min", "crash_rate_pct"]:
        result = server.detect_anomalies("liveops_daily", column, method)
        predicted = {a["index"] for a in result["anomalies"]}
        actual = ground_truth.get(column, set())
        scores = _precision_recall_f1(predicted, actual)
        per_column[column] = scores
        all_tp += scores["tp"]
        all_fp += scores["fp"]
        all_fn += scores["fn"]

    overall = _precision_recall_f1(
        set(range(all_tp)),  # placeholder, overwritten below
        set(),
    )
    # compute overall directly from aggregated counts instead
    precision = all_tp / (all_tp + all_fp) if (all_tp + all_fp) else 0.0
    recall = all_tp / (all_tp + all_fn) if (all_tp + all_fn) else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0
    overall = {"tp": all_tp, "fp": all_fp, "fn": all_fn, "precision": precision, "recall": recall, "f1": f1}

    return {"method": method, "per_column": per_column, "overall": overall}


def test_v2_robust_beats_v1_zscore_on_f1():
    """The actual regression-proof: the improved method must not be worse
    than the naive baseline on the labeled synthetic dataset."""
    v1 = evaluate_method("v1_zscore")
    v2 = evaluate_method("v2_robust")
    assert v2["overall"]["f1"] >= v1["overall"]["f1"], (
        f"v2_robust F1 ({v2['overall']['f1']:.2f}) did not beat "
        f"v1_zscore F1 ({v1['overall']['f1']:.2f})"
    )


if __name__ == "__main__":
    import json
    for m in ["v1_zscore", "v2_robust"]:
        print(f"\n=== {m} ===")
        print(json.dumps(evaluate_method(m), indent=2))
