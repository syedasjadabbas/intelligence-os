import logging
import re
from typing import Any, Dict, List, Optional, Union
from openai import AsyncOpenAI

from app.core.config import settings

logger = logging.getLogger(__name__)

PRONOUN_PATTERN = re.compile(
    r"\b(it|its|they|them|their|this|that|these|those|the system|the unit|the device)\b",
    re.IGNORECASE,
)


class QueryRewriterService:
    """
    Query Rewriting Service for contextual conversational RAG.
    Resolves coreferences and anaphora (e.g. 'what is its voltage?')
    by examining past conversation turns and rewriting the question into a self-contained query.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
    ):
        self.api_key = api_key if api_key is not None else settings.OPENAI_API_KEY
        self.model = model or settings.LLM_MODEL
        self._client: Optional[AsyncOpenAI] = None

        if self.api_key and self.api_key.strip():
            try:
                self._client = AsyncOpenAI(api_key=self.api_key.strip())
            except Exception as exc:
                logger.warning(
                    f"Failed to initialize OpenAI client in QueryRewriter: {exc}"
                )

    def _has_coreference(self, query: str) -> bool:
        """Checks if the query contains coreferential pronouns or ellipsis."""
        cleaned = query.strip()
        if PRONOUN_PATTERN.search(cleaned):
            return True
        # Check for elliptical follow-ups like "What about ...?", "And for ...?"
        if re.match(r"^(what|how|and)\s+(about|for)\b", cleaned, re.IGNORECASE):
            return True
        return False

    def _extract_subject_from_history(
        self,
        history: List[Union[Dict[str, Any], Any]],
    ) -> Optional[str]:
        """
        Extracts salient noun phrase or subject entity from previous messages
        for deterministic local coreference resolution.
        Prioritizes user queries from non-refusal turns.
        """
        # Filter out refusal messages and pair them with user queries
        valid_user_contents = []
        valid_assistant_contents = []
        skip_prev_user = False

        for item in reversed(history):
            content = ""
            role = ""
            if isinstance(item, dict):
                content = item.get("content", "")
                role = item.get("role", "")
            elif hasattr(item, "content"):
                content = getattr(item, "content", "")
                role = getattr(item, "role", "")

            # If assistant replied with refusal, mark to skip preceding user query
            if role == "assistant" and settings.INSUFFICIENT_EVIDENCE_PHRASE.lower() in content.lower():
                skip_prev_user = True
                continue

            if role == "user" and skip_prev_user:
                skip_prev_user = False
                continue

            skip_prev_user = False
            if content:
                if role == "user":
                    valid_user_contents.append(content)
                else:
                    valid_assistant_contents.append(content)

        # Check user queries first for explicit query subjects
        for content in valid_user_contents:
            # Look for Title Case multi-word phrases (e.g. Arc Reactor, Iron Legion) without crossing newlines
            title_phrases = re.findall(r"\b[A-Z][a-z]+(?:[ \t]+[A-Z][a-z]+)+\b", content)
            if title_phrases:
                candidate = title_phrases[0].strip()
                candidate = re.sub(r"^(The|A|An)\s+", "", candidate, flags=re.IGNORECASE)
                if candidate:
                    return candidate

            match = re.search(r"(?:about|on|for|in the|in)\s+([A-Za-z0-9_\-\s]{3,30})", content, re.IGNORECASE)
            if match:
                candidate = match.group(1).strip().strip("?.,!")
                candidate = re.sub(r"^(the|a|an)\s+", "", candidate, flags=re.IGNORECASE)
                if candidate:
                    return candidate

        # If not found in user messages, check assistant messages
        for content in valid_assistant_contents:
            # Remove markdown headings before checking
            cleaned_content = re.sub(r"^#+[^\n]*$", "", content, flags=re.MULTILINE)
            title_phrases = re.findall(r"\b[A-Z][a-z]+(?:[ \t]+[A-Z][a-z]+)+\b", cleaned_content)
            if title_phrases:
                for candidate in title_phrases:
                    cand = re.sub(r"^(The|A|An)\s+", "", candidate, flags=re.IGNORECASE).strip()
                    if cand and cand.lower() not in {"emergency shutdown", "liquid nitrogen", "insufficient evidence"}:
                        return cand

        return None

    async def rewrite_query(
        self,
        query: str,
        conversation_history: Optional[List[Union[Dict[str, Any], Any]]] = None,
    ) -> str:
        """
        Rewrites a user question into a self-contained search query.
        Preserves original query if standalone, or if no history is provided.
        """
        cleaned_query = query.strip()
        if not conversation_history or len(conversation_history) == 0:
            return cleaned_query

        # Check if rewriting is necessary
        if not self._has_coreference(cleaned_query):
            return cleaned_query

        # 1. Use OpenAI if client is available
        if self._client:
            try:
                formatted_turns = []
                for turn in conversation_history[-6:]:  # Last 3 turns (user & assistant)
                    role = (
                        turn.get("role")
                        if isinstance(turn, dict)
                        else getattr(turn, "role", "user")
                    )
                    content = (
                        turn.get("content")
                        if isinstance(turn, dict)
                        else getattr(turn, "content", "")
                    )
                    if role in ("user", "assistant") and content:
                        formatted_turns.append({"role": role, "content": content})

                if formatted_turns:
                    messages = [
                        {
                            "role": "system",
                            "content": (
                                "You are a query rewriting module for enterprise RAG search. "
                                "Given the prior conversation context and the user's latest follow-up question, "
                                "rewrite the question into a single, self-contained search query resolving all pronouns "
                                "(e.g., 'it', 'its', 'their', 'this'). "
                                "Do NOT answer the question. Output ONLY the rewritten query text."
                            ),
                        },
                        *formatted_turns,
                        {
                            "role": "user",
                            "content": f"Rewrite this follow-up query to be self-contained: {cleaned_query}",
                        },
                    ]
                    response = await self._client.chat.completions.create(
                        model=self.model,
                        messages=messages,
                        temperature=0.0,
                        max_tokens=60,
                    )
                    rewritten = response.choices[0].message.content.strip().strip('"')
                    if rewritten:
                        logger.info(
                            f"LLM rewritten query: '{cleaned_query}' -> '{rewritten}'"
                        )
                        return rewritten
            except Exception as exc:
                logger.warning(
                    f"OpenAI query rewriting failed: {exc}. Using deterministic fallback."
                )

        # 2. Deterministic local coreference rewriting fallback
        subject = self._extract_subject_from_history(conversation_history)
        if subject:
            # Replace possessive "its" -> "{Subject}'s"
            rewritten = re.sub(r"\bits\b", f"{subject}'s", cleaned_query, flags=re.IGNORECASE)
            # Replace pronoun "it" -> "{Subject}"
            rewritten = re.sub(r"\bit\b", subject, rewritten, flags=re.IGNORECASE)
            # Replace "this/that system" -> "{Subject}"
            rewritten = re.sub(
                r"\b(this|that)\s+(system|unit|device|machine)\b",
                subject,
                rewritten,
                flags=re.IGNORECASE,
            )
            # If nothing replaced but coreference was detected, append subject context
            if rewritten == cleaned_query:
                rewritten = f"{cleaned_query} ({subject})"

            logger.info(
                f"Deterministic rewritten query: '{cleaned_query}' -> '{rewritten}'"
            )
            return rewritten

        return cleaned_query


# Global singleton query rewriter
query_rewriter = QueryRewriterService()
