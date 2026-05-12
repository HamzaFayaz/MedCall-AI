import argparse
import json
from dataclasses import asdict, dataclass
from typing import Any, Iterable

from src.config import config
from src.rag.embeddings import QwenEmbeddingAdapter, get_embedding_adapter
from src.rag.ingest import DEFAULT_KB_VERSION, KnowledgeChunk, load_knowledge_chunks


KNOWLEDGE_TABLE = "knowledge_chunks"
MATCH_RPC = "match_knowledge_chunks"
DEFAULT_TOP_K = 4
DEFAULT_UPSERT_BATCH_SIZE = 50
UPSERT_CONFLICT_TARGET = "source_file,section,kb_version"


@dataclass(frozen=True)
class KnowledgeMatch:
    id: str
    content: str
    source_file: str
    source_type: str
    section: str
    topic: str | None
    department: str | None
    allowed_claims: list[str]
    metadata: dict[str, Any]
    kb_version: str
    score: float

    @classmethod
    def from_supabase_row(cls, row: dict[str, Any]) -> "KnowledgeMatch":
        return cls(
            id=str(row["id"]),
            content=row["content"],
            source_file=row["source_file"],
            source_type=row["source_type"],
            section=row["section"],
            topic=row.get("topic"),
            department=row.get("department"),
            allowed_claims=list(row.get("allowed_claims") or []),
            metadata=dict(row.get("metadata") or {}),
            kb_version=row["kb_version"],
            score=float(row["score"]),
        )


@dataclass(frozen=True)
class UpsertResult:
    chunk_count: int
    embedding_count: int
    upserted_count: int
    kb_version: str


def create_supabase_client() -> Any:
    """Create the Supabase client used by RAG ingestion and retrieval."""
    url = config.SUPABASE_URL
    key = config.SUPABASE_SERVICE_ROLE_KEY or config.SUPABASE_KEY

    if not url:
        raise RuntimeError("SUPABASE_URL is required for RAG vector DB access.")

    if not key:
        raise RuntimeError(
            "SUPABASE_SERVICE_ROLE_KEY or SUPABASE_KEY is required for RAG vector DB access."
        )

    try:
        from supabase import create_client
    except ImportError as exc:
        raise RuntimeError(
            "Supabase dependencies are missing. Install requirements with "
            "`pip install -r requirements.txt`."
        ) from exc

    return create_client(url, key)


def _batched(items: list[dict[str, Any]], batch_size: int) -> Iterable[list[dict[str, Any]]]:
    if batch_size < 1:
        raise ValueError("batch_size must be at least 1.")

    for start in range(0, len(items), batch_size):
        yield items[start : start + batch_size]


def _normalize_vector(vector: list[float], expected_dimension: int) -> list[float]:
    if len(vector) != expected_dimension:
        raise ValueError(
            f"Embedding dimension mismatch: got {len(vector)}, "
            f"expected {expected_dimension}."
        )

    return [float(value) for value in vector]


def _row_for_chunk(
    chunk: KnowledgeChunk,
    embedding: list[float],
    expected_dimension: int,
) -> dict[str, Any]:
    row = chunk.to_supabase_payload()
    row["allowed_claims"] = row.get("allowed_claims") or []
    row["metadata"] = row.get("metadata") or {}
    row["embedding"] = _normalize_vector(embedding, expected_dimension)
    return row


