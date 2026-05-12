import argparse
import json
import re
from dataclasses import asdict, dataclass
from typing import Any, Literal

from src.rag.ingest import DEFAULT_KB_VERSION
from src.rag.vector_db import DEFAULT_TOP_K, KnowledgeMatch, SupabaseRAGVectorDB


RetrievalStatus = Literal["ok", "empty", "empty_query", "out_of_scope"]

MAX_TOP_K = 10
SAFE_EMPTY_RETRIEVAL_MESSAGE = (
    "I can't assess symptoms from the knowledge base. I can help with scheduling "
    "or connect the caller to hospital staff."
)
STRUCTURED_TOOL_REQUIRED_MESSAGE = (
    "This request needs a structured EHR or scheduling tool, not RAG retrieval."
)
ALLOWED_SOURCE_TYPES = {
    "operational_policy",
    "department_services",
    "symptom_routing",
    "faq_script",
}

OUT_OF_SCOPE_PATTERNS: tuple[tuple[str, str], ...] = (
    ("live_availability", r"\b(available|availability|open slot|appointment slot|slots?)\b"),
    ("booking_side_effect", r"\b(book me|schedule me|make an appointment|reserve|confirm my appointment)\b"),
    ("appointment_change", r"\b(cancel my|reschedule my|change my|move my)\b"),
    ("patient_identity", r"\b(my patient id|my date of birth|verify me|authenticate me)\b"),
    ("patient_clinical_profile", r"\b(my medications?|my allergies|my conditions?|my diagnosis|my test results?|my medical record)\b"),
    ("live_insurance_or_referral", r"\b(my insurance eligibility|am i covered|my referral status)\b"),
)


@dataclass(frozen=True)
class RetrievalFilters:
    topic: str | None = None
    department: str | None = None
    kb_version: str = DEFAULT_KB_VERSION


@dataclass(frozen=True)
class RetrievalMatch:
    content: str
    snippet: str
    source_file: str
    source_type: str
    section: str
    topic: str | None
    department: str | None
    score: float
    citation: dict[str, str | None]
    allowed_claims: list[str]
    metadata: dict[str, Any]


@dataclass(frozen=True)
class RetrievalResult:
    query: str
    status: RetrievalStatus
    matches: list[RetrievalMatch]
    filters: RetrievalFilters
    fallback: str | None = None
    out_of_scope_reason: str | None = None


def _coerce_top_k(top_k: int) -> int:
    return min(max(int(top_k), 1), MAX_TOP_K)


def _find_out_of_scope_reason(query: str) -> str | None:
    lowered = query.lower()
    for reason, pattern in OUT_OF_SCOPE_PATTERNS:
        if re.search(pattern, lowered):
            return reason
    return None


def _build_snippet(content: str, max_chars: int = 500) -> str:
    normalized = re.sub(r"\s+", " ", content).strip()
    if len(normalized) <= max_chars:
        return normalized
    return f"{normalized[: max_chars - 3].rstrip()}..."


def _to_retrieval_match(match: KnowledgeMatch) -> RetrievalMatch:
    return RetrievalMatch(
        content=match.content,
        snippet=_build_snippet(match.content),
        source_file=match.source_file,
        source_type=match.source_type,
        section=match.section,
        topic=match.topic,
        department=match.department,
        score=match.score,
        citation={
            "source_file": match.source_file,
            "section": match.section,
            "kb_version": match.kb_version,
        },
        allowed_claims=match.allowed_claims,
        metadata=match.metadata,
    )


class RAGKnowledgeService:
    """Application-facing RAG retrieval service.

    This service returns source chunks for the orchestrator/LLM. It does not
    compose final patient-facing answers or perform scheduling side effects.
    """

    def __init__(
        self,
        vector_db: SupabaseRAGVectorDB | None = None,
        kb_version: str = DEFAULT_KB_VERSION,
    ) -> None:
        self.vector_db = vector_db or SupabaseRAGVectorDB()
        self.kb_version = kb_version

    def retrieve_knowledge(
        self,
        query: str,
        topic: str | None = None,
        department: str | None = None,
        top_k: int = DEFAULT_TOP_K,
    ) -> RetrievalResult:
        clean_query = query.strip()
        filters = RetrievalFilters(
            topic=topic,
            department=department,
            kb_version=self.kb_version,
        )

        if not clean_query:
            return RetrievalResult(
                query=query,
                status="empty_query",
                matches=[],
                filters=filters,
                fallback=SAFE_EMPTY_RETRIEVAL_MESSAGE,
            )

        out_of_scope_reason = _find_out_of_scope_reason(clean_query)
        if out_of_scope_reason:
            return RetrievalResult(
                query=clean_query,
                status="out_of_scope",
                matches=[],
                filters=filters,
                fallback=STRUCTURED_TOOL_REQUIRED_MESSAGE,
                out_of_scope_reason=out_of_scope_reason,
            )

        raw_matches = self.vector_db.search(
            query=clean_query,
            top_k=_coerce_top_k(top_k),
            kb_version=self.kb_version,
            topic=topic,
            department=department,
        )
        matches = [
            _to_retrieval_match(match)
            for match in raw_matches
            if match.source_type in ALLOWED_SOURCE_TYPES
        ]

        if not matches:
            return RetrievalResult(
                query=clean_query,
                status="empty",
                matches=[],
                filters=filters,
                fallback=SAFE_EMPTY_RETRIEVAL_MESSAGE,
            )

        return RetrievalResult(
            query=clean_query,
            status="ok",
            matches=matches,
            filters=filters,
        )


def retrieve_knowledge(
    query: str,
    topic: str | None = None,
    department: str | None = None,
    top_k: int = DEFAULT_TOP_K,
) -> dict[str, Any]:
    service = RAGKnowledgeService()
    result = service.retrieve_knowledge(
        query=query,
        topic=topic,
        department=department,
        top_k=top_k,
    )
    return asdict(result)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Retrieve approved Mercy General RAG chunks.")
    parser.add_argument("query", help="Policy, FAQ, or care-routing query.")
    parser.add_argument("--topic")
    parser.add_argument("--department")
    parser.add_argument("--top-k", type=int, default=DEFAULT_TOP_K)
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    result = retrieve_knowledge(
        query=args.query,
        topic=args.topic,
        department=args.department,
        top_k=args.top_k,
    )
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
