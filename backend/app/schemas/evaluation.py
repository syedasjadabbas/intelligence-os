from datetime import datetime
from typing import Any, Dict, List, Optional
import uuid
from pydantic import BaseModel, ConfigDict, Field


class EvidenceAnchor(BaseModel):
    """
    Decoupled semantic ground-truth evidence anchor.
    Matches chunks dynamically by document title, page number, and key phrase substrings
    without any dependency on database chunk UUIDs.
    """
    document_title: str
    page_number: Optional[int] = None
    section_heading: Optional[str] = None
    content_anchors: List[str] = Field(
        default_factory=list,
        description="Key phrases or canonical substrings that must appear in the supporting chunk.",
    )


class BenchmarkTestCase(BaseModel):
    """Single benchmark evaluation test case."""
    id: str
    query: str
    conversation_history: List[Dict[str, str]] = Field(default_factory=list)
    query_type: str = "single_hop"  # single_hop, multi_hop, coreference_followup, retrieval_hard, multi_document, semantic_search, citation_sensitive, reranking_test, unanswerable
    expected_behavior: str = "answer"  # answer, refuse
    ground_truth_answer: Optional[str] = None
    key_facts: List[str] = Field(default_factory=list)
    ground_truth_evidence: List[EvidenceAnchor] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class BenchmarkDataset(BaseModel):
    """Complete version-controlled benchmark dataset specification."""
    dataset_name: str
    description: Optional[str] = None
    version: str = "2.0.0"
    target_documents: List[str] = Field(default_factory=list)
    test_cases: List[BenchmarkTestCase] = Field(default_factory=list)


# --- Phase 5B: Database-backed Dataset & Test Case Schemas ---

class TestCaseCreate(BaseModel):
    """Payload to create an evaluation test case in a dataset."""
    case_identifier: Optional[str] = Field(default=None, max_length=100, description="Optional custom identifier (e.g. TC-001). Auto-generated if omitted.")
    query: str = Field(min_length=1, description="Evaluation user query.")
    query_type: str = Field(default="single_hop", max_length=50, description="Category: single_hop, multi_hop, coreference_followup, retrieval_hard, multi_document, semantic_search, citation_sensitive, reranking_test, unanswerable.")
    expected_behavior: str = Field(default="answer", max_length=20, description="Expected system behavior: 'answer' or 'refuse'.")
    ground_truth_answer: Optional[str] = Field(default=None, description="Ideal ground-truth factual answer.")
    key_facts: List[str] = Field(default_factory=list, description="Key atomic facts required in answer.")
    ground_truth_evidence: List[EvidenceAnchor] = Field(default_factory=list, description="Semantic anchors for evidence matching.")
    conversation_history: List[Dict[str, str]] = Field(default_factory=list, description="Optional multi-turn conversation context.")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Arbitrary extra metadata tags.")


class TestCaseUpdate(BaseModel):
    """Payload to update an existing evaluation test case."""
    case_identifier: Optional[str] = Field(default=None, max_length=100)
    query: Optional[str] = Field(default=None, min_length=1)
    query_type: Optional[str] = Field(default=None, max_length=50)
    expected_behavior: Optional[str] = Field(default=None, max_length=20)
    ground_truth_answer: Optional[str] = None
    key_facts: Optional[List[str]] = None
    ground_truth_evidence: Optional[List[EvidenceAnchor]] = None
    conversation_history: Optional[List[Dict[str, str]]] = None
    metadata: Optional[Dict[str, Any]] = None


class TestCaseDetail(BaseModel):
    """Full detail of a persisted test case."""
    id: uuid.UUID
    dataset_id: uuid.UUID
    org_id: uuid.UUID
    case_identifier: str
    query: str
    query_type: str
    expected_behavior: str
    ground_truth_answer: Optional[str] = None
    key_facts: List[str] = Field(default_factory=list)
    ground_truth_evidence: List[EvidenceAnchor] = Field(default_factory=list)
    conversation_history: List[Dict[str, str]] = Field(default_factory=list)
    metadata_json: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class DatasetCreate(BaseModel):
    """Payload to create a new evaluation dataset."""
    name: str = Field(min_length=1, max_length=255, description="Unique name of dataset for tenant.")
    description: Optional[str] = Field(default=None, description="Optional description of the dataset.")
    version: str = Field(default="1.0.0", max_length=50, description="Dataset version.")
    test_cases: List[TestCaseCreate] = Field(default_factory=list, description="Optional initial test cases.")


