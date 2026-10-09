"""
Unit and integration tests for the RAG Evaluation CI Regression Gate.
Verifies:
1. All metrics passing threshold criteria
2. Recall@3 regression triggers FAIL
3. Recall@5 regression triggers FAIL
4. MRR regression triggers FAIL
5. nDCG@5 regression triggers FAIL
6. Citation precision regression triggers FAIL
7. Citation coverage regression triggers FAIL
8. Correct refusal rate regression triggers FAIL
9. False refusal rate excess triggers FAIL
10. Mean latency excess triggers FAIL
11. P95 latency excess triggers FAIL
12. Exact boundary threshold behavior (boundary values pass)
13. Floating point tolerance behavior (precision drift within 1e-4 passes)
14. Multiple simultaneous failures reported cleanly
15. Missing required metric handling
16. Malformed configuration / metric type handling
17. Standalone regression CLI exit codes (0 for pass, 1 for fail, 2 for error)
18. Evaluation CLI regression gate integration and controlled failure detection
"""
import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile

from app.eval.config import DEFAULT_THRESHOLDS, EvaluationThresholds
from app.eval.regression import evaluate_regression

# Baseline passing metrics matching Phase 2 benchmark performance
PASSING_METRICS = {
    "pass_rate": 0.9600,
    "recall_at_3": 0.9000,
    "recall_at_5": 0.9667,
    "mrr": 0.8458,
    "ndcg_at_5": 0.8662,
    "citation_precision": 0.8800,
    "citation_coverage": 0.9500,
    "correct_refusal_rate": 1.0000,
    "false_refusal_rate": 0.0000,
    "mean_latency_ms": 235.0,
    "latency_p95_ms": 320.0,
}


def test_1_all_metrics_pass():
    report = evaluate_regression(PASSING_METRICS, DEFAULT_THRESHOLDS)
    assert report.passed is True
    assert report.failed_checks == 0
    assert report.passed_checks == report.total_checks
    print("[PASS] Test 1: All metrics pass against standard thresholds.")


def test_2_recall_at_3_regression():
    m = copy.deepcopy(PASSING_METRICS)
    m["recall_at_3"] = 0.8400  # Threshold is 0.8500
    report = evaluate_regression(m, DEFAULT_THRESHOLDS)
    assert report.passed is False
    assert any("recall_at_3" in f for f in report.failures)
    print("[PASS] Test 2: Recall@3 regression detected and failed.")


def test_3_recall_at_5_regression():
    m = copy.deepcopy(PASSING_METRICS)
    m["recall_at_5"] = 0.8800  # Threshold is 0.9000
    report = evaluate_regression(m, DEFAULT_THRESHOLDS)
    assert report.passed is False
    assert any("recall_at_5" in f for f in report.failures)
    print("[PASS] Test 3: Recall@5 regression detected and failed.")


def test_4_mrr_regression():
    m = copy.deepcopy(PASSING_METRICS)
    m["mrr"] = 0.7800  # Threshold is 0.8000
    report = evaluate_regression(m, DEFAULT_THRESHOLDS)
    assert report.passed is False
    assert any("mrr" in f for f in report.failures)
    print("[PASS] Test 4: MRR regression detected and failed.")


def test_5_ndcg_at_5_regression():
    m = copy.deepcopy(PASSING_METRICS)
    m["ndcg_at_5"] = 0.8200  # Threshold is 0.8500
    report = evaluate_regression(m, DEFAULT_THRESHOLDS)
    assert report.passed is False
    assert any("ndcg_at_5" in f for f in report.failures)
    print("[PASS] Test 5: nDCG@5 regression detected and failed.")


def test_6_citation_precision_regression():
    m = copy.deepcopy(PASSING_METRICS)
    m["citation_precision"] = 0.8200  # Threshold is 0.8500
    report = evaluate_regression(m, DEFAULT_THRESHOLDS)
    assert report.passed is False
    assert any("citation_precision" in f for f in report.failures)
    print("[PASS] Test 6: Citation precision regression detected and failed.")


def test_7_citation_coverage_regression():
    m = copy.deepcopy(PASSING_METRICS)
    m["citation_coverage"] = 0.8800  # Threshold is 0.9000
    report = evaluate_regression(m, DEFAULT_THRESHOLDS)
    assert report.passed is False
    assert any("citation_coverage" in f for f in report.failures)
    print("[PASS] Test 7: Citation coverage regression detected and failed.")


