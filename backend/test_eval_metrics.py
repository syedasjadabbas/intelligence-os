"""
Unit test suite for RAG evaluation metric calculators and deterministic judges.
Tests pure mathematical formulations, evidence anchor matching, citation scoring,
refusal matrices, and deterministic judging with zero external dependencies.
"""
import asyncio
import sys

from app.eval.judges import DeterministicJudge
from app.eval.metrics import (
    compute_citation_metrics,
    compute_key_facts_coverage,
    compute_mrr,
    compute_rank_shift,
    compute_recall_at_k,
    compute_refusal_metrics,
    compute_retrieval_metrics,
    detect_refusal,
    matches_evidence_anchor,
)
from app.schemas.evaluation import EvidenceAnchor


def test_matches_evidence_anchor():
    print("\n--- Test: matches_evidence_anchor ---")
    anchor = EvidenceAnchor(
        document_title="arc_reactor_tech.pdf",
        page_number=1,
        section_heading="# ARC REACTOR FUSION SPECIFICATION",
        content_anchors=["palladium core containment", "cold fusion"],
    )

    # 1. Exact match
    cand1 = {
        "document_title": "arc_reactor_tech.pdf",
        "page_number": 1,
        "section_heading": "# ARC REACTOR FUSION SPECIFICATION",
        "content": "The Arc Reactor utilizes palladium core containment to catalyze cold fusion reactions.",
    }
    assert matches_evidence_anchor(cand1, anchor) is True, "Exact candidate should match anchor"

    # 2. Case-insensitive title and content match without .pdf in candidate title
    cand2 = {
        "document_title": "Arc_Reactor_Tech",
        "page_number": 1,
        "section_heading": "Arc Reactor Fusion Specification",
        "content": "Contains Palladium Core Containment for Cold Fusion experiments.",
    }
    assert matches_evidence_anchor(cand2, anchor) is True, "Case-insensitive title without .pdf should match"

    # 3. Wrong page number
    cand_wrong_page = {
        "document_title": "arc_reactor_tech.pdf",
        "page_number": 2,
        "content": "The Arc Reactor utilizes palladium core containment to catalyze cold fusion reactions.",
    }
    assert matches_evidence_anchor(cand_wrong_page, anchor) is False, "Mismatched page must fail"

    # 4. Missing one of the required content anchors
    cand_missing_phrase = {
        "document_title": "arc_reactor_tech.pdf",
        "page_number": 1,
        "content": "The Arc Reactor utilizes palladium core containment for high energy generation.",
    }
    assert matches_evidence_anchor(cand_missing_phrase, anchor) is False, "Missing content anchor must fail"

    # 5. Wrong document title
    cand_wrong_doc = {
        "document_title": "iron_legion_avionics.pdf",
        "page_number": 1,
        "content": "The Arc Reactor utilizes palladium core containment to catalyze cold fusion reactions.",
    }
    assert matches_evidence_anchor(cand_wrong_doc, anchor) is False, "Wrong document title must fail"

    print("[PASS] matches_evidence_anchor verified across all variations.")


def test_recall_at_k():
    print("\n--- Test: compute_recall_at_k ---")
    anchor1 = EvidenceAnchor(document_title="doc_a.pdf", content_anchors=["fusion reaction"])
    anchor2 = EvidenceAnchor(document_title="doc_b.pdf", content_anchors=["nitrogen cooling"])

    candidates = [
        {"document_title": "other.pdf", "content": "random noise"},
        {"document_title": "doc_a.pdf", "content": "this has fusion reaction"},
        {"document_title": "other2.pdf", "content": "more noise"},
        {"document_title": "other3.pdf", "content": "noise"},
        {"document_title": "doc_b.pdf", "content": "liquid nitrogen cooling circuits"},
    ]

    # At k=1: neither anchor found (candidates[0] is other.pdf)
    assert compute_recall_at_k(candidates, [anchor1, anchor2], k=1) == 0.0

    # At k=3: anchor1 is at rank 2 (index 1), anchor2 is at rank 5 -> 1 of 2 found = 0.5
    assert compute_recall_at_k(candidates, [anchor1, anchor2], k=3) == 0.5

    # At k=5: both anchor1 and anchor2 found in top 5 -> 2 of 2 found = 1.0
    assert compute_recall_at_k(candidates, [anchor1, anchor2], k=5) == 1.0

    # Empty ground truth (e.g. unanswerable test case) -> should return 1.0
    assert compute_recall_at_k(candidates, [], k=5) == 1.0

    # Empty candidate list with non-empty anchors -> 0.0
    assert compute_recall_at_k([], [anchor1], k=5) == 0.0

    print("[PASS] compute_recall_at_k verified.")