class DatasetUpdate(BaseModel):
    """Payload to update dataset metadata."""
    name: Optional[str] = Field(default=None, min_length=1, max_length=255)
    description: Optional[str] = None
    version: Optional[str] = Field(default=None, max_length=50)


class DatasetListItem(BaseModel):
    """Compact summary of a dataset for list views."""
    id: uuid.UUID
    org_id: uuid.UUID
    name: str
    description: Optional[str] = None
    version: str
    test_case_count: int = 0
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class DatasetDetail(BaseModel):
    """Complete dataset details with all test cases."""
    id: uuid.UUID
    org_id: uuid.UUID
    name: str
    description: Optional[str] = None
    version: str
    test_case_count: int = 0
    test_cases: List[TestCaseDetail] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class DatasetsPage(BaseModel):
    """Paginated or listed datasets response."""
    items: List[DatasetListItem]
    total: int


# --- Metrics Schemas ---

class RetrievalMetrics(BaseModel):
    """Retrieval quality metrics for a single query."""
    recall_at_3: float
    recall_at_5: float
    mrr: float
    ndcg_at_5: float
    relevant_found: int
    total_expected: int


class RerankerMetrics(BaseModel):
    """Reranker ranking shift metrics."""
    first_relevant_rank_before: Optional[int] = None
    first_relevant_rank_after: Optional[int] = None
    position_shift: int = 0
    promoted_to_top3: bool = False
    mrr_before: Optional[float] = None
    mrr_after: Optional[float] = None


class CitationMetrics(BaseModel):
    """Grounding citation correctness and coverage."""
    precision: float
    coverage: float
    total_citations: int
    supported_citations: int


class RefusalMetrics(BaseModel):
    """Refusal guardrail evaluation."""
    is_refusal: bool
    correct_refusal: bool
    false_refusal: bool


class JudgeOutputSchema(BaseModel):
    """
    Structured, strongly typed output from LLM and deterministic judges.
    Covers Faithfulness, Correctness, Completeness, and Citation Correctness.
    """
    faithfulness: float = Field(ge=0.0, le=1.0, description="Score 0.0-1.0 measuring factual grounding in evidence.")
    correctness: float = Field(ge=0.0, le=1.0, description="Score 0.0-1.0 measuring factual equivalence with ground truth.")
    completeness: float = Field(ge=0.0, le=1.0, description="Score 0.0-1.0 measuring coverage of all required key points.")
    citation_correctness: float = Field(default=1.0, ge=0.0, le=1.0, description="Score 0.0-1.0 measuring validity of cited source tags.")
    supported: bool = Field(default=True, description="Whether claims are fully grounded without hallucination.")
    reasoning: str = Field(default="", description="Detailed qualitative explanation for scores.")
    unsupported_claims: List[str] = Field(default_factory=list, description="Claims made in answer not supported by context.")


class CaseEvaluationMetrics(BaseModel):
    """Aggregated evaluation metrics for a single benchmark test case."""
    recall_at_3: float
    recall_at_5: float
    mrr: float
    ndcg_at_5: float
    citation_precision: float
    citation_coverage: float
    faithfulness: Optional[float] = None
    correctness: Optional[float] = None
    completeness: Optional[float] = None
    total_latency_ms: float
    passed: bool
    failure_reason: Optional[str] = None


# --- Run Schemas ---

