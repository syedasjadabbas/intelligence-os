"""
Guardrails and Sufficiency Checking Module for RAG Pipeline.
Enforces grounded answers, prevents hallucinations, evaluates evidence sufficiency,
and manages refusal triggers with calibrated relevance thresholds.
"""

import logging
from typing import List, Tuple
from app.core.config import settings
from app.services.retrieval_service import SearchResultItem

logger = logging.getLogger(__name__)

# Calibrated relevance score threshold cut-off.
# Reduced from 0.75 -> 0.45 to prevent false refusal on valid queries with moderate similarity.
RELEVANCE_THRESHOLD: float = getattr(settings, "GUARDRAIL_SCORE_THRESHOLD", 0.45)


def is_context_sufficient(
    candidates: List[SearchResultItem],
    threshold: float = RELEVANCE_THRESHOLD,
) -> bool:
    """
    Evaluates whether the retrieved and reranked candidate chunks provide
    sufficient evidence to attempt answering the user query.
    
    Returns True if at least one candidate chunk meets or exceeds the
    calibrated relevance threshold (0.45). Returns False if candidates list
    is empty or all candidates fall below the cut-off.
    """
    if not candidates:
        return False

    for c in candidates:
        score = c.rerank_score if c.rerank_score is not None else c.score
        if score >= threshold:
            return True

    logger.info(
        f"Context sufficiency check: No candidates exceeded threshold {threshold}. "
        f"Max score observed: {max((c.rerank_score if c.rerank_score is not None else c.score) for c in candidates):.4f}"
    )
    return False


def filter_sufficient_candidates(
    candidates: List[SearchResultItem],
    threshold: float = RELEVANCE_THRESHOLD,
    min_candidates: int = 3,
    max_candidates: int = 5,
) -> List[SearchResultItem]:
    """
    Ensures moderate-scoring candidates (score >= 0.45) are not pruned out.
    Allows top 3-5 candidates through to the context builder regardless of strict margins,
    preventing over-aggressive rejection while maintaining context quality.
    """
    if not candidates:
        return []

    # Sort descending by rerank score or base score
    sorted_candidates = sorted(
        candidates,
        key=lambda x: x.rerank_score if x.rerank_score is not None else (x.score or 0.0),
        reverse=True,
    )

    # Filter candidates meeting the calibrated cut-off
    sufficient = [
        c
        for c in sorted_candidates
        if (c.rerank_score if c.rerank_score is not None else c.score) >= threshold
    ]

    # If fewer than min_candidates meet threshold but candidates exist,
    # preserve at least top min_candidates if any candidate has positive score
    if len(sufficient) < min_candidates:
        sufficient = sorted_candidates[:min_candidates]

    return sufficient[:max_candidates]


def evaluate_grounded_refusal_guardrail(
    answer: str,
    is_sufficient: bool = True,
) -> Tuple[str, bool]:
    """
    Evaluates whether the grounded refusal guardrail was triggered.
    
    If the context was deemed insufficient or the model indicated lack of evidence,
    returns (settings.INSUFFICIENT_EVIDENCE_PHRASE, True).
    Otherwise returns (answer, False).
    """
    if not is_sufficient:
        return settings.INSUFFICIENT_EVIDENCE_PHRASE, True

    if not answer or not answer.strip():
        return settings.INSUFFICIENT_EVIDENCE_PHRASE, True

    lower_ans = answer.lower()
    refusal_markers = [
        settings.INSUFFICIENT_EVIDENCE_PHRASE.lower(),
        "cannot find sufficient evidence",
        "insufficient evidence",
        "does not contain sufficient",
        "does not contain any information",
        "no mention in the provided",
        "no information provided",
    ]

    for marker in refusal_markers:
        if marker in lower_ans:
            return settings.INSUFFICIENT_EVIDENCE_PHRASE, True

    return answer.strip(), False