def test_mrr():
    print("\n--- Test: compute_mrr ---")
    anchor = EvidenceAnchor(document_title="target.pdf", content_anchors=["quantum flux"])

    # Match at rank 1 -> MRR = 1.0
    cands_rank1 = [{"document_title": "target.pdf", "content": "quantum flux"}]
    assert compute_mrr(cands_rank1, [anchor]) == 1.0

    # Match at rank 2 -> MRR = 0.5
    cands_rank2 = [
        {"document_title": "other.pdf", "content": "none"},
        {"document_title": "target.pdf", "content": "quantum flux"},
    ]
    assert compute_mrr(cands_rank2, [anchor]) == 0.5

    # Match at rank 4 -> MRR = 0.25
    cands_rank4 = [
        {"document_title": "c1.pdf", "content": "x"},
        {"document_title": "c2.pdf", "content": "y"},
        {"document_title": "c3.pdf", "content": "z"},
        {"document_title": "target.pdf", "content": "quantum flux"},
    ]
    assert compute_mrr(cands_rank4, [anchor]) == 0.25

    # No match in candidates -> MRR = 0.0
    cands_none = [{"document_title": "c1.pdf", "content": "x"}]
    assert compute_mrr(cands_none, [anchor]) == 0.0

    # Empty ground truth -> MRR = 1.0
    assert compute_mrr(cands_rank4, []) == 1.0

    print("[PASS] compute_mrr verified.")


def test_rank_shift():
    print("\n--- Test: compute_rank_shift ---")
    anchor = EvidenceAnchor(document_title="target.pdf", content_anchors=["core spec"])
    target_item = {"document_title": "target.pdf", "content": "core spec"}
    noise = {"document_title": "noise.pdf", "content": "noise"}

    # Target is rank 5 before reranking, rank 1 after reranking -> shifted +4, promoted_to_top3 = True
    before = [noise, noise, noise, noise, target_item]
    after = [target_item, noise, noise, noise, noise]
    res = compute_rank_shift(before, after, [anchor])

    assert res.first_relevant_rank_before == 5
    assert res.first_relevant_rank_after == 1
    assert res.position_shift == 4
    assert res.promoted_to_top3 is True

    # Target stays rank 2 before and after -> shift = 0, promoted_to_top3 = False
    before2 = [noise, target_item]
    after2 = [noise, target_item]
    res2 = compute_rank_shift(before2, after2, [anchor])
    assert res2.position_shift == 0
    assert res2.promoted_to_top3 is False

    print("[PASS] compute_rank_shift verified.")


def test_citation_metrics():
    print("\n--- Test: compute_citation_metrics ---")
    anchor1 = EvidenceAnchor(document_title="doc1.pdf", content_anchors=["anchor one"])
    anchor2 = EvidenceAnchor(document_title="doc2.pdf", content_anchors=["anchor two"])

    cits = [
        {"document_title": "doc1.pdf", "content": "has anchor one"},
        {"document_title": "doc2.pdf", "content": "has anchor two"},
    ]
    res = compute_citation_metrics(cits, [anchor1, anchor2])
    assert res.precision == 1.0
    assert res.coverage == 1.0
    assert res.supported_citations == 2
    assert res.total_citations == 2

    # 1 supported citation out of 2 total; 1 of 2 anchors covered
    cits_noisy = [
        {"document_title": "doc1.pdf", "content": "has anchor one"},
        {"document_title": "doc3_bogus.pdf", "content": "irrelevant hallucinated source"},
    ]
    res_noisy = compute_citation_metrics(cits_noisy, [anchor1, anchor2])
    assert res_noisy.precision == 0.5  # 1 supported out of 2
    assert res_noisy.coverage == 0.5   # 1 covered out of 2

    # Empty citations with non-empty anchors -> 0.0
    res_empty = compute_citation_metrics([], [anchor1])
    assert res_empty.precision == 0.0
    assert res_empty.coverage == 0.0

    # Empty citations with empty anchors (unanswerable) -> 1.0
    res_unans = compute_citation_metrics([], [])
    assert res_unans.precision == 1.0
    assert res_unans.coverage == 1.0

    print("[PASS] compute_citation_metrics verified.")


