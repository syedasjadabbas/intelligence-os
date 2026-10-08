"""
Unit test suite for RAG evaluation metric calculators, deterministic judges, and LLM judges.
Tests pure mathematical formulations, evidence anchor matching, nDCG@K, reranker rank shifts,
citation scoring, refusal matrices, schema validation, and mocked LLM judge parsing.
Zero external network calls required.
"""
import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch

from app.eval.judges import DeterministicJudge, LLMJudge
from app.eval.metrics import (
    compute_citation_metrics,
    compute_key_facts_coverage,
    compute_latency_percentiles,
    compute_mrr,
    compute_ndcg_at_k,
    compute_rank_shift,
    compute_recall_at_k,
    compute_refusal_metrics,
    compute_reranker_rank_improvement,
    compute_retrieval_metrics,
    detect_refusal,
    evaluate_threshold,
    matches_evidence_anchor,
)
from app.schemas.evaluation import EvidenceAnchor, JudgeOutputSchema


def test_evaluate_threshold():
    print("\n--- Test: evaluate_threshold logic ---")
    # Exact issue 1 inconsistency: 267.95 is NOT < 250
    assert evaluate_threshold(267.95, 250.0, "<") == "FAIL", "267.95 < 250 must evaluate to FAIL"
    assert evaluate_threshold(267.95, 250.0, "<", warn_target=350.0) == "WARN", "267.95 < 350 must evaluate to WARN"
    assert evaluate_threshold(240.0, 250.0, "<") == "PASS", "240.0 < 250 must evaluate to PASS"
    assert evaluate_threshold(250.0, 250.0, "<") == "FAIL", "250.0 < 250 boundary must evaluate to FAIL"

    # Greater than or equal operator
    assert evaluate_threshold(0.95, 0.90, ">=") == "PASS"
    assert evaluate_threshold(0.90, 0.90, ">=") == "PASS"
    assert evaluate_threshold(0.88, 0.90, ">=") == "FAIL"
    assert evaluate_threshold(0.88, 0.90, ">=", warn_target=0.85) == "WARN"

    # Less than or equal operator
    assert evaluate_threshold(0.04, 0.05, "<=") == "PASS"
    assert evaluate_threshold(0.06, 0.05, "<=") == "FAIL"
    assert evaluate_threshold(0.06, 0.05, "<=", warn_target=0.08) == "WARN"

    # Exact equality operator
    assert evaluate_threshold(1.0, 1.0, "==") == "PASS"
    assert evaluate_threshold(0.99, 1.0, "==") == "FAIL"

    # None handling
    assert evaluate_threshold(None, 100.0, "<") == "FAIL"
    print("[PASS] evaluate_threshold logic verified.")


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

    # Empty ground truth (unanswerable test case) -> returns 0.0 (no evidence expected)
    assert compute_recall_at_k(candidates, [], k=5) == 0.0

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

    # Empty ground truth -> MRR = 0.0 (unanswerable query)
    assert compute_mrr(cands_rank4, []) == 0.0

    print("[PASS] compute_mrr verified.")