class EvalRunSummary(BaseModel):
    """Summary of an evaluation run with aggregate metrics."""
    id: uuid.UUID
    org_id: uuid.UUID
    dataset_name: str
    dataset_version: str
    status: str
    total_test_cases: int
    passed_test_cases: int
    pass_rate: Optional[float] = None
    recall_at_3: Optional[float] = None
    recall_at_5: Optional[float] = None
    mrr: Optional[float] = None
    ndcg_at_5: Optional[float] = None
    citation_precision: Optional[float] = None
    citation_coverage: Optional[float] = None
    correct_refusal_rate: Optional[float] = None
    false_refusal_rate: Optional[float] = None
    mean_faithfulness: Optional[float] = None
    mean_correctness: Optional[float] = None
    mean_completeness: Optional[float] = None
    mean_citation_correctness: Optional[float] = None
    mean_latency_ms: Optional[float] = None
    latency_p95_ms: Optional[float] = None
    judge_type: Optional[str] = None
    progress_current: int = 0
    progress_total: int = 0
    error_message: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class EvaluationRunListItem(BaseModel):
    """Compact summary schema for evaluation history lists and tables."""
    id: uuid.UUID
    org_id: uuid.UUID
    dataset_id: Optional[uuid.UUID] = None
    dataset_name: str
    dataset_version: str
    status: str
    judge_type: str = "deterministic"
    llm_provider: Optional[str] = None
    llm_model: Optional[str] = None
    total_test_cases: int
    passed_test_cases: int
    pass_rate: float = 0.0
    progress_current: int = 0
    progress_total: int = 0
    error_message: Optional[str] = None
    recall_at_3: Optional[float] = None
    recall_at_5: Optional[float] = None
    mrr: Optional[float] = None
    ndcg_at_5: Optional[float] = None
    citation_precision: Optional[float] = None
    citation_coverage: Optional[float] = None
    mean_faithfulness: Optional[float] = None
    mean_correctness: Optional[float] = None
    mean_completeness: Optional[float] = None
    mean_citation_correctness: Optional[float] = None
    mean_latency_ms: Optional[float] = None
    latency_p95_ms: Optional[float] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class EvaluationRunDetail(BaseModel):
    """Detailed evaluation run payload including configuration snapshot and summary metrics."""
    id: uuid.UUID
    org_id: uuid.UUID
    dataset_id: Optional[uuid.UUID] = None
    dataset_name: str
    dataset_version: str
    status: str
    judge_type: str = "deterministic"
    llm_provider: Optional[str] = None
    llm_model: Optional[str] = None
    embedding_model: Optional[str] = None
    reranker_model: Optional[str] = None
    total_test_cases: int
    passed_test_cases: int
    pass_rate: float = 0.0
    progress_current: int = 0
    progress_total: int = 0
    error_message: Optional[str] = None
    recall_at_3: Optional[float] = None
    recall_at_5: Optional[float] = None
    mrr: Optional[float] = None
    ndcg_at_5: Optional[float] = None
    citation_precision: Optional[float] = None
    citation_coverage: Optional[float] = None
    correct_refusal_rate: Optional[float] = None
    false_refusal_rate: Optional[float] = None
    mean_faithfulness: Optional[float] = None
    mean_correctness: Optional[float] = None
    mean_completeness: Optional[float] = None
    mean_citation_correctness: Optional[float] = None
    mean_latency_ms: Optional[float] = None
    latency_p95_ms: Optional[float] = None
    config_snapshot: Dict[str, Any] = Field(default_factory=dict)
    summary_metrics: Dict[str, Any] = Field(default_factory=dict)
    regression_summary: Dict[str, Any] = Field(default_factory=dict)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class EvaluationRunsPage(BaseModel):
    """Paginated evaluation run list response."""
    items: List[EvaluationRunListItem]
    total: int
    skip: int
    limit: int


class EvaluationRunCreate(BaseModel):
    """Request payload to start an evaluation run."""
    dataset_id: Optional[uuid.UUID] = Field(default=None, description="Optional ID of custom database dataset.")
    dataset_name: str = Field(default="golden_dataset", description="Name of benchmark dataset to evaluate.")
    judge_type: str = Field(default="deterministic", description="'deterministic' or 'llm'")
    limit: Optional[int] = Field(default=50, ge=1, le=50, description="Maximum test cases to evaluate (hard server cap: 50).")
    offline: bool = Field(default=True, description="Whether to run in deterministic offline mode.")


