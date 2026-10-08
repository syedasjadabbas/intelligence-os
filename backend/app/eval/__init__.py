"""
Intelligence OS - RAG Evaluation Framework.
Provides modular and end-to-end evaluation metrics, decoupled evidence resolution,
runner harness, and regression testing for enterprise multi-tenant RAG.
"""

from app.eval.metrics import (
    compute_recall_at_k,
    compute_mrr,
    compute_rank_shift,
    compute_citation_metrics,
    compute_refusal_metrics,
    compute_retrieval_metrics,
    detect_refusal,
    matches_evidence_anchor,
)
from app.eval.judges import BaseJudge, DeterministicJudge, JudgeResult
from app.eval.runner import EvalRunner

__all__ = [
    "compute_recall_at_k",
    "compute_mrr",
    "compute_rank_shift",
    "compute_citation_metrics",
    "compute_refusal_metrics",
    "compute_retrieval_metrics",
    "detect_refusal",
    "matches_evidence_anchor",
    "BaseJudge",
    "DeterministicJudge",
    "JudgeResult",
    "EvalRunner",
]