def test_8_correct_refusal_rate_regression():
    m = copy.deepcopy(PASSING_METRICS)
    m["correct_refusal_rate"] = 0.8000  # Threshold is strictly 1.0000
    report = evaluate_regression(m, DEFAULT_THRESHOLDS)
    assert report.passed is False
    assert any("correct_refusal_rate" in f for f in report.failures)
    print("[PASS] Test 8: Correct refusal rate regression detected and failed.")


def test_9_false_refusal_rate_regression():
    m = copy.deepcopy(PASSING_METRICS)
    m["false_refusal_rate"] = 0.0800  # Threshold is <= 0.0500
    report = evaluate_regression(m, DEFAULT_THRESHOLDS)
    assert report.passed is False
    assert any("false_refusal_rate" in f for f in report.failures)
    print("[PASS] Test 9: False refusal rate excess detected and failed.")


def test_10_mean_latency_regression():
    m = copy.deepcopy(PASSING_METRICS)
    m["mean_latency_ms"] = 380.0  # Threshold is <= 350.0 ms
    report = evaluate_regression(m, DEFAULT_THRESHOLDS)
    assert report.passed is False
    assert any("mean_latency_ms" in f for f in report.failures)
    print("[PASS] Test 10: Mean latency excess detected and failed.")


def test_11_p95_latency_regression():
    m = copy.deepcopy(PASSING_METRICS)
    m["latency_p95_ms"] = 650.0  # Threshold is <= 600.0 ms
    report = evaluate_regression(m, DEFAULT_THRESHOLDS)
    assert report.passed is False
    assert any("latency_p95_ms" in f for f in report.failures)
    print("[PASS] Test 11: P95 latency excess detected and failed.")


def test_12_threshold_boundary_behavior():
    # Exactly on boundary values
    boundary_metrics = {
        "pass_rate": 0.9000,
        "recall_at_3": 0.8500,
        "recall_at_5": 0.9000,
        "mrr": 0.8000,
        "ndcg_at_5": 0.8500,
        "citation_precision": 0.8500,
        "citation_coverage": 0.9000,
        "correct_refusal_rate": 1.0000,
        "false_refusal_rate": 0.0500,
        "mean_latency_ms": 350.0,
        "latency_p95_ms": 600.0,
    }
    report = evaluate_regression(boundary_metrics, DEFAULT_THRESHOLDS)
    assert report.passed is True
    assert report.failed_checks == 0
    print("[PASS] Test 12: Exact threshold boundary values pass cleanly.")


def test_13_floating_point_tolerance_behavior():
    m = copy.deepcopy(PASSING_METRICS)
    # 0.89995 is within 0.0001 tolerance of 0.9000
    m["recall_at_5"] = 0.89995
    report = evaluate_regression(m, DEFAULT_THRESHOLDS)
    assert report.passed is True
    print("[PASS] Test 13: Numerical tolerance (1e-4) safely prevents precision drift false failures.")


def test_14_multiple_simultaneous_failures():
    m = copy.deepcopy(PASSING_METRICS)
    m["recall_at_5"] = 0.7000
    m["mrr"] = 0.5000
    m["mean_latency_ms"] = 500.0
    report = evaluate_regression(m, DEFAULT_THRESHOLDS)
    assert report.passed is False
    assert report.failed_checks == 3
    assert len(report.failures) == 3
    print("[PASS] Test 14: Multiple simultaneous regressions correctly identified and counted.")


def test_15_missing_metric_handling():
    m = copy.deepcopy(PASSING_METRICS)
    del m["recall_at_5"]
    report = evaluate_regression(m, DEFAULT_THRESHOLDS)
    assert report.passed is False
    assert any("Missing required metric 'recall_at_5'" in f for f in report.failures)
    print("[PASS] Test 15: Missing required metric cleanly captured as a gate violation.")


def test_16_malformed_configuration_handling():
    m = copy.deepcopy(PASSING_METRICS)
    m["ndcg_at_5"] = "non-numeric-value"
    report = evaluate_regression(m, DEFAULT_THRESHOLDS)
    assert report.passed is False
    assert any("Invalid numeric type" in f for f in report.failures)
    print("[PASS] Test 16: Malformed / non-numeric metric captured safely without exceptions.")