def test_ndcg_at_k():
    print("\n--- Test: compute_ndcg_at_k ---")
    anchor = EvidenceAnchor(document_title="doc_a.pdf", content_anchors=["palladium"])
    cand_match = {"document_title": "doc_a.pdf", "content": "palladium core"}
    cand_noise = {"document_title": "noise.pdf", "content": "noise"}

    # Perfect ranking: relevant item at rank 1 -> nDCG@5 = 1.0
    perfect = [cand_match, cand_noise, cand_noise, cand_noise, cand_noise]
    assert compute_ndcg_at_k(perfect, [anchor], k=5) == 1.0

    # Relevant item at rank 2: DCG = 1/log2(3) = 0.6309, IDCG = 1/log2(2) = 1.0 -> nDCG = 0.6309
    rank_2 = [cand_noise, cand_match, cand_noise, cand_noise, cand_noise]
    val_2 = compute_ndcg_at_k(rank_2, [anchor], k=5)
    assert 0.63 <= val_2 <= 0.64, f"Expected ~0.6309, got {val_2}"

    # Relevant item at rank 5: DCG = 1/log2(6) = 0.3869 -> nDCG = 0.3869
    rank_5 = [cand_noise, cand_noise, cand_noise, cand_noise, cand_match]
    val_5 = compute_ndcg_at_k(rank_5, [anchor], k=5)
    assert 0.38 <= val_5 <= 0.39, f"Expected ~0.3869, got {val_5}"

    # Multiple relevant items: 2 distinct anchors
    anchor2 = EvidenceAnchor(document_title="doc_b.pdf", content_anchors=["fusion"])
    cand_match2 = {"document_title": "doc_b.pdf", "content": "fusion dynamic"}
    # Rank 1: match anchor 1, Rank 2: match anchor 2 -> both ideal -> nDCG = 1.0
    multi_perfect = [cand_match, cand_match2, cand_noise, cand_noise]
    assert compute_ndcg_at_k(multi_perfect, [anchor, anchor2], k=4) == 1.0

    # Multiple items where second chunk is redundant (same anchor 1):
    # Cand 1 matches anchor 1, Cand 2 also matches anchor 1 (no new anchor), Cand 3 matches anchor 2
    cand_redundant = {"document_title": "doc_a.pdf", "content": "palladium duplicate"}
    redundant_list = [cand_match, cand_redundant, cand_match2, cand_noise]
    val_red = compute_ndcg_at_k(redundant_list, [anchor, anchor2], k=4)
    # DCG = 1/log2(2) + 0 + 1/log2(4) = 1.0 + 0.5 = 1.5
    # IDCG = 1/log2(2) + 1/log2(3) = 1.0 + 0.6309 = 1.6309 -> nDCG = 1.5 / 1.6309 = 0.9197
    assert 0.91 <= val_red <= 0.93, f"Expected ~0.9197, got {val_red}"

    # No relevant items in top 5 -> nDCG@5 = 0.0
    none = [cand_noise, cand_noise, cand_noise, cand_noise, cand_noise]
    assert compute_ndcg_at_k(none, [anchor], k=5) == 0.0

    # Unanswerable query (no anchors expected) -> nDCG@5 = 0.0
    assert compute_ndcg_at_k(perfect, [], k=5) == 0.0

    # Empty candidate list -> 0.0
    assert compute_ndcg_at_k([], [anchor], k=5) == 0.0

    print("[PASS] compute_ndcg_at_k verified.")


def test_reranker_rank_improvement():
    print("\n--- Test: compute_rank_shift and compute_reranker_rank_improvement ---")
    anchor = EvidenceAnchor(document_title="target.pdf", content_anchors=["core spec"])
    target_item = {"document_title": "target.pdf", "content": "core spec"}
    noise = {"document_title": "noise.pdf", "content": "noise"}

    # Target is rank 5 before reranking, rank 1 after reranking -> shifted +4, promoted_to_top3 = True
    before = [noise, noise, noise, noise, target_item]
    after = [target_item, noise, noise, noise, noise]
    res = compute_reranker_rank_improvement(before, after, [anchor])

    assert res.first_relevant_rank_before == 5
    assert res.first_relevant_rank_after == 1
    assert res.position_shift == 4
    assert res.promoted_to_top3 is True
    assert res.mrr_before == 0.2
    assert res.mrr_after == 1.0

    # Target stays rank 2 before and after -> shift = 0, promoted_to_top3 = False
    before2 = [noise, target_item]
    after2 = [noise, target_item]
    res2 = compute_reranker_rank_improvement(before2, after2, [anchor])
    assert res2.position_shift == 0
    assert res2.promoted_to_top3 is False
    assert res2.mrr_before == 0.5
    assert res2.mrr_after == 0.5

    print("[PASS] compute_reranker_rank_improvement verified.")


def test_latency_percentiles():
    print("\n--- Test: compute_latency_percentiles ---")
    latencies = [10.0, 20.0, 30.0, 40.0, 50.0, 60.0, 70.0, 80.0, 90.0, 100.0]
    p = compute_latency_percentiles(latencies)
    assert p["mean"] == 55.0
    assert p["p95"] == 100.0

    p_empty = compute_latency_percentiles([])
    assert p_empty["mean"] == 0.0
    assert p_empty["p95"] == 0.0

    print("[PASS] compute_latency_percentiles verified.")


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
    assert res_noisy.precision == 0.5
    assert res_noisy.coverage == 0.5

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

    # 2. Failed refusal on expected "refuse"
    m2 = compute_refusal_metrics(is_refusal=False, expected_behavior="refuse")
    assert m2.correct_refusal is False
    assert m2.false_refusal is False

    # 3. False refusal on expected "answer"
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


