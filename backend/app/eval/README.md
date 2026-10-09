# Intelligence OS - RAG Quality Evaluation & CI Regression Gate

This directory contains the automated RAG evaluation framework and continuous integration (CI) quality gates for Intelligence OS.

---

## 1. Overview & Architecture

The evaluation system measures retrieval relevance, ranking effectiveness, answer faithfulness, citation accuracy, and refusal reliability.

In CI, evaluations run in **deterministic offline mode** to ensure:
- **Reproducibility**: Identical inputs yield identical metrics across local machines and CI runners.
- **Independence**: Zero external credentials (`GEMINI_API_KEY`, `OPENAI_API_KEY`, `COHERE_API_KEY`) required.
- **Speed**: Runs the 50-case golden benchmark in seconds without network rate limits.
- **Reliability**: No false CI failures caused by external API downtime, network jitter, or non-deterministic LLM variance.

---

## 2. Deterministic CI Judge vs. LLM Judge

| Dimension | Deterministic CI Judge (`--judge deterministic`) | LLM-as-a-Judge (`--judge llm`) |
| :--- | :--- | :--- |
| **Purpose** | Fast, repeatable CI regression gating on PRs/pushes | In-depth qualitative semantic evaluation and audits |
| **Execution** | Pure rule-based lexical matching, nDCG, MRR, recall | LLM prompt scoring (Faithfulness, Correctness, Completeness) |
| **Credentials** | None required (`--offline`) | Requires Gemini or OpenAI API keys |
| **Environment** | Clean CI runner, ephemeral SQLite database | Staging/Production environments, admin dashboard |

---

## 3. How to Run Locally

### A. Run Deterministic Evaluation CLI
Execute the benchmark offline using the deterministic judge:

```bash
# Standard benchmark run with machine-readable JSON output
python -m app.eval.cli --judge deterministic --offline --output-json eval-results.json

# Run with CI regression gate enforcement (exits 1 on quality degradation)
python -m app.eval.cli --judge deterministic --offline --check-regression --output-json eval-results.json

# Sliced benchmark run for quick verification (first 10 test cases)
python -m app.eval.cli --limit 10 --judge deterministic --offline
```

### B. Run the Standalone Regression Gate
Validate any exported evaluation JSON against regression thresholds:

```bash
python -m app.eval.regression --input eval-results.json

# With custom threshold configuration override:
python -m app.eval.regression --input eval-results.json --thresholds custom_thresholds.json

# With GitHub Actions step summary generation:
python -m app.eval.regression --input eval-results.json --output-summary $GITHUB_STEP_SUMMARY
```

### C. Run Regression Unit & Integration Tests
Execute the comprehensive regression engine test suite:

```bash
python test_eval_regression.py
```

---

## 4. Regression Thresholds Reference

Thresholds are version-controlled in `backend/app/eval/config.py`:

| Metric | Comparator | Threshold | Description | Rationale |
| :--- | :---: | :---: | :--- | :--- |
| **Recall@3** | `>=` | `0.8500` | Fraction of relevant documents retrieved in top 3 | Ensures core evidence is immediately accessible in top results. |
| **Recall@5** | `>=` | `0.9000` | Fraction of relevant documents retrieved in top 5 | Baseline golden benchmark achieves 0.94+. Allows tolerance for slight variations. |
| **MRR** | `>=` | `0.8000` | Mean Reciprocal Rank of first relevant document | Ensures highest-ranked chunk is near the top of the context window. |
| **nDCG@5** | `>=` | `0.8500` | Normalized Discounted Cumulative Gain at rank 5 | Evaluates graded relevance ranking quality across multiple chunks. |
| **Citation Precision** | `>=` | `0.8500` | Fraction of cited sources that contain ground truth facts | Prevents hallucinated or irrelevant document citations. |
| **Citation Coverage** | `>=` | `0.9000` | Fraction of required ground-truth facts covered by citations | Guarantees all factual claims are grounded with citations. |
| **Correct Refusal Rate** | `==` | `1.0000` | Fraction of unanswerable queries correctly refused | Critical security metric: zero tolerance for answering out-of-scope/adversarial queries. |
| **False Refusal Rate** | `<=` | `0.0500` | Fraction of answerable queries incorrectly refused | Prevents overly timid retrieval from refusing valid queries. |
| **Mean Latency** | `<=` | `350.0 ms` | Average end-to-end evaluation latency per case | Prevents algorithmic slowdown while allowing CI runner CPU shared contention. |
| **P95 Latency** | `<=` | `600.0 ms` | 95th percentile evaluation latency | Catches long-tail latency spikes in retrieval or reranking. |
| **Pass Rate** | `>=` | `0.9000` | Fraction of total test cases meeting all criteria | Global quality safeguard: at least 90% of benchmark cases must pass. |