class SupabaseRAGVectorDB:
    """Persist and search approved RAG chunks in Supabase pgvector."""

    def __init__(
        self,
        client: Any | None = None,
        embedding_adapter: QwenEmbeddingAdapter | None = None,
        table_name: str = KNOWLEDGE_TABLE,
        match_rpc: str = MATCH_RPC,
    ) -> None:
        self.client = client or create_supabase_client()
        self.embedding_adapter = embedding_adapter or get_embedding_adapter()
        self.table_name = table_name
        self.match_rpc = match_rpc

    def upsert_chunks(
        self,
        chunks: list[KnowledgeChunk],
        batch_size: int = DEFAULT_UPSERT_BATCH_SIZE,
    ) -> UpsertResult:
        if not chunks:
            return UpsertResult(
                chunk_count=0,
                embedding_count=0,
                upserted_count=0,
                kb_version=DEFAULT_KB_VERSION,
            )

        embeddings = self.embedding_adapter.embed_documents(
            [chunk.to_embedding_text() for chunk in chunks]
        )

        if len(embeddings) != len(chunks):
            raise RuntimeError(
                f"Embedding adapter returned {len(embeddings)} embeddings for "
                f"{len(chunks)} chunks."
            )

        rows = [
            _row_for_chunk(chunk, embedding, self.embedding_adapter.dimension)
            for chunk, embedding in zip(chunks, embeddings)
        ]

        upserted_count = 0
        for batch in _batched(rows, batch_size):
            response = (
                self.client.table(self.table_name)
                .upsert(batch, on_conflict=UPSERT_CONFLICT_TARGET)
                .execute()
            )
            upserted_count += len(response.data or batch)

        kb_versions = sorted({chunk.kb_version for chunk in chunks})
        kb_version = kb_versions[0] if len(kb_versions) == 1 else "multiple"

        return UpsertResult(
            chunk_count=len(chunks),
            embedding_count=len(embeddings),
            upserted_count=upserted_count,
            kb_version=kb_version,
        )

    def search_by_vector(
        self,
        query_embedding: list[float],
        top_k: int = DEFAULT_TOP_K,
        kb_version: str = DEFAULT_KB_VERSION,
        source_type: str | None = None,
        topic: str | None = None,
        department: str | None = None,
    ) -> list[KnowledgeMatch]:
        params = {
            "query_embedding": _normalize_vector(
                query_embedding,
                self.embedding_adapter.dimension,
            ),
            "match_count": max(top_k, 1),
            "filter_kb_version": kb_version,
            "filter_source_type": source_type,
            "filter_topic": topic,
            "filter_department": department,
        }

        response = self.client.rpc(self.match_rpc, params).execute()
        return [
            KnowledgeMatch.from_supabase_row(row)
            for row in response.data or []
        ]

    def search(
        self,
        query: str,
        top_k: int = DEFAULT_TOP_K,
        kb_version: str = DEFAULT_KB_VERSION,
        source_type: str | None = None,
        topic: str | None = None,
        department: str | None = None,
    ) -> list[KnowledgeMatch]:
        query_embedding = self.embedding_adapter.embed_query(query)
        return self.search_by_vector(
            query_embedding=query_embedding,
            top_k=top_k,
            kb_version=kb_version,
            source_type=source_type,
            topic=topic,
            department=department,
        )


def ingest_approved_knowledge(
    kb_version: str = DEFAULT_KB_VERSION,
    vector_db: SupabaseRAGVectorDB | None = None,
) -> UpsertResult:
    chunks = load_knowledge_chunks(kb_version=kb_version)
    db = vector_db or SupabaseRAGVectorDB()
    return db.upsert_chunks(chunks)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Upsert and search approved Mercy General RAG chunks in Supabase."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    ingest_parser = subparsers.add_parser("ingest", help="Embed and upsert approved KB chunks.")
    ingest_parser.add_argument(
        "--kb-version",
        default=DEFAULT_KB_VERSION,
        help="Knowledge base version tag to write.",
    )
    ingest_parser.add_argument(
        "--batch-size",
        type=int,
        default=DEFAULT_UPSERT_BATCH_SIZE,
        help="Supabase upsert batch size.",
    )

    search_parser = subparsers.add_parser("search", help="Search approved KB chunks.")
    search_parser.add_argument("query", help="Policy, FAQ, or care-routing query.")
    search_parser.add_argument("--top-k", type=int, default=DEFAULT_TOP_K)
    search_parser.add_argument("--kb-version", default=DEFAULT_KB_VERSION)
    search_parser.add_argument("--source-type")
    search_parser.add_argument("--topic")
    search_parser.add_argument("--department")

    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    db = SupabaseRAGVectorDB()

    if args.command == "ingest":
        chunks = load_knowledge_chunks(kb_version=args.kb_version)
        result = db.upsert_chunks(chunks, batch_size=args.batch_size)
        print(json.dumps(asdict(result), indent=2))
        return

    matches = db.search(
        query=args.query,
        top_k=args.top_k,
        kb_version=args.kb_version,
        source_type=args.source_type,
        topic=args.topic,
        department=args.department,
    )
    print(json.dumps([asdict(match) for match in matches], indent=2))


if __name__ == "__main__":
    main()
