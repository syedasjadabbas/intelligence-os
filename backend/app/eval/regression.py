"""
Regression engine for Intelligence OS RAG Evaluation CI Quality Gates.
Validates benchmark evaluation metrics against version-controlled thresholds,
identifies quality regressions, and produces structured pass/fail reports with exit codes.
"""
import argparse
from dataclasses import asdict, dataclass, field
import json
import logging
from pathlib import Path
import sys
from typing import Any, Dict, List, Optional

from app.eval.config import DEFAULT_THRESHOLDS, EvaluationThresholds, MetricThreshold

logger = logging.getLogger("eval-regression")


@dataclass
class MetricCheckResult:
    """Individual metric regression check outcome."""
    metric_name: str
    actual_value: Optional[float]
    target_value: float
    comparator: str
    passed: bool
    message: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class RegressionReport:
    """Consolidated regression evaluation report."""
    passed: bool
    total_checks: int
    passed_checks: int
    failed_checks: int
    results: List[MetricCheckResult] = field(default_factory=list)
    failures: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "passed": self.passed,
            "total_checks": self.total_checks,
            "passed_checks": self.passed_checks,
            "failed_checks": self.failed_checks,
            "failures": self.failures,
            "checks": [r.to_dict() for r in self.results],
        }

    def format_summary_table(self) -> str:
        """Renders an ASCII summary table suitable for terminal and CI logs."""
        headers = ["Metric", "Actual", "Target", "Status", "Note"]
        widths = [26, 12, 12, 8, 30]

        sep = "+-" + "-+-".join("-" * w for w in widths) + "-+"
        header_line = "| " + " | ".join(h.ljust(widths[i]) for i, h in enumerate(headers)) + " |"

        data_lines = []
        for r in self.results:
            act_str = f"{r.actual_value:.4f}" if r.actual_value is not None else "None"
            target_str = f"{r.comparator} {r.target_value:.4f}"
            status_str = "PASS" if r.passed else "FAIL"
            note_str = "Meets requirement" if r.passed else r.message

            line = (
                f"| {r.metric_name.ljust(widths[0])} "
                f"| {act_str.ljust(widths[1])} "
                f"| {target_str.ljust(widths[2])} "
                f"| {status_str.ljust(widths[3])} "
                f"| {note_str[:widths[4]].ljust(widths[4])} |"
            )
            data_lines.append(line)

        banner = (
            "=======================================================================================\n"
            f"                  RAG EVALUATION REGRESSION GATE REPORT - {'PASSED' if self.passed else 'FAILED'}\n"
            "======================================================================================="
        )

        summary_stats = (
            f"Total Checks: {self.total_checks} | Passed: {self.passed_checks} | "
            f"Regressions/Violations: {self.failed_checks}\n"
        )

        return "\n".join([banner, summary_stats, sep, header_line, sep] + data_lines + [sep])


def evaluate_regression(
    metrics: Dict[str, Any],
    thresholds: Optional[EvaluationThresholds] = None,
) -> RegressionReport:
    """
    Evaluates observed evaluation metrics against strict regression thresholds.
    Distinguishes minimum requirements (actual >= target) and maximum allowances (actual <= target).
    Applies explicit numerical tolerances to prevent false failures from IEEE 754 precision drift.
    """
    if thresholds is None:
        thresholds = DEFAULT_THRESHOLDS

    specs = thresholds.get_threshold_specs()
    results: List[MetricCheckResult] = []
    failures: List[str] = []

    for spec in specs:
        raw_val = metrics.get(spec.name)

        # Check for missing or None metric values
        if raw_val is None:
            msg = f"Missing required metric '{spec.name}' (expected {spec.comparator} {spec.target})"
            results.append(
                MetricCheckResult(
                    metric_name=spec.name,
                    actual_value=None,
                    target_value=spec.target,
                    comparator=spec.comparator,
                    passed=False,
                    message=msg,
                )
            )
            failures.append(msg)
            continue

        try:
            actual = float(raw_val)
        except (ValueError, TypeError):
            msg = f"Invalid numeric type for '{spec.name}': {raw_val}"
            results.append(
                MetricCheckResult(
                    metric_name=spec.name,
                    actual_value=None,
                    target_value=spec.target,
                    comparator=spec.comparator,
                    passed=False,
                    message=msg,
                )
            )
            failures.append(msg)
            continue

        # Evaluate comparison with numerical tolerance
        tol = spec.tolerance
        passed = False
        message = ""

        if spec.comparator == ">=":
            passed = actual >= (spec.target - tol)
            if not passed:
                delta = actual - spec.target
                message = f"Regressed by {delta:.4f} below threshold {spec.target:.4f}"
        elif spec.comparator == "<=":
            passed = actual <= (spec.target + tol)
            if not passed:
                delta = actual - spec.target
                message = f"Exceeded limit by +{delta:.4f} above threshold {spec.target:.4f}"
        elif spec.comparator == "==":
            passed = abs(actual - spec.target) <= tol
            if not passed:
                delta = actual - spec.target
                message = f"Expected exact value {spec.target:.4f}, got {actual:.4f} (diff: {delta:+.4f})"
        elif spec.comparator == ">":
            passed = actual > (spec.target - tol)
            if not passed:
                delta = actual - spec.target
                message = f"Must be strictly greater than {spec.target:.4f}, got {actual:.4f}"
        elif spec.comparator == "<":
            passed = actual < (spec.target + tol)
            if not passed:
                delta = actual - spec.target
                message = f"Must be strictly less than {spec.target:.4f}, got {actual:.4f}"
        else:
            passed = False
            message = f"Unsupported comparator '{spec.comparator}'"

        if not passed:
            failures.append(f"[{spec.name}] {message}")

        results.append(
            MetricCheckResult(
                metric_name=spec.name,
                actual_value=actual,
                target_value=spec.target,
                comparator=spec.comparator,
                passed=passed,
                message=message,
            )
        )

    passed_count = sum(1 for r in results if r.passed)
    failed_count = sum(1 for r in results if not r.passed)
    overall_passed = failed_count == 0

    return RegressionReport(
        passed=overall_passed,
        total_checks=len(results),
        passed_checks=passed_count,
        failed_checks=failed_count,
        results=results,
        failures=failures,
    )


