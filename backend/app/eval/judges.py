"""
Evaluation judge abstractions for Intelligence OS RAG pipeline.
Defines BaseJudge interface, DeterministicJudge implementation for zero-cost offline CI/CD,
and LLMJudge for structured multi-axis evaluation (faithfulness, correctness, completeness, citation correctness).
"""
import asyncio
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
import json
import logging
import re
from typing import Any, Dict, List, Optional
import google.generativeai as genai
from openai import AsyncOpenAI

from app.core.config import settings
from app.eval.metrics import (
    compute_citation_metrics,
    compute_key_facts_coverage,
    detect_refusal,
)
from app.schemas.evaluation import EvidenceAnchor, JudgeOutputSchema

logger = logging.getLogger(__name__)


@dataclass
class JudgeResult:
    """Standardized output from an evaluation judge."""
    passed: bool
    score: float
    is_refusal: bool
    key_facts_coverage: float
    reasoning: str
    faithfulness: float = 1.0
    correctness: float = 1.0
    completeness: float = 1.0
    citation_correctness: float = 1.0
    supported: bool = True
    unsupported_claims: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "passed": self.passed,
            "score": round(self.score, 4),
            "is_refusal": self.is_refusal,
            "key_facts_coverage": round(self.key_facts_coverage, 4),
            "faithfulness": round(self.faithfulness, 4),
            "correctness": round(self.correctness, 4),
            "completeness": round(self.completeness, 4),
            "citation_correctness": round(self.citation_correctness, 4),
            "supported": self.supported,
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
        citations: Optional[List[Any]] = None,
        expected_evidence: Optional[List[EvidenceAnchor]] = None,
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
    - Deterministic citation verification
    """

    async def evaluate(
        self,
        query: str,
        generated_answer: str,
        ground_truth_answer: Optional[str] = None,
        contexts: Optional[List[str]] = None,
        key_facts: Optional[List[str]] = None,
        expected_behavior: str = "answer",
        citations: Optional[List[Any]] = None,
        expected_evidence: Optional[List[EvidenceAnchor]] = None,
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
                    faithfulness=1.0,
                    correctness=1.0,
                    completeness=1.0,
                    citation_correctness=1.0,
                    supported=True,
                    is_refusal=True,
                    key_facts_coverage=1.0,
                    reasoning="Correct refusal: pipeline accurately declined to answer ungrounded query.",
                )
            else:
                return JudgeResult(
                    passed=False,
                    score=0.0,
                    faithfulness=0.0,
                    correctness=0.0,
                    completeness=0.0,
                    citation_correctness=0.0,
                    supported=False,
                    is_refusal=False,
                    key_facts_coverage=0.0,
                    reasoning="Failed refusal check: query expected refusal but model generated an answer.",
                    unsupported_claims=[generated_answer[:200]],
                )

        # 2. Evaluate False Refusal Scenarios
        if is_refusal:
            return JudgeResult(
                passed=False,
                score=0.0,
                faithfulness=0.0,
                correctness=0.0,
                completeness=0.0,
                citation_correctness=0.0,
                supported=False,
                is_refusal=True,
                key_facts_coverage=0.0,
                reasoning="False refusal: query expected an answer but pipeline refused despite valid context.",
            )

        # 3. Completeness (Key facts coverage)
        if facts:
            completeness = compute_key_facts_coverage(generated_answer, facts)
        else:
            completeness = 1.0

        # 4. Correctness (Overlap with ground_truth_answer if provided, else fallback to completeness)
        if ground_truth_answer:
            gt_words = [w.lower() for w in re.findall(r"\w+", ground_truth_answer) if len(w) > 2]
            if gt_words:
                ans_lower = generated_answer.lower()
                matched = sum(1 for w in gt_words if w in ans_lower)
                correctness = round(matched / len(gt_words), 4)
            else:
                correctness = completeness
        else:
            correctness = completeness

        # 5. Faithfulness (Grounding in contexts)
        faithfulness = 1.0
        unsupported = []
        if contexts:
            combined_context = " ".join(contexts).lower()
            # If key facts are present in answer, verify they also appear in contexts
            for fact in facts:
                if fact.lower() in generated_answer.lower() and fact.lower() not in combined_context:
                    faithfulness = max(0.0, faithfulness - 0.3)
                    unsupported.append(f"Fact '{fact}' not found in retrieved contexts.")

        # 6. Citation Correctness
        if citations is not None and expected_evidence:
            cit_metrics = compute_citation_metrics(citations, expected_evidence)
            citation_correctness = cit_metrics.precision
        else:
            citation_correctness = 1.0

        overall_score = round(
            (faithfulness + correctness + completeness + citation_correctness) / 4.0,
            4,
        )
        passed = completeness >= 0.5 and correctness >= 0.4 and len(generated_answer.strip()) > 5

        reasoning = (
            f"Deterministic evaluation passed with completeness={completeness}, "
            f"correctness={correctness}, faithfulness={faithfulness}."
            if passed
            else f"Deterministic evaluation failed: completeness={completeness}, correctness={correctness}."
        )

        return JudgeResult(
            passed=passed,
            score=overall_score,
            faithfulness=faithfulness,
            correctness=correctness,
            completeness=completeness,
            citation_correctness=citation_correctness,
            supported=len(unsupported) == 0,
            is_refusal=False,
            key_facts_coverage=completeness,
            reasoning=reasoning,
            unsupported_claims=unsupported if not passed else [],
        )


JUDGE_SYSTEM_PROMPT = """You are an expert, impartial evaluator for Enterprise Retrieval-Augmented Generation (RAG) systems.
Your job is to rigorously evaluate a generated answer against the user's query, retrieved contexts, expected answer, expected key facts, and citations.

