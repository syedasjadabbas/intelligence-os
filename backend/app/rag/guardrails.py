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
    
    If cross-encoder rerank_score is present (unnormalized logits),
    scores >= -6.0 indicate semantic relevance (completely irrelevant chunks score < -10.0).
    If only base similarity score is present, checks against threshold (0.45).
    """
    if not candidates:
        return False

    for c in candidates:
        if c.rerank_score is not None:
            if c.rerank_score >= -8.0:
                return True
        elif c.score is not None and c.score >= threshold:
            return True

    logger.info(
        f"Context sufficiency check: No candidates exceeded sufficiency threshold. "
        f"Max score observed: {max(((c.rerank_score if c.rerank_score is not None else c.score) or 0.0) for c in candidates):.4f}"
    )
    return False


def filter_sufficient_candidates(
    candidates: List[SearchResultItem],
    threshold: float = RELEVANCE_THRESHOLD,
    min_candidates: int = 3,
    max_candidates: int = 5,
) -> List[SearchResultItem]:
    """
    Ensures moderate-scoring candidates are not pruned out.
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

    sufficient = [
        c
        for c in sorted_candidates
        if (
            (c.rerank_score >= -8.0)
            if c.rerank_score is not None
            else ((c.score or 0.0) >= threshold)
        )
    ]

    # If fewer than min_candidates meet threshold but candidates exist,
    # preserve at least top min_candidates
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

    cleaned_answer = answer.strip()
    lower_ans = cleaned_answer.lower()

    # Absent fact indicators where the model directly notes the document does not specify the requested fact
    absent_indicators = [
        "not specified",
        "has not specified",
        "does not specify",
        "not explicitly stated",
        "not provided in the",
        "no mention of",
        "does not mention",
    ]
    for ind in absent_indicators:
        if ind in lower_ans and not any(k in lower_ans for k in ["except", "excluding"]):
            return settings.INSUFFICIENT_EVIDENCE_PHRASE, True

    refusal_phrase = settings.INSUFFICIENT_EVIDENCE_PHRASE.lower()

    # If the answer IS purely the refusal phrase or contains strong refusal markers
    refusal_markers = [
        refusal_phrase,
        "cannot find sufficient evidence",
        "insufficient evidence",
        "does not contain sufficient",
        "does not contain any information",
        "no mention in the provided",
        "no information provided",
        "cannot provide information",
        "cannot answer this question",
        "unable to answer",
    ]

    has_refusal_marker = any(m in lower_ans for m in refusal_markers)
    if has_refusal_marker:
        # If the answer already contains substantive factual answer + citations (e.g. Ayesha Malik... [Source 1]),
        # but the model tacked on the boilerplate refusal at the very end, strip the trailing refusal!
        lines = [line.strip() for line in cleaned_answer.splitlines() if line.strip()]
        valid_factual_lines = [
            l for l in lines
            if not any(m in l.lower() for m in refusal_markers)
        ]
        if valid_factual_lines and any("[source" in l.lower() for l in valid_factual_lines):
            cleaned_factual = " ".join(valid_factual_lines).strip()
            return cleaned_factual, False
        return settings.INSUFFICIENT_EVIDENCE_PHRASE, True

    return cleaned_answer, False
