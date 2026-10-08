"""
Mathematical and rule-based evaluation metrics for RAG pipeline.
Covers retrieval quality, reranker impact, citation validity, and refusal guardrails.
All functions in this module are purely deterministic with zero external dependencies.
"""
import re
from typing import Any, Dict, List, Optional, Union
from app.schemas.evaluation import (
    CitationMetrics,
    EvidenceAnchor,
    RefusalMetrics,
    RerankerMetrics,
    RetrievalMetrics,
)

REFUSAL_PHRASES = [
    "cannot find sufficient evidence",
    "do not have sufficient information",
    "insufficient evidence",
    "i am unable to answer",
    "not mentioned in the provided",
    "does not contain information",
    "cannot answer this question based on",
    "no evidence found",
    "no information provided",
    "not provided in the context",
]


def _normalize_text(text: Optional[str]) -> str:
    if not text:
        return ""
    # Strip markdown header hashes and symbols
    cleaned = re.sub(r"^[#\s\-*]+", "", text.strip())
    # Normalize underscores and hyphens to spaces for flexible document title matching
    cleaned = cleaned.replace("_", " ")
    return re.sub(r"\s+", " ", cleaned.lower().strip())


def matches_evidence_anchor(
    candidate: Union[Dict[str, Any], Any],
    anchor: EvidenceAnchor,
) -> bool:
    """
    Decoupled semantic check determining if a retrieved candidate chunk
    or citation satisfies a ground-truth evidence anchor.

    Matches by:
    1. Document title (case-insensitive substring or equality, ignoring .pdf extension differences)
    2. Optional page number (if specified in both anchor and candidate)
    3. Content anchors (all key phrases must be present in chunk content, case-insensitive)
    """
    if isinstance(candidate, dict):
        cand_title = candidate.get("document_title") or candidate.get("title") or ""
        cand_page = candidate.get("page_number")
        cand_content = candidate.get("content") or ""
        cand_heading = candidate.get("section_heading")
    else:
        cand_title = getattr(candidate, "document_title", "") or getattr(candidate, "title", "")
        cand_page = getattr(candidate, "page_number", None)
        cand_content = getattr(candidate, "content", "")
        cand_heading = getattr(candidate, "section_heading", None)

    norm_cand_title = _normalize_text(cand_title).replace(".pdf", "")
    norm_anchor_title = _normalize_text(anchor.document_title).replace(".pdf", "")

    # Title check: must match (either contains or equals)
    if not norm_cand_title or not norm_anchor_title:
        return False
    if norm_anchor_title not in norm_cand_title and norm_cand_title not in norm_anchor_title:
        return False

    # Page number check (if anchor specifies page_number, candidate page should match if available)
    if anchor.page_number is not None and cand_page is not None:
        if int(anchor.page_number) != int(cand_page):
            return False

    # Section heading check (if specified)
    if anchor.section_heading and cand_heading:
        norm_anchor_heading = _normalize_text(anchor.section_heading)
        norm_cand_heading = _normalize_text(cand_heading)
        if norm_anchor_heading not in norm_cand_heading:
            # If section heading is given but not in chunk heading, check if it's in content
            if norm_anchor_heading not in _normalize_text(cand_content):
                return False

    # Content anchors check: all anchor phrases must exist in the candidate text
    if anchor.content_anchors:
        norm_content = _normalize_text(cand_content)
        for ca in anchor.content_anchors:
            norm_ca = _normalize_text(ca)
            if norm_ca not in norm_content:
                return False

    return True


def compute_recall_at_k(
    retrieved_candidates: List[Union[Dict[str, Any], Any]],
    ground_truth_anchors: List[EvidenceAnchor],
    k: int,
) -> float:
    """
    Computes Recall@K: proportion of ground-truth evidence anchors retrieved within the top K results.
    If ground_truth_anchors is empty (e.g., unanswerable test cases), returns 1.0.
    """
    if not ground_truth_anchors:
        return 1.0
    if not retrieved_candidates or k <= 0:
        return 0.0

    top_k = retrieved_candidates[:k]
    matched_anchors_count = 0

    for anchor in ground_truth_anchors:
        found = any(matches_evidence_anchor(cand, anchor) for cand in top_k)
        if found:
            matched_anchors_count += 1

    return round(matched_anchors_count / len(ground_truth_anchors), 4)


def compute_mrr(
    retrieved_candidates: List[Union[Dict[str, Any], Any]],
    ground_truth_anchors: List[EvidenceAnchor],
) -> float:
    """
    Computes Mean Reciprocal Rank (MRR) for the first relevant evidence chunk.
    If ground_truth_anchors is empty, returns 1.0.
    If no relevant candidate is found, returns 0.0.
    """
    if not ground_truth_anchors:
        return 1.0
    if not retrieved_candidates:
        return 0.0

    for rank, cand in enumerate(retrieved_candidates, start=1):
        for anchor in ground_truth_anchors:
            if matches_evidence_anchor(cand, anchor):
                return round(1.0 / rank, 4)

    return 0.0