def main() -> None:
    """CLI entrypoint for standalone regression check on exported evaluation JSON."""
    parser = argparse.ArgumentParser(
        prog="python -m app.eval.regression",
        description="Intelligence OS RAG Quality Regression Gate Checker",
    )
    parser.add_argument(
        "--input",
        type=str,
        required=True,
        help="Path to the evaluation output JSON file to check.",
    )
    parser.add_argument(
        "--thresholds",
        type=str,
        default=None,
        help="Optional path to custom thresholds JSON configuration.",
    )
    parser.add_argument(
        "--output-summary",
        type=str,
        default=None,
        help="Optional path to write GitHub Actions Step Summary markdown.",
    )

    args = parser.parse_args()

    input_path = Path(args.input)
    if not input_path.exists():
        print(f"[ERROR] Evaluation output JSON file not found: {input_path}")
        sys.exit(2)

    try:
        with open(input_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as exc:
        print(f"[ERROR] Failed to parse JSON file {input_path}: {exc}")
        sys.exit(2)

    # Extract metrics dict from exported payload
    # Handles both direct metric dict and standard eval output structure
    metrics = data.get("metrics") or data.get("summary_metrics") or data

    thresholds = None
    if args.thresholds:
        t_path = Path(args.thresholds)
        if not t_path.exists():
            print(f"[ERROR] Thresholds file not found: {t_path}")
            sys.exit(2)
        try:
            thresholds = EvaluationThresholds.from_file(t_path)
        except Exception as exc:
            print(f"[ERROR] Failed to load thresholds from {t_path}: {exc}")
            sys.exit(2)

    report = evaluate_regression(metrics=metrics, thresholds=thresholds)

    # Print terminal report
    print(report.format_summary_table())

    # Write GitHub Step Summary if requested
    if args.output_summary:
        out_summary_path = Path(args.output_summary)
        try:
            with open(out_summary_path, "a", encoding="utf-8") as sf:
                sf.write(f"\n### 🎯 RAG Quality Regression Gate: {'✅ PASSED' if report.passed else '❌ FAILED'}\n\n")
                sf.write(f"| Metric | Actual | Target | Status |\n")
                sf.write(f"| :--- | :--- | :--- | :---: |\n")
                for r in report.results:
                    act_str = f"{r.actual_value:.4f}" if r.actual_value is not None else "None"
                    stat_icon = "✅" if r.passed else "❌"
                    sf.write(f"| `{r.metric_name}` | {act_str} | {r.comparator} {r.target_value:.4f} | {stat_icon} |\n")
                if not report.passed:
                    sf.write("\n**Quality Violations:**\n")
                    for fl in report.failures:
                        sf.write(f"- ⚠️ {fl}\n")
        except Exception as exc:
            logger.warning(f"Could not write to summary file {args.output_summary}: {exc}")

    sys.exit(0 if report.passed else 1)


if __name__ == "__main__":
    main()