class EvalRunResultItem(BaseModel):
    """Itemized test case result."""
    id: uuid.UUID
    run_id: uuid.UUID
    test_case_id: str
    query: str
    query_type: str
    expected_behavior: str
    generated_answer: str
    passed: bool
    is_refusal: bool
    recall_at_3: Optional[float] = None
    recall_at_5: Optional[float] = None
    mrr: Optional[float] = None
    ndcg_at_5: Optional[float] = None
    citation_precision: Optional[float] = None
    citation_coverage: Optional[float] = None
    faithfulness: Optional[float] = None
    correctness: Optional[float] = None
    completeness: Optional[float] = None
    citation_correctness: Optional[float] = None
    total_latency_ms: Optional[float] = None
    failure_reason: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class EvaluationResultListItem(BaseModel):
    """Compact test case result item for paginated tables without heavy candidate arrays."""
    id: uuid.UUID
    run_id: uuid.UUID
    test_case_id: str
    query: str
    query_type: str
    expected_behavior: str
    generated_answer: str
    passed: bool
    is_refusal: bool
    recall_at_3: Optional[float] = None
    recall_at_5: Optional[float] = None
    mrr: Optional[float] = None
    ndcg_at_5: Optional[float] = None
    citation_precision: Optional[float] = None
    citation_coverage: Optional[float] = None
    faithfulness: Optional[float] = None
    correctness: Optional[float] = None
    completeness: Optional[float] = None
    citation_correctness: Optional[float] = None
    total_latency_ms: Optional[float] = None
    failure_reason: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class EvaluationResultDetail(BaseModel):
    """Complete test case detail inspection schema with retrieved chunks, reranked chunks, citations, and judge reasoning."""
    id: uuid.UUID
    run_id: uuid.UUID
    org_id: uuid.UUID
    test_case_id: str
    query: str
    query_type: str
    expected_behavior: str
    generated_answer: str
    passed: bool
    is_refusal: bool
    recall_at_3: Optional[float] = None
    recall_at_5: Optional[float] = None
    mrr: Optional[float] = None
    ndcg_at_5: Optional[float] = None
    citation_precision: Optional[float] = None
    citation_coverage: Optional[float] = None
    faithfulness: Optional[float] = None
    correctness: Optional[float] = None
    completeness: Optional[float] = None
    citation_correctness: Optional[float] = None
    total_latency_ms: Optional[float] = None
    retrieved_candidates: List[Dict[str, Any]] = Field(default_factory=list)
    reranked_candidates: List[Dict[str, Any]] = Field(default_factory=list)
    citations: List[Dict[str, Any]] = Field(default_factory=list)
    trace_data: Dict[str, Any] = Field(default_factory=dict)
    judge_output: Dict[str, Any] = Field(default_factory=dict)
    failure_reason: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class EvaluationResultsPage(BaseModel):
    """Paginated evaluation results list response."""
    items: List[EvaluationResultListItem]
    total: int
    skip: int
    limit: int


# --- Run Comparison Schemas ---

class MetricDelta(BaseModel):
    """Delta comparison for a single metric between base and target runs."""
    base_value: Optional[float] = None
    target_value: Optional[float] = None
    delta: Optional[float] = None
    percent_change: Optional[float] = None
    status: str = "neutral"  # improved, regressed, neutral


class EvaluationComparisonDeltas(BaseModel):
    """Metrics deltas comparison between two evaluation runs."""
    pass_rate: MetricDelta
    recall_at_3: MetricDelta
    recall_at_5: MetricDelta
    mrr: MetricDelta
    ndcg_at_5: MetricDelta
    citation_precision: MetricDelta
    citation_coverage: MetricDelta
    mean_faithfulness: MetricDelta
    mean_correctness: MetricDelta
    mean_completeness: MetricDelta
    mean_citation_correctness: MetricDelta
    mean_latency_ms: MetricDelta


class EvaluationComparisonResponse(BaseModel):
    """Full comparison response between two evaluation runs."""
    base_run: EvaluationRunListItem
    target_run: EvaluationRunListItem
    deltas: EvaluationComparisonDeltas
    regressed_cases_count: int = 0
    improved_cases_count: int = 0