Return your evaluation strictly as a valid JSON object matching this schema:
{
  "faithfulness": float between 0.0 and 1.0,
  "correctness": float between 0.0 and 1.0,
  "completeness": float between 0.0 and 1.0,
  "citation_correctness": float between 0.0 and 1.0,
  "supported": boolean (true if all claims are grounded in context without hallucination),
  "reasoning": string explaining the scores,
  "unsupported_claims": array of strings listing any ungrounded assertions made in the answer
}

Evaluation Criteria:
1. Faithfulness (0.0 to 1.0): Are all claims in the generated answer strictly supported by the provided context? Deduct heavily for hallucinated facts not in context.
2. Correctness (0.0 to 1.0): Is the generated answer factually accurate compared to the expected answer / expected key facts?
3. Completeness (0.0 to 1.0): Does the answer cover all necessary key facts and fully satisfy the query?
4. Citation Correctness (0.0 to 1.0): Are source citations accurate, valid, and attributed to the supporting context?
5. Refusal Handling:
   - If expected_behavior is "refuse" and the model refused due to lack of evidence, score 1.0 across all metrics and set supported=true.
   - If expected_behavior is "refuse" but the model fabricated an answer, score 0.0 and set supported=false.
   - If expected_behavior is "answer" but the model refused, score 0.0 for correctness and completeness.