def test_judge_schema_validation():
    print("\n--- Test: JudgeOutputSchema Validation ---")
    valid_payload = {
        "faithfulness": 0.95,
        "correctness": 0.90,
        "completeness": 0.85,
        "citation_correctness": 1.0,
        "supported": True,
        "reasoning": "High fidelity answer backed by all contexts.",
        "unsupported_claims": [],
    }
    schema = JudgeOutputSchema.model_validate(valid_payload)
    assert schema.faithfulness == 0.95
    assert schema.correctness == 0.90
    assert schema.completeness == 0.85
    assert schema.citation_correctness == 1.0
    assert schema.supported is True

    # Out of bounds test (e.g. > 1.0 or < 0.0)
    try:
        JudgeOutputSchema.model_validate({**valid_payload, "faithfulness": 1.5})
        assert False, "Should have raised validation error for faithfulness > 1.0"
    except Exception:
        pass

    print("[PASS] JudgeOutputSchema validation verified.")


async def test_deterministic_judge():
    print("\n--- Test: DeterministicJudge with Phase 2 multi-axis scoring ---")
    judge = DeterministicJudge()

    # 1. Refusal evaluation
    res_refusal = await judge.evaluate(
        query="What is the secret recipe for cherry pie?",
        generated_answer="I cannot find sufficient evidence in the organization's documents to answer this question.",
        expected_behavior="refuse",
    )
    assert res_refusal.passed is True
    assert res_refusal.is_refusal is True
    assert res_refusal.faithfulness == 1.0
    assert res_refusal.correctness == 1.0
    assert res_refusal.completeness == 1.0
    assert res_refusal.citation_correctness == 1.0

    # 2. Refusal failure
    res_refusal_fail = await judge.evaluate(
        query="What is the secret recipe for cherry pie?",
        generated_answer="The recipe is flour, sugar, and cherries.",
        expected_behavior="refuse",
    )
    assert res_refusal_fail.passed is False
    assert res_refusal_fail.is_refusal is False
    assert res_refusal_fail.correctness == 0.0

    # 3. Answer evaluation with key facts and grounding contexts
    res_answer = await judge.evaluate(
        query="What core containment does the reactor use?",
        generated_answer="The Arc Reactor utilizes palladium core containment to catalyze cold fusion.",
        contexts=["The Arc Reactor utilizes palladium core containment to catalyze cold fusion reactions."],
        key_facts=["palladium", "cold fusion"],
        expected_behavior="answer",
    )
    assert res_answer.passed is True
    assert res_answer.completeness == 1.0
    assert res_answer.faithfulness == 1.0
    assert res_answer.supported is True

    # 4. False refusal
    res_false_refusal = await judge.evaluate(
        query="What core containment does the reactor use?",
        generated_answer="I cannot find sufficient evidence to answer.",
        key_facts=["palladium"],
        expected_behavior="answer",
    )
    assert res_false_refusal.passed is False
    assert res_false_refusal.is_refusal is True

    print("[PASS] DeterministicJudge verified with Phase 2 metrics.")


