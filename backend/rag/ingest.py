"""
RAG Ingestion / Chunking Layer -- Phase 3.

Reads the local structured knowledge source (rag/data/seed_knowledge.json)
and produces a deterministic list of chunk records ready for embedding and
storage in ChromaDB, or for direct procedure-filtered keyword ranking in the
offline fallback path (see knowledge_base.py).

Design notes:
  - The current seed knowledge base is small (5 short clinical documents), so
    each document currently yields exactly one chunk. _split_into_chunks()
    is sentence-aware and will automatically split any future, longer vetted
    protocol document into multiple chunks without any other code changes.
  - Chunk ids are deterministic: f"{doc_id}-c{n}". Re-running ingestion
    against unchanged source content always produces the same ids, which is
    what makes upsert-based Chroma indexing idempotent (see vector_store.py).
  - No clinical content is invented here -- every chunk's `content` is a
    verbatim (or verbatim-split) excerpt of the corresponding seed document.
    `body_region` and `category` are derived bookkeeping labels (from the
    existing `procedure` code and `topic` text respectively), not clinical
    facts.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

_DATA_PATH = Path(__file__).parent / "data" / "seed_knowledge.json"
_SOURCE_LABEL = "OrthoSync Clinical Knowledge Base (seed)"
_MAX_CHUNK_CHARS = 800

# Derived (not fabricated) body-region label per procedure code, using the
# same procedure vocabulary already present in the seed documents ("TKA",
# "THA", "All"). "All" denotes cross-procedure generic guidance, not a body
# region -- mapped to "general" for metadata purposes only.
_BODY_REGION_BY_PROCEDURE: dict[str, str] = {
    "TKA": "knee",
    "THA": "hip",
    "All": "general",
}


def _slugify(text: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")
    return slug or "general"


def load_seed_documents() -> list[dict[str, Any]]:
    """Load the raw seed knowledge documents (clinical content unchanged)."""
    with open(_DATA_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def _split_into_chunks(text: str, max_chars: int = _MAX_CHUNK_CHARS) -> list[str]:
    """
    Sentence-aware chunk splitter. Every current seed document fits in a
    single chunk (well under max_chars); this only activates for future,
    longer protocol documents so the ingestion layer does not need to change
    when larger vetted content is added.
    """
    if len(text) <= max_chars:
        return [text]

    sentences = re.split(r"(?<=[.!?])\s+", text)
    chunks: list[str] = []
    current = ""
    for sentence in sentences:
        candidate = f"{current} {sentence}".strip()
        if len(candidate) <= max_chars:
            current = candidate
        else:
            if current:
                chunks.append(current)
            current = sentence
    if current:
        chunks.append(current)
    return chunks


def build_chunks() -> list[dict[str, Any]]:
    """
    Build the full, deterministic list of chunk records from the seed
    knowledge source. Each record carries retained/derived metadata:
    chunk_id, doc_id, topic, title, procedure, body_region, category, days,
    content, keywords, source.
    """
    chunks: list[dict[str, Any]] = []
    for doc in load_seed_documents():
        body_region = _BODY_REGION_BY_PROCEDURE.get(doc["procedure"], "general")
        category = _slugify(doc["topic"])
        pieces = _split_into_chunks(doc["content"])
        for index, piece in enumerate(pieces):
            chunks.append({
                "chunk_id": f"{doc['id']}-c{index}",
                "doc_id": doc["id"],
                "topic": doc["topic"],
                "title": doc["topic"],
                "procedure": doc["procedure"],
                "body_region": body_region,
                "category": category,
                "days": doc["days"],
                "content": piece,
                "keywords": list(doc["keywords"]),
                "source": _SOURCE_LABEL,
            })
    return chunks