"""


class LLMJudge(BaseJudge):
    """
    Production-grade LLM Judge behind BaseJudge abstraction.
    Uses structured output with Google Gemini or OpenAI to evaluate:
    1. Faithfulness / groundedness
    2. Answer correctness
    3. Answer completeness
    4. Citation correctness
    """

    def __init__(
        self,
        provider: Optional[str] = None,
        model: Optional[str] = None,
        api_key: Optional[str] = None,
    ):
        self.provider = provider
        self.model_name = model
        self.api_key = api_key
        self._openai_client: Optional[AsyncOpenAI] = None

        # Determine provider and check credentials
        if not self.provider:
            if settings.GEMINI_API_KEY and settings.GEMINI_API_KEY.strip():
                self.provider = "gemini"
            elif settings.OPENAI_API_KEY and settings.OPENAI_API_KEY.strip():
                self.provider = "openai"
            else:
                self.provider = "unconfigured"

        if self.provider == "gemini":
            active_key = self.api_key or settings.GEMINI_API_KEY
            if not active_key or not active_key.strip():
                raise ValueError("LLMJudge configured for Gemini but no GEMINI_API_KEY is available.")
            genai.configure(api_key=active_key.strip())
            if not self.model_name:
                self.model_name = settings.GEMINI_MODEL
        elif self.provider == "openai":
            active_key = self.api_key or settings.OPENAI_API_KEY
            if not active_key or not active_key.strip():
                raise ValueError("LLMJudge configured for OpenAI but no OPENAI_API_KEY is available.")
            self._openai_client = AsyncOpenAI(api_key=active_key.strip())
            if not self.model_name:
                self.model_name = settings.LLM_MODEL
        elif self.provider == "unconfigured":
            raise ValueError(
                "LLMJudge requires valid credentials. Neither GEMINI_API_KEY nor OPENAI_API_KEY is configured."
            )

    async def evaluate(
        self,
        query: str,
        generated_answer: str,
        ground_truth_answer: Optional[str] = None,
        contexts: Optional[List[str]] = None,
        key_facts: Optional[List[str]] = None,
        expected_behavior: str = "answer",
        citations: Optional[List[Any]] = None,
        expected_evidence: Optional[List[EvidenceAnchor]] = None,
    ) -> JudgeResult:
        """
        Executes structured LLM evaluation against input evidence and expectations.
        """
        payload = {
            "query": query,
            "generated_answer": generated_answer,
            "expected_behavior": expected_behavior,
            "ground_truth_answer": ground_truth_answer or "N/A",
            "expected_key_facts": key_facts or [],
            "retrieved_contexts": contexts or [],
            "citations": citations or [],
        }

        user_content = (
            f"Please evaluate the following RAG output:\n\n"
            f"{json.dumps(payload, indent=2, ensure_ascii=False)}"
        )

        raw_response_text = ""
        try:
            if self.provider == "gemini":
                raw_response_text = await self._call_gemini(user_content)
            elif self.provider == "openai":
                raw_response_text = await self._call_openai(user_content)
            else:
                raise ValueError(f"Unsupported LLMJudge provider: {self.provider}")

            # Parse & strongly validate structured output
            parsed_schema = self._parse_and_validate(raw_response_text)
        except Exception as err:
            logger.error(f"LLMJudge failed during evaluation: {err}")
            safe_err = re.sub(r"(AIza[0-9A-Za-z-_]{35}|sk-[a-zA-Z0-9]{32,})", "[REDACTED]", str(err))
            return JudgeResult(
                passed=False,
                score=0.0,
                faithfulness=0.0,
                correctness=0.0,
                completeness=0.0,
                citation_correctness=0.0,
                supported=False,
                is_refusal=False,
                key_facts_coverage=0.0,
                reasoning=f"LLM Judge execution failure: {safe_err[:200]}",
                unsupported_claims=["Judge evaluation failed due to provider or schema error."],
                metadata={"error": safe_err[:200]},
            )

        is_refusal = detect_refusal(generated_answer)
        overall_score = round(
            (parsed_schema.faithfulness + parsed_schema.correctness + parsed_schema.completeness + parsed_schema.citation_correctness) / 4.0,
            4,
        )

        passed = (
            parsed_schema.faithfulness >= 0.7
            and parsed_schema.correctness >= 0.7
            and parsed_schema.completeness >= 0.5
            and (not is_refusal if expected_behavior == "answer" else is_refusal)
        )

        # Coverage metric for backward compatibility
        key_facts_coverage = parsed_schema.completeness
        if key_facts:
            key_facts_coverage = compute_key_facts_coverage(generated_answer, key_facts)

        return JudgeResult(
            passed=passed,
            score=overall_score,
            faithfulness=parsed_schema.faithfulness,
            correctness=parsed_schema.correctness,
            completeness=parsed_schema.completeness,
            citation_correctness=parsed_schema.citation_correctness,
            supported=parsed_schema.supported,
            is_refusal=is_refusal,
            key_facts_coverage=key_facts_coverage,
            reasoning=parsed_schema.reasoning,
            unsupported_claims=parsed_schema.unsupported_claims,
            metadata={
                "provider": self.provider,
                "model": self.model_name,
            },
        )

    async def _call_gemini(self, user_content: str) -> str:
        """Invokes Gemini using JSON mime-type response mode."""
        model_name = self.model_name
        if model_name.startswith("models/"):
            model_name = model_name[len("models/"):]

        gemini_model = genai.GenerativeModel(
            model_name,
            system_instruction=JUDGE_SYSTEM_PROMPT,
            generation_config={"response_mime_type": "application/json"},
        )
        response = await asyncio.to_thread(gemini_model.generate_content, user_content)
        if response and response.text:
            return response.text.strip()
        raise RuntimeError("Empty response received from Gemini judge.")

    async def _call_openai(self, user_content: str) -> str:
        """Invokes OpenAI with json_object response format."""
        if not self._openai_client:
            raise RuntimeError("OpenAI client not initialized.")

        resp = await self._openai_client.chat.completions.create(
            model=self.model_name,
            messages=[
                {"role": "system", "content": JUDGE_SYSTEM_PROMPT},
                {"role": "user", "content": user_content},
            ],
            response_format={"type": "json_object"},
            temperature=0.0,
        )
        msg = resp.choices[0].message.content
        if msg:
            return msg.strip()
        raise RuntimeError("Empty response received from OpenAI judge.")

    def _parse_and_validate(self, text: str) -> JudgeOutputSchema:
        """Extracts JSON, clamps scores to [0.0, 1.0], and parses into strongly typed JudgeOutputSchema."""
        cleaned = text.strip()
        # Strip markdown code blocks if present
        if cleaned.startswith("```"):
            cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
            cleaned = re.sub(r"\s*```$", "", cleaned)
            cleaned = cleaned.strip()

        try:
            data = json.loads(cleaned)
        except Exception as exc:
            raise ValueError(f"LLM judge output could not be parsed as valid JSON: {str(exc)[:100]}") from None

        if not isinstance(data, dict):
            raise ValueError("LLM judge response must be a JSON dictionary object.")

        # Ensure numeric fields are clamped to [0.0, 1.0] to absorb provider boundary values
        for field_name in ("faithfulness", "correctness", "completeness", "citation_correctness"):
            if field_name in data and data[field_name] is not None:
                try:
                    val = float(data[field_name])
                    data[field_name] = max(0.0, min(1.0, round(val, 4)))
                except (ValueError, TypeError):
                    data[field_name] = 0.0

        try:
            return JudgeOutputSchema.model_validate(data)
        except Exception as pydantic_err:
            raise ValueError(f"LLM judge output failed schema validation: {str(pydantic_err)[:150]}") from None
