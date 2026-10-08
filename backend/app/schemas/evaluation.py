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
    query_type: str = "single_hop"  # single_hop, multi_hop, coreference_followup, unanswerable
    expected_behavior: str = "answer"  # answer, refuse
    ground_truth_answer: Optional[str] = None
    key_facts: List[str] = Field(default_factory=list)
    ground_truth_evidence: List[EvidenceAnchor] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class BenchmarkDataset(BaseModel):
    """Complete version-controlled benchmark dataset specification."""
    dataset_name: str
    description: Optional[str] = None
    version: str = "1.0.0"
    target_documents: List[str] = Field(default_factory=list)
    test_cases: List[BenchmarkTestCase] = Field(default_factory=list)


# --- Metrics Schemas ---

class RetrievalMetrics(BaseModel):
    """Retrieval quality metrics for a single query."""
    recall_at_3: float
    recall_at_5: float
    mrr: float
    relevant_found: int
    total_expected: int


class RerankerMetrics(BaseModel):
    """Reranker ranking shift metrics."""
    first_relevant_rank_before: Optional[int] = None
    first_relevant_rank_after: Optional[int] = None
    position_shift: int = 0
    promoted_to_top3: bool = False


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


class CaseEvaluationMetrics(BaseModel):
    """Aggregated evaluation metrics for a single benchmark test case."""
    recall_at_3: float
    recall_at_5: float
    mrr: float
    citation_precision: float
    citation_coverage: float
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
    recall_at_3: Optional[float] = None
    recall_at_5: Optional[float] = None
    mrr: Optional[float] = None
    citation_precision: Optional[float] = None
    citation_coverage: Optional[float] = None
    correct_refusal_rate: Optional[float] = None
    false_refusal_rate: Optional[float] = None
    latency_p95_ms: Optional[float] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


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
    citation_precision: Optional[float] = None
    citation_coverage: Optional[float] = None
    total_latency_ms: Optional[float] = None
    failure_reason: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
