"""
RAG Vector Store -- Phase 3 local ChromaDB-backed semantic retrieval.

Owns:
  - the lazy, once-only SentenceTransformer embedding model singleton
    (sentence-transformers/all-MiniLM-L6-v2, same model used by the Phase 2
    intent classifier -- loaded independently here to keep the rag and lam
    packages decoupled, but by name/config identical)
  - the lazy, once-only local persistent ChromaDB client/collection
  - (re)indexing the seed knowledge chunks (idempotent via upsert)
  - low-level semantic similarity queries with metadata (procedure) filtering

Fully local/offline: no cloud vector database, no external embedding API.
If ChromaDB or the embedding model cannot be loaded (missing dependency,
corrupted cache, no disk access, etc.) every function here degrades to
returning None so callers (knowledge_base.py) fall back to deterministic
keyword retrieval instead of crashing.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

from rag.ingest import build_chunks

MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"
# Local persistent on-disk vector store. Runtime cache only -- never
# committed to Git (see .gitignore).
PERSIST_DIRECTORY = Path(__file__).parent / "data" / "chroma_db"
COLLECTION_NAME = "orthosync_clinical_knowledge"

# Maximum cosine distance (collection uses hnsw:space="cosine") for a Chroma
# result to be considered a genuine semantic match rather than "nearest
# available, but not actually relevant" noise.
#
# PROVISIONAL initial value, chosen from the Phase 3 diagnostic run over the
# current 5-document seed set, not tuned to force any specific test to pass:
#   good THA retrieval                 ~= 0.4006
#   good TKA retrieval                 ~= 0.5427
#   good unseen semantic paraphrase     ~= 0.5567
#   irrelevant ("chocolate cake") query ~= 0.9393
# 0.75 sits roughly in the middle of the ~0.19-wide gap on either side (best
# observed genuine match 0.5567, worst observed irrelevant match 0.9393),
# comfortably clear of both clusters. It must be recalibrated once a larger
# vetted retrieval evaluation set (more documents, more query variety) is
# available -- five short seed documents are not enough to fit this
# statistically.
SEMANTIC_MAX_DISTANCE: float = 0.75

_embedder = None
_collection = None
_load_attempted = False
_available = False


def _load() -> bool:
    """
    Load the embedding model and open/create the local persistent Chroma
    collection exactly once (lazily, on first use). A failed load is treated
    as a stable "offline" state for the remainder of the process lifetime --
    subsequent calls do not retry.
    """
    global _embedder, _collection, _load_attempted, _available
    if _load_attempted:
        return _available
    _load_attempted = True
    try:
        import chromadb
        from sentence_transformers import SentenceTransformer

        _embedder = SentenceTransformer(MODEL_NAME)
        PERSIST_DIRECTORY.mkdir(parents=True, exist_ok=True)
        client = chromadb.PersistentClient(path=str(PERSIST_DIRECTORY))
        _collection = client.get_or_create_collection(
            name=COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"},
        )
        _available = True
        _upsert_chunks(_collection, _embedder)
    except Exception:
        _embedder = None
        _collection = None
        _available = False
    return _available


def _upsert_chunks(collection, embedder) -> None:
    """
    Embed and upsert every current seed chunk. Upsert (rather than add) is
    what makes re-running ingestion idempotent: chunk ids are deterministic,
    so calling this again just overwrites the same rows in place instead of
    duplicating them.
    """
    chunks = build_chunks()
    ids = [c["chunk_id"] for c in chunks]
    texts = [c["content"] for c in chunks]
    metadatas = [
        {
            "doc_id": c["doc_id"],
            "topic": c["topic"],
            "title": c["title"],
            "procedure": c["procedure"],
            "body_region": c["body_region"],
            "category": c["category"],
            "days": c["days"],
            # Chroma metadata values must be scalar (str/int/float/bool).
            "keywords": ",".join(c["keywords"]),
            "source": c["source"],
        }
        for c in chunks
    ]
    embeddings = embedder.encode(
        texts, normalize_embeddings=True, convert_to_numpy=True
    ).tolist()
    collection.upsert(ids=ids, documents=texts, metadatas=metadatas, embeddings=embeddings)


def is_available() -> bool:
    """Whether the ChromaDB + embedding backend loaded successfully."""
    return _load()


def reindex() -> Optional[int]:
    """
    Force (re)ingestion of the seed knowledge chunks into the collection.
    Safe to call multiple times: chunk ids are deterministic and upsert
    overwrites in place, so re-running never duplicates documents. Returns
    the resulting collection count, or None if the vector store is
    unavailable.
    """
    if not _load():
        return None
    _upsert_chunks(_collection, _embedder)
    return _collection.count()


def collection_count() -> Optional[int]:
    """Current row count of the Chroma collection, or None if unavailable."""
    if not _load():
        return None
    return _collection.count()


def query(query_text: str, procedure: str, limit: int) -> Optional[list[dict[str, Any]]]:
    """
    Semantic similarity search over the local Chroma collection, hard-
    filtered to documents tagged for `procedure` or the universal "All"
    procedure value (never both TKA- and THA-specific content at once).

    Results whose cosine distance exceeds SEMANTIC_MAX_DISTANCE are dropped
    as not genuinely relevant. If every candidate is filtered out this way,
    an empty list is returned (NOT None) -- the semantic retrieval
    infrastructure still worked correctly; it just found nothing relevant
    enough to surface, which must not trigger keyword fallback.

    Returns None (never raises) if the vector store or embedding model is
    unavailable, or if the query itself fails for any reason -- callers use
    this signal to trigger deterministic keyword fallback instead.
    """
    if not _load():
        return None
    try:
        query_embedding = _embedder.encode(
            [query_text], normalize_embeddings=True, convert_to_numpy=True
        ).tolist()
        result = _collection.query(
            query_embeddings=query_embedding,
            n_results=max(limit, 1),
            where={"procedure": {"$in": [procedure, "All"]}},
        )
    except Exception:
        return None

    ids = (result.get("ids") or [[]])[0]
    documents = (result.get("documents") or [[]])[0]
    metadatas = (result.get("metadatas") or [[]])[0]
    distances = (result.get("distances") or [[]])[0]

    parsed: list[dict[str, Any]] = []
    for i, chunk_id in enumerate(ids):
        distance = distances[i] if i < len(distances) else None
        if distance is not None and distance > SEMANTIC_MAX_DISTANCE:
            continue
        meta = metadatas[i] or {}
        keywords_raw = meta.get("keywords", "")
        parsed.append({
            "chunk_id": chunk_id,
            "doc_id": meta.get("doc_id", chunk_id),
            "topic": meta.get("topic", ""),
            "title": meta.get("title", meta.get("topic", "")),
            "procedure": meta.get("procedure", procedure),
            "body_region": meta.get("body_region", "general"),
            "category": meta.get("category", ""),
            "days": meta.get("days", ""),
            "content": documents[i] if i < len(documents) else "",
            "keywords": keywords_raw.split(",") if keywords_raw else [],
            "source": meta.get("source", ""),
            "distance": distance,
        })
    return parsed
