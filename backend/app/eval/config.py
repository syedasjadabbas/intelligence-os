"""
RAG Evaluation Threshold Configuration for CI Regression Gates.
Defines explicit, deterministic quality bars calibrated against the 50-case
golden benchmark dataset baseline.
"""
from dataclasses import asdict, dataclass, field
import json
from pathlib import Path
from typing import Any, Dict, List, Optional


@dataclass(frozen=True)
class MetricThreshold:
    """Specification of an evaluation metric threshold."""
    name: str
    target: float
    comparator: str  # ">=", "<=", "==", ">", "<"
    description: str
    tolerance: float = 0.0001
    is_critical: bool = True  # If True, violation fails the CI gate


@dataclass
class EvaluationThresholds:
    """
    Standard regression gate thresholds for deterministic CI benchmarks.
    Calibrated against the 50-case golden benchmark baseline:
      - Recall@5: baseline ~0.9667 (threshold: >= 0.9000)
      - Recall@3: baseline ~0.9000 (threshold: >= 0.8500)
      - MRR: baseline ~0.8458 (threshold: >= 0.8000)
      - nDCG@5: baseline ~0.8662 (threshold: >= 0.8500)
      - Citation Precision: baseline ~0.8800 (threshold: >= 0.8500)
      - Citation Coverage: baseline ~0.9500 (threshold: >= 0.9000)
      - Correct Refusal Rate (CRR): baseline 1.0000 (threshold: == 1.0000)
      - False Refusal Rate (FRR): baseline 0.0000 (threshold: <= 0.0500)
      - Mean Latency: baseline ~210-250ms (threshold: <= 350.0 ms)
      - P95 Latency: baseline ~300-400ms (threshold: <= 600.0 ms)
      - Overall Pass Rate: baseline 96.0% (threshold: >= 0.9000)
    """
    # 1. Retrieval & Ranking Quality
    min_recall_at_3: float = 0.8500
    min_recall_at_5: float = 0.9000
    min_mrr: float = 0.8000
    min_ndcg_at_5: float = 0.8500

    # 2. Citation & Grounding Coverage
    min_citation_precision: float = 0.8500
    min_citation_coverage: float = 0.9000

    # 3. Guardrail Refusals
    min_correct_refusal_rate: float = 1.0000
    max_false_refusal_rate: float = 0.0500

    # 4. Latency Performance (milliseconds, calibrated for CI shared-CPU runners)
    max_mean_latency_ms: float = 350.0
    max_p95_latency_ms: float = 600.0

    # 5. Overall Test Case Pass Rate
    min_pass_rate: float = 0.9000

    def get_threshold_specs(self) -> List[MetricThreshold]:
        """Returns ordered list of strongly-typed threshold specifications."""
        return [
            MetricThreshold(
                name="recall_at_3",
                target=self.min_recall_at_3,
                comparator=">=",
                description="Minimum Recall@3 across answerable queries.",
            ),
            MetricThreshold(
                name="recall_at_5",
                target=self.min_recall_at_5,
                comparator=">=",
                description="Minimum Recall@5 across answerable queries.",
            ),
            MetricThreshold(
                name="mrr",
                target=self.min_mrr,
                comparator=">=",
                description="Mean Reciprocal Rank of first relevant chunk.",
            ),
            MetricThreshold(
                name="ndcg_at_5",
                target=self.min_ndcg_at_5,
                comparator=">=",
                description="Normalized Discounted Cumulative Gain at rank 5.",
            ),
            MetricThreshold(
                name="citation_precision",
                target=self.min_citation_precision,
                comparator=">=",
                description="Fraction of citations that match ground truth evidence.",
            ),
            MetricThreshold(
                name="citation_coverage",
                target=self.min_citation_coverage,
                comparator=">=",
                description="Fraction of ground truth evidence anchors cited.",
            ),
            MetricThreshold(
                name="correct_refusal_rate",
                target=self.min_correct_refusal_rate,
                comparator="==",
                description="Strict refusal rate for unanswerable/out-of-domain queries.",
            ),
            MetricThreshold(
                name="false_refusal_rate",
                target=self.max_false_refusal_rate,
                comparator="<=",
                description="Maximum allowable false refusals on answerable queries.",
            ),
            MetricThreshold(
                name="mean_latency_ms",
                target=self.max_mean_latency_ms,
                comparator="<=",
                description="Maximum allowable mean pipeline latency in milliseconds.",
            ),
            MetricThreshold(
                name="latency_p95_ms",
                target=self.max_p95_latency_ms,
                comparator="<=",
                description="Maximum allowable 95th percentile latency in milliseconds.",
            ),
            MetricThreshold(
                name="pass_rate",
                target=self.min_pass_rate,
                comparator=">=",
                description="Minimum percentage of test cases passing all quality checks.",
            ),
        ]

    def to_dict(self) -> Dict[str, Any]:
        """Serializes thresholds to a plain dictionary."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "EvaluationThresholds":
        """Constructs thresholds from a dictionary, ignoring extraneous keys."""
        valid_fields = {f for f in cls.__dataclass_fields__}
        filtered = {k: float(v) for k, v in data.items() if k in valid_fields}
        return cls(**filtered)

    @classmethod
    def from_file(cls, path: Path) -> "EvaluationThresholds":
        """Loads thresholds from a JSON file."""
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return cls.from_dict(data)


# Default singleton instance for standard CI runs
DEFAULT_THRESHOLDS = EvaluationThresholds()