*Note: Floating-point comparisons apply an explicit numerical tolerance (`1e-4`) to eliminate IEEE 754 precision drift false failures.*

---

## 5. How to Intentionally Change a Threshold

Thresholds represent an agreed quality contract. They are never dynamically calculated or automatically widened.

To modify thresholds:
1. Open `backend/app/eval/config.py`.
2. Update the target value in `DEFAULT_THRESHOLDS` or the corresponding field on `EvaluationThresholds`.
3. Document the engineering rationale in the commit message and PR description.
4. Verify tests pass via `python test_eval_regression.py`.

Alternatively, for ad-hoc experiment evaluation, supply a JSON threshold override file via `--thresholds-file <path>` in the CLI.

---

## 6. Interpreting a Failed Evaluation

When the regression gate fails, the CLI prints an itemized report and exits with status code `1`:

```
=======================================================================================
                  RAG EVALUATION REGRESSION GATE REPORT - FAILED
=======================================================================================
Total Checks: 11 | Passed: 10 | Regressions/Violations: 1

+----------------------+---------+------------+--------+---------------------------------------+
| Metric               | Actual  | Target     | Status | Note                                  |
+----------------------+---------+------------+--------+---------------------------------------+
| recall_at_3          | 0.8800  | >= 0.8500  | PASS   | Meets requirement                     |
| recall_at_5          | 0.8200  | >= 0.9000  | FAIL   | Regression: 0.8200 < 0.9000 (diff: -0.0800) |
| mrr                  | 0.9200  | >= 0.8000  | PASS   | Meets requirement                     |
...
[CI GATE FAILED] 1 quality regression(s) detected.
```

Steps to diagnose:
1. **Identify the failing metric(s)** in the regression table (marked with `FAIL`).
2. **Inspect the machine-readable artifact** (`eval-results.json`): check the `results` array for itemized per-case failures and `failure_reason`.
3. **Check query types**: Determine if regressions are concentrated in specific query types (e.g., `multi_hop`, `adversarial`, `domain_specific`).
4. **Inspect retrieval vs reranking**: If Recall@5 dropped, inspect hybrid search candidate pooling. If MRR/nDCG dropped while Recall@5 remained high, inspect cross-encoder reranker scoring.

---

## 7. CI Workflow & Artifacts

The GitHub Actions workflow is defined in `.github/workflows/rag-evaluation.yml`.

### Workflow Pipeline:
1. **Checkout**: Clones the commit.
2. **Setup Python**: Uses Python 3.11 with pip caching.
3. **Install Dependencies**: Installs `backend/requirements.txt`.
4. **Execute Deterministic Benchmark**: Runs `app.eval.cli` with `--check-regression`, `--output-json eval-results.json`, and an isolated SQLite database URL (`--db-url sqlite+aiosqlite:///ci_eval.db`).
5. **Publish Artifact**: Uploads `eval-results.json` via `actions/upload-artifact@v4` with a 14-day retention period.
6. **Step Summary**: Appends a markdown table of all checked metrics to `$GITHUB_STEP_SUMMARY`.
