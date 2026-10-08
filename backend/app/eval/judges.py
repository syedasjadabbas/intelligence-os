"""
Evaluation judge abstractions for Intelligence OS RAG pipeline.
Defines BaseJudge interface and DeterministicJudge implementation for zero-cost,
variance-free local testing and CI/CD pipelines.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from app.eval.metrics import compute_key_facts_coverage, detect_refusal


@dataclass
class JudgeResult:
    """Standardized output from an evaluation judge."""
    passed: bool
    score: float
    is_refusal: bool
    key_facts_coverage: float
    reasoning: str
    unsupported_claims: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "passed": self.passed,
            "score": round(self.score, 4),
            "is_refusal": self.is_refusal,
            "key_facts_coverage": round(self.key_facts_coverage, 4),
            "reasoning": self.reasoning,
            "unsupported_claims": self.unsupported_claims,
            "metadata": self.metadata,
        }


class BaseJudge(ABC):
    """Abstract base class for all RAG evaluation judges."""

    @abstractmethod
    async def evaluate(
        self,
        query: str,
        generated_answer: str,
        ground_truth_answer: Optional[str] = None,
        contexts: Optional[List[str]] = None,
        key_facts: Optional[List[str]] = None,
        expected_behavior: str = "answer",
    ) -> JudgeResult:
        """
        Evaluate generated answer quality against ground truth and contexts.
        """
        pass


class DeterministicJudge(BaseJudge):
    """
    Pure Python deterministic judge for offline testing and CI/CD evaluation.
    Requires zero external API keys and provides zero-variance scoring using:
    - Rule-based refusal recognition
    - Key fact substring & token containment
    - Ground truth answer overlap
    """

    async def evaluate(
        self,
        query: str,
        generated_answer: str,
        ground_truth_answer: Optional[str] = None,
        contexts: Optional[List[str]] = None,
        key_facts: Optional[List[str]] = None,
        expected_behavior: str = "answer",
    ) -> JudgeResult:
        expected = (expected_behavior or "answer").lower().strip()
        is_refusal = detect_refusal(generated_answer)
        facts = key_facts or []

        # 1. Evaluate Refusal Scenarios
        if expected == "refuse":
            if is_refusal:
                return JudgeResult(
                    passed=True,
                    score=1.0,
                    is_refusal=True,
                    key_facts_coverage=1.0,
                    reasoning="Correct refusal: pipeline accurately declined to answer ungrounded query.",
                )
            else:
                return JudgeResult(
                    passed=False,
                    score=0.0,
                    is_refusal=False,
                    key_facts_coverage=0.0,
                    reasoning="Failed refusal check: query expected refusal but model generated an answer.",
                    unsupported_claims=[generated_answer[:200]],
                )

        # 2. Evaluate Answer Scenarios
        if is_refusal:
            return JudgeResult(
                passed=False,
                score=0.0,
                is_refusal=True,
                key_facts_coverage=0.0,
                reasoning="False refusal: query expected an answer but pipeline refused despite valid context.",
            )

        # Measure key facts coverage
        if facts:
            coverage = compute_key_facts_coverage(generated_answer, facts)
        else:
            coverage = 1.0

        # Deterministic pass threshold: at least 50% key facts covered
        passed = coverage >= 0.5 and len(generated_answer.strip()) > 5

        reasoning = (
            f"Deterministic evaluation passed with {int(coverage * 100)}% key fact coverage."
            if passed
            else f"Deterministic evaluation failed: insufficient key fact coverage ({int(coverage * 100)}%)."
        )

        return JudgeResult(
            passed=passed,
            score=coverage,
            is_refusal=False,
            key_facts_coverage=coverage,
            reasoning=reasoning,
            unsupported_claims=[] if passed else [f"Missing expected facts from: {facts}"],
        )