def test_refusal_detection_and_metrics():
    print("\n--- Test: detect_refusal and compute_refusal_metrics ---")
    refusal_msg = "I cannot find sufficient evidence in the organization's documents to answer this question."
    normal_answer = "The Arc Reactor utilizes palladium core containment to catalyze cold fusion reactions."

    assert detect_refusal(refusal_msg) is True
    assert detect_refusal(normal_answer) is False

    # 1. Correct refusal on expected "refuse"
    m1 = compute_refusal_metrics(is_refusal=True, expected_behavior="refuse")
    assert m1.correct_refusal is True
    assert m1.false_refusal is False

    # 2. Failed refusal on expected "refuse" (model gave answer instead of refusing)
    m2 = compute_refusal_metrics(is_refusal=False, expected_behavior="refuse")
    assert m2.correct_refusal is False
    assert m2.false_refusal is False

    # 3. False refusal on expected "answer" (model refused when it should answer)
    m3 = compute_refusal_metrics(is_refusal=True, expected_behavior="answer")
    assert m3.correct_refusal is False
    assert m3.false_refusal is True

    # 4. Correct answer on expected "answer"
    m4 = compute_refusal_metrics(is_refusal=False, expected_behavior="answer")
    assert m4.correct_refusal is False
    assert m4.false_refusal is False

    print("[PASS] refusal detection and metrics verified.")


def test_key_facts_coverage():
    print("\n--- Test: compute_key_facts_coverage ---")
    text = "The Arc Reactor utilizes palladium core containment to catalyze cold fusion reactions."
    facts = ["palladium", "cold fusion", "irrelevant fact not present"]
    cov = compute_key_facts_coverage(text, facts)
    assert cov == 0.6667, f"Expected 0.6667, got {cov}"

    assert compute_key_facts_coverage(text, ["palladium", "cold fusion"]) == 1.0
    assert compute_key_facts_coverage(text, []) == 1.0
    print("[PASS] compute_key_facts_coverage verified.")


async def test_deterministic_judge():
    print("\n--- Test: DeterministicJudge ---")
    judge = DeterministicJudge()

    # 1. Refusal evaluation
    res_refusal = await judge.evaluate(
        query="What is the secret recipe for cherry pie?",
        generated_answer="I cannot find sufficient evidence in the organization's documents to answer this question.",
        expected_behavior="refuse",
    )
    assert res_refusal.passed is True
    assert res_refusal.is_refusal is True
    assert res_refusal.score == 1.0

    # 2. Refusal failure (generated answer instead of refuse)
    res_refusal_fail = await judge.evaluate(
        query="What is the secret recipe for cherry pie?",
        generated_answer="The recipe is flour, sugar, and cherries.",
        expected_behavior="refuse",
    )
    assert res_refusal_fail.passed is False
    assert res_refusal_fail.is_refusal is False

    # 3. Answer evaluation with key facts
    res_answer = await judge.evaluate(
        query="What core containment does the reactor use?",
        generated_answer="The Arc Reactor utilizes palladium core containment to catalyze cold fusion.",
        key_facts=["palladium", "cold fusion"],
        expected_behavior="answer",
    )
    assert res_answer.passed is True
    assert res_answer.key_facts_coverage == 1.0
    assert res_answer.score == 1.0

    # 4. False refusal (refused when an answer was expected)
    res_false_refusal = await judge.evaluate(
        query="What core containment does the reactor use?",
        generated_answer="I cannot find sufficient evidence to answer.",
        key_facts=["palladium"],
        expected_behavior="answer",
    )
    assert res_false_refusal.passed is False
    assert res_false_refusal.is_refusal is True

    print("[PASS] DeterministicJudge verified.")


def run_all_tests():
    print("=" * 70)
    print("RUNNING RAG EVALUATION METRIC UNIT TESTS")
    print("=" * 70)
    test_matches_evidence_anchor()
    test_recall_at_k()
    test_mrr()
    test_rank_shift()
    test_citation_metrics()
    test_refusal_detection_and_metrics()
    test_key_facts_coverage()
    asyncio.run(test_deterministic_judge())
    print("\n" + "=" * 70)
    print("ALL EVALUATION METRIC UNIT TESTS PASSED SUCCESSFULLY!")
    print("=" * 70)


if __name__ == "__main__":
    run_all_tests()