def compute_retrieval_metrics(
    retrieved_candidates: List[Union[Dict[str, Any], Any]],
    ground_truth_anchors: List[EvidenceAnchor],
) -> RetrievalMetrics:
    """Computes Recall@3, Recall@5, and MRR for a retrieved candidate list."""
    recall_3 = compute_recall_at_k(retrieved_candidates, ground_truth_anchors, k=3)
    recall_5 = compute_recall_at_k(retrieved_candidates, ground_truth_anchors, k=5)
    mrr = compute_mrr(retrieved_candidates, ground_truth_anchors)

    relevant_found = 0
    for anchor in ground_truth_anchors:
        if any(matches_evidence_anchor(cand, anchor) for cand in retrieved_candidates):
            relevant_found += 1

    return RetrievalMetrics(
        recall_at_3=recall_3,
        recall_at_5=recall_5,
        mrr=mrr,
        relevant_found=relevant_found,
        total_expected=len(ground_truth_anchors),
    )


def compute_rank_shift(
    before_rerank: List[Union[Dict[str, Any], Any]],
    after_rerank: List[Union[Dict[str, Any], Any]],
    ground_truth_anchors: List[EvidenceAnchor],
) -> RerankerMetrics:
    """
    Measures the ranking shift of the first relevant chunk before and after reranking.
    """
    if not ground_truth_anchors:
        return RerankerMetrics()

    rank_before: Optional[int] = None
    for r, cand in enumerate(before_rerank, start=1):
        if any(matches_evidence_anchor(cand, anchor) for anchor in ground_truth_anchors):
            rank_before = r
            break

    rank_after: Optional[int] = None
    for r, cand in enumerate(after_rerank, start=1):
        if any(matches_evidence_anchor(cand, anchor) for anchor in ground_truth_anchors):
            rank_after = r
            break

    shift = 0
    if rank_before is not None and rank_after is not None:
        # Positive shift means moved higher up (e.g. from rank 5 to rank 1 -> +4)
        shift = rank_before - rank_after

    promoted_to_top3 = False
    if rank_after is not None and rank_after <= 3:
        if rank_before is None or rank_before > 3:
            promoted_to_top3 = True

    return RerankerMetrics(
        first_relevant_rank_before=rank_before,
        first_relevant_rank_after=rank_after,
        position_shift=shift,
        promoted_to_top3=promoted_to_top3,
    )


def compute_citation_metrics(
    citations: List[Union[Dict[str, Any], Any]],
    ground_truth_anchors: List[EvidenceAnchor],
) -> CitationMetrics:
    """
    Computes Citation Precision and Coverage against ground-truth evidence anchors.
    Precision: fraction of cited items that correspond to valid ground-truth evidence.
    Coverage: fraction of ground-truth evidence anchors that were cited.
    """
    total_citations = len(citations)

    if not ground_truth_anchors:
        if total_citations == 0:
            return CitationMetrics(
                precision=1.0,
                coverage=1.0,
                total_citations=0,
                supported_citations=0,
            )
        else:
            return CitationMetrics(
                precision=0.0,
                coverage=1.0,
                total_citations=total_citations,
                supported_citations=0,
            )

    if total_citations == 0:
        return CitationMetrics(
            precision=0.0,
            coverage=0.0,
            total_citations=0,
            supported_citations=0,
        )

    # Check which citations match at least one ground-truth anchor
    supported_count = 0
    for cit in citations:
        if any(matches_evidence_anchor(cit, anchor) for anchor in ground_truth_anchors):
            supported_count += 1

    # Check which ground-truth anchors are covered by at least one citation
    covered_anchors = 0
    for anchor in ground_truth_anchors:
        if any(matches_evidence_anchor(cit, anchor) for cit in citations):
            covered_anchors += 1

    precision = round(supported_count / total_citations, 4)
    coverage = round(covered_anchors / len(ground_truth_anchors), 4)

    return CitationMetrics(
        precision=precision,
        coverage=coverage,
        total_citations=total_citations,
        supported_citations=supported_count,
    )


def detect_refusal(text: Optional[str]) -> bool:
    """
    Detects whether generated answer represents a refusal to answer due to insufficient evidence.
    """
    if not text:
        return False
    clean = _normalize_text(text)
    for phrase in REFUSAL_PHRASES:
        if phrase in clean:
            return True
    return False


def compute_refusal_metrics(
    is_refusal: bool,
    expected_behavior: str,
) -> RefusalMetrics:
    """
    Computes refusal correctness metrics for a test case.
    expected_behavior must be 'refuse' or 'answer'.
    """
    exp = (expected_behavior or "answer").lower().strip()
    if exp == "refuse":
        correct_refusal = is_refusal
        false_refusal = False
    else:
        correct_refusal = False
        false_refusal = is_refusal

    return RefusalMetrics(
        is_refusal=is_refusal,
        correct_refusal=correct_refusal,
        false_refusal=false_refusal,
    )


def compute_key_facts_coverage(text: Optional[str], key_facts: List[str]) -> float:
    """
    Computes the fraction of key facts present in the answer text (case-insensitive).
    """
    if not key_facts:
        return 1.0
    if not text:
        return 0.0

    clean_text = _normalize_text(text)
    found = 0
    for fact in key_facts:
        norm_fact = _normalize_text(fact)
        if norm_fact in clean_text:
            found += 1
        else:
            # Word-level fallback: at least 75% of salient words present
            words = [w for w in norm_fact.split() if len(w) > 2]
            if words:
                word_matches = sum(1 for w in words if w in clean_text)
                if word_matches / len(words) >= 0.75:
                    found += 1

    return round(found / len(key_facts), 4)