def test_17_regression_cli_exit_codes():
    python_exe = sys.executable

    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)

        # 17a: Passing payload -> Exit 0
        passing_file = tmp_path / "pass.json"
        with open(passing_file, "w", encoding="utf-8") as f:
            json.dump({"metrics": PASSING_METRICS}, f)

        res_pass = subprocess.run(
            [python_exe, "-m", "app.eval.regression", "--input", str(passing_file)],
            capture_output=True,
            text=True,
        )
        assert res_pass.returncode == 0, f"Expected 0, got {res_pass.returncode}: {res_pass.stderr}"

        # 17b: Failing payload -> Exit 1
        failing_metrics = copy.deepcopy(PASSING_METRICS)
        failing_metrics["recall_at_5"] = 0.7500
        failing_file = tmp_path / "fail.json"
        with open(failing_file, "w", encoding="utf-8") as f:
            json.dump({"metrics": failing_metrics}, f)

        res_fail = subprocess.run(
            [python_exe, "-m", "app.eval.regression", "--input", str(failing_file)],
            capture_output=True,
            text=True,
        )
        assert res_fail.returncode == 1, f"Expected 1, got {res_fail.returncode}"
        assert "FAIL" in res_fail.stdout

        # 17c: Nonexistent file -> Exit 2
        res_missing = subprocess.run(
            [python_exe, "-m", "app.eval.regression", "--input", str(tmp_path / "missing.json")],
            capture_output=True,
            text=True,
        )
        assert res_missing.returncode == 2, f"Expected 2, got {res_missing.returncode}"

    print("[PASS] Test 17: Standalone regression CLI exit codes verified (0=pass, 1=fail, 2=error).")


def test_18_eval_cli_check_regression_integration():
    python_exe = sys.executable

    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        db_file = tmp_path / "test_ci.db"
        out_json = tmp_path / "results.json"
        db_url = f"sqlite+aiosqlite:///{db_file}"

        # Run 2 cases with --check-regression
        cmd = [
            python_exe,
            "-m",
            "app.eval.cli",
            "--limit",
            "2",
            "--judge",
            "deterministic",
            "--offline",
            "--output-json",
            str(out_json),
            "--check-regression",
            "--db-url",
            db_url,
        ]
        res = subprocess.run(cmd, capture_output=True, text=True)
        assert res.returncode == 0, f"CLI benchmark run failed: {res.stderr}\n{res.stdout}"
        assert out_json.exists(), "Exported JSON was not generated."

        with open(out_json, "r", encoding="utf-8") as f:
            data = json.load(f)

        assert "benchmark_name" in data
        assert "metrics" in data
        assert "regression_gate" in data
        assert data["overall_passed"] is True

        # Now test intentional failure using a strict custom threshold
        strict_thresholds_file = tmp_path / "strict.json"
        with open(strict_thresholds_file, "w", encoding="utf-8") as f:
            # Unattainable 1.05 threshold forces regression failure
            json.dump({"min_recall_at_5": 1.05}, f)

        cmd_fail = [
            python_exe,
            "-m",
            "app.eval.cli",
            "--limit",
            "2",
            "--judge",
            "deterministic",
            "--offline",
            "--thresholds-file",
            str(strict_thresholds_file),
            "--check-regression",
            "--db-url",
            db_url,
        ]
        res_fail = subprocess.run(cmd_fail, capture_output=True, text=True)
        assert res_fail.returncode == 1, f"Expected CLI to exit 1 on regression failure, got {res_fail.returncode}"
        assert "[CI GATE FAILED]" in res_fail.stdout

        # Test exit code 2 on nonexistent thresholds file
        cmd_invalid = [
            python_exe,
            "-m",
            "app.eval.cli",
            "--thresholds-file",
            str(tmp_path / "missing_thresholds.json"),
        ]
        res_invalid = subprocess.run(cmd_invalid, capture_output=True, text=True)
        assert res_invalid.returncode == 2, f"Expected 2 on invalid config, got {res_invalid.returncode}"

    print("[PASS] Test 18: Evaluation CLI --check-regression integration, exit code 1 failure, and exit code 2 invalid config verified.")


def run_all_tests():
    print("=" * 80)
    print("RUNNING RAG EVALUATION CI REGRESSION GATE TEST SUITE")
    print("=" * 80)

    test_1_all_metrics_pass()
    test_2_recall_at_3_regression()
    test_3_recall_at_5_regression()
    test_4_mrr_regression()
    test_5_ndcg_at_5_regression()
    test_6_citation_precision_regression()
    test_7_citation_coverage_regression()
    test_8_correct_refusal_rate_regression()
    test_9_false_refusal_rate_regression()
    test_10_mean_latency_regression()
    test_11_p95_latency_regression()
    test_12_threshold_boundary_behavior()
    test_13_floating_point_tolerance_behavior()
    test_14_multiple_simultaneous_failures()
    test_15_missing_metric_handling()
    test_16_malformed_configuration_handling()
    test_17_regression_cli_exit_codes()
    test_18_eval_cli_check_regression_integration()

    print("=" * 80)
    print("ALL 18 REGRESSION ENGINE TESTS PASSED SUCCESSFULLY!")
    print("=" * 80)


if __name__ == "__main__":
    run_all_tests()