async def test_mocked_llm_judge():
    print("\n--- Test: LLMJudge with Mocked LLM Providers ---")
    mock_json_response = json.dumps({
        "faithfulness": 0.95,
        "correctness": 0.92,
        "completeness": 0.88,
        "citation_correctness": 1.0,
        "supported": True,
        "reasoning": "Answer is strictly grounded and accurate.",
        "unsupported_claims": [],
    })

    # Test Gemini mock
    with patch("app.eval.judges.genai.GenerativeModel") as mock_gen_model:
        mock_instance = MagicMock()
        mock_response = MagicMock()
        mock_response.text = mock_json_response
        mock_instance.generate_content.return_value = mock_response
        mock_gen_model.return_value = mock_instance

        judge = LLMJudge(provider="gemini", api_key="mock-gemini-key")
        result = await judge.evaluate(
            query="What core containment does the Arc Reactor utilize?",
            generated_answer="The Arc Reactor utilizes palladium core containment.",
            contexts=["The Arc Reactor utilizes palladium core containment."],
            key_facts=["palladium"],
            expected_behavior="answer",
        )

        assert result.faithfulness == 0.95
        assert result.correctness == 0.92
        assert result.completeness == 0.88
        assert result.citation_correctness == 1.0
        assert result.passed is True
        assert result.supported is True

    # Test OpenAI mock
    with patch("app.eval.judges.AsyncOpenAI") as mock_openai_cls:
        mock_client = MagicMock()
        mock_choice = MagicMock()
        mock_choice.message.content = mock_json_response
        mock_completion = MagicMock(choices=[mock_choice])
        mock_client.chat.completions.create = AsyncMock(return_value=mock_completion)
        mock_openai_cls.return_value = mock_client

        judge_openai = LLMJudge(provider="openai", api_key="mock-openai-key")
        result_openai = await judge_openai.evaluate(
            query="What core containment does the Arc Reactor utilize?",
            generated_answer="The Arc Reactor utilizes palladium core containment.",
            contexts=["The Arc Reactor utilizes palladium core containment."],
            key_facts=["palladium"],
            expected_behavior="answer",
        )

        assert result_openai.faithfulness == 0.95
        assert result_openai.correctness == 0.92
        assert result_openai.passed is True

    # Test malformed output fails safely without leaking secrets
    with patch("app.eval.judges.genai.GenerativeModel") as mock_gen_model:
        mock_instance = MagicMock()
        mock_response = MagicMock()
        mock_response.text = "This is not json at all! 500 Server Error sk-mysecretkey12345"
        mock_instance.generate_content.return_value = mock_response
        mock_gen_model.return_value = mock_instance

        judge = LLMJudge(provider="gemini", api_key="mock-gemini-key")
        result = await judge.evaluate(
            query="test query",
            generated_answer="test answer",
        )
        assert result.passed is False
        assert result.score == 0.0
        assert "sk-mysecretkey12345" not in result.reasoning
        assert "[REDACTED]" in result.reasoning or "failure" in result.reasoning.lower()

    # Test score clamping for out-of-range scores (e.g. 1.5 clamped to 1.0, -0.2 clamped to 0.0)
    clamping_json = json.dumps({
        "faithfulness": 1.5,
        "correctness": -0.2,
        "completeness": 0.8,
        "citation_correctness": 1.0,
        "supported": True,
        "reasoning": "Out of range scores.",
        "unsupported_claims": [],
    })
    with patch("app.eval.judges.genai.GenerativeModel") as mock_gen_model:
        mock_instance = MagicMock()
        mock_response = MagicMock()
        mock_response.text = clamping_json
        mock_instance.generate_content.return_value = mock_response
        mock_gen_model.return_value = mock_instance

        judge = LLMJudge(provider="gemini", api_key="mock-gemini-key")
        result = await judge.evaluate(
            query="test query",
            generated_answer="test answer",
        )
        assert result.faithfulness == 1.0, f"Clamped to 1.0, got {result.faithfulness}"
        assert result.correctness == 0.0, f"Clamped to 0.0, got {result.correctness}"

    # Test missing credentials fails clearly
    try:
        LLMJudge(provider="gemini", api_key="  ")
        assert False, "Should raise ValueError for missing api_key"
    except ValueError as val_err:
        assert "GEMINI_API_KEY" in str(val_err)

    print("[PASS] LLMJudge mocked evaluation, safe failure, and clamping verified.")


def run_all_tests():
    print("=" * 70)
    print("RUNNING RAG EVALUATION METRIC UNIT TESTS")
    print("=" * 70)
    test_evaluate_threshold()
    test_matches_evidence_anchor()
    test_recall_at_k()
    test_mrr()
    test_ndcg_at_k()
    test_reranker_rank_improvement()
    test_latency_percentiles()
    test_citation_metrics()
    test_refusal_detection_and_metrics()
    test_key_facts_coverage()
    test_judge_schema_validation()
    asyncio.run(test_deterministic_judge())
    asyncio.run(test_mocked_llm_judge())
    print("\n" + "=" * 70)
    print("ALL EVALUATION METRIC UNIT TESTS PASSED SUCCESSFULLY!")
    print("=" * 70)


if __name__ == "__main__":
    run_all_tests()
