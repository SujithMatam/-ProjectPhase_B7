"""
Clinical Knowledge Base for Post-Operative Orthopedic Recovery (RAG) -- Phase 3.

Public interface (unchanged from Phase 1):
    ClinicalKnowledgeBase.query(query_text: str, procedure: str = "TKA", limit: int = 2)
        -> List[Dict[str, Any]]

Phase 3 retrieval flow:
    patient query -> semantic query embedding -> ChromaDB similarity search
                      (metadata-filtered to `procedure` or the universal
                      "All" procedure) -> top relevant clinical chunks
    Falls back to a deterministic, procedure-filtered keyword ranking over
    the SAME seed content if ChromaDB or the embedding model is unavailable
    for any reason (offline resilience -- the backend never crashes because
    the vector store is down).

The clinical content itself lives in rag/data/seed_knowledge.json and is
unchanged from the original hard-coded Phase 1 knowledge base -- this phase
only replaces HOW it is retrieved, not WHAT it says.

Procedure-aware by construction in BOTH retrieval paths: a chunk tagged for
one arthroplasty procedure (TKA or THA) is never returned for a query
resolved to the other, and non-arthroplasty/unresolved cases (GEN) only
receive universal ("All") guidance. This closes the original bug where
keyword overlap alone (e.g. the shared word "bend" in both a knee ROM
document and the hip-precautions document) could surface hip precautions
for a knee question regardless of procedure.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from rag import vector_store
from rag.ingest import build_chunks

_DEFAULT_PROCEDURE = "TKA"

# ---------------------------------------------------------------------------
# Deterministic, token/phrase-aware keyword matching for the offline
# fallback (no external NLP library -- see _normalize_word() docstring).
# ---------------------------------------------------------------------------

# Small, explicit variant map for irregular word forms that show up in real
# patient phrasing but not verbatim in the seed keyword list (e.g. the past
# participle "swollen" for the keyword "swelling"). Deliberately tiny and
# hand-curated -- not a general morphology/stemming engine.
_WORD_VARIANTS: dict[str, str] = {
    "swollen": "swelling",
    "swells": "swelling",
    "swell": "swelling",
}

# (suffix, minimum word length required before stripping it) -- checked in
# order, first match wins. Deliberately conservative: only strips a suffix
# when the remaining stem is still long enough to be meaningful, so short
# words like "a", "is", "an" are never touched.
_SUFFIX_RULES: tuple[tuple[str, int], ...] = (
    ("ing", 6),
    ("ed", 5),
    ("es", 5),
    ("s", 4),
)


def _normalize_word(word: str) -> str:
    """
    Light, fully deterministic single-word normalization used ONLY for
    whole-word keyword matching in the offline fallback: lowercase, map a
    small set of known irregular variants to their canonical keyword form,
    then strip at most one common regular suffix. This is intentionally not
    a general stemmer -- just enough to match simple regular variants
    (exercise/exercises, dressing/dressed) and the specific irregular
    swelling/swollen pair, without an NLP dependency. It never reduces a
    short word (e.g. "a", "an", "is") to something that could coincidentally
    equal a keyword stem.
    """
    word = word.lower()
    word = _WORD_VARIANTS.get(word, word)
    for suffix, min_len in _SUFFIX_RULES:
        if word.endswith(suffix) and len(word) >= min_len:
            return word[: -len(suffix)]
    return word


def _tokenize(text: str) -> list[str]:
    """Lowercase whole-word tokens, punctuation stripped."""
    return re.findall(r"[a-z]+", text.lower())


def _keyword_matches_query(keyword: str, query_lower: str, query_normalized_tokens: set[str]) -> bool:
    """
    Token/phrase-aware deterministic match, replacing naive unrestricted
    substring matching:
      - a multi-word keyword ("range of motion", "severe pain", "cross
        legs") matches as a literal whole-phrase, word-boundary-safe
        substring of the query -- still simple, but can no longer match a
        lone short word inside it (e.g. "an" no longer "matches" via being
        a substring of "range").
      - a single-word keyword matches only a WHOLE, normalized query word --
        never an arbitrary substring. This is what stops a token like "a"
        from "matching" merely because it is a substring of "calf".
    """
    keyword_lower = keyword.lower()
    if " " in keyword_lower:
        pattern = r"\b" + re.escape(keyword_lower) + r"\b"
        return re.search(pattern, query_lower) is not None
    return _normalize_word(keyword_lower) in query_normalized_tokens


@dataclass
class RetrievedChunk:
    """A single retrieved clinical chunk plus its retrieval metadata."""
    chunk_id: str
    doc_id: str
    topic: str
    title: str
    procedure: str
    body_region: str
    category: str
    days: str
    content: str
    keywords: List[str]
    source: str
    distance: Optional[float] = None

    def to_legacy_dict(self) -> Dict[str, Any]:
        """
        Shape matching the original Phase 1 CLINICAL_KNOWLEDGE_DOCS dict, so
        existing callers (ChatAgent, SymptomAssessmentAgent) that read
        doc["topic"] / doc["content"] keep working unmodified. The Phase 3
        metadata keys (chunk_id, title, body_region, category, source,
        distance) are additive.
        """
        return {
            "id": self.doc_id,
            "topic": self.topic,
            "procedure": self.procedure,
            "days": self.days,
            "content": self.content,
            "keywords": self.keywords,
            "chunk_id": self.chunk_id,
            "title": self.title,
            "body_region": self.body_region,
            "category": self.category,
            "source": self.source,
            "distance": self.distance,
        }


@dataclass
class RetrievalDetail:
    """Diagnostic detail behind a single retrieve_detailed() call."""
    query: str
    procedure_filter: str
    results: List[RetrievedChunk]
    retrieval_path: str  # "semantic_chroma" | "keyword_fallback"


def _keyword_fallback(query_text: str, procedure: str, limit: int) -> List[RetrievedChunk]:
    """
    Deterministic keyword-overlap ranking over the seed chunks, HARD-filtered
    by procedure (chunk procedure == requested code, or the universal "All"
    code) before any scoring happens. This is what makes the fallback safe
    against the original leakage bug: a THA-tagged chunk is excluded from the
    candidate set entirely for a TKA query, regardless of keyword overlap.

    Matching is token/phrase-aware (see _keyword_matches_query()), not naive
    substring matching -- a single-word keyword must match a whole,
    normalized query word, and a multi-word keyword phrase must appear as a
    literal whole-phrase in the query. This is what stops short common
    words (e.g. "a") from spuriously "matching" merely because they are a
    substring of some unrelated keyword (e.g. "calf").

    Only chunks with a strictly positive keyword-overlap score are returned
    (matching the original Phase 1 behavior). Procedure match alone is a
    necessary candidacy filter, not a scoring signal -- an unrelated query
    that happens to match the requested procedure but shares no keywords
    with any chunk must return an empty list, not an arbitrary zero-score
    "closest" chunk.
    """
    query_lower = query_text.lower()
    query_tokens = {_normalize_word(t) for t in _tokenize(query_text)}

    candidates = [
        chunk for chunk in build_chunks()
        if chunk["procedure"] == procedure or chunk["procedure"] == "All"
    ]

    scored: list[tuple[int, dict]] = []
    for chunk in candidates:
        score = 0
        for kw in chunk["keywords"]:
            if _keyword_matches_query(kw, query_lower, query_tokens):
                score += 2
        if score > 0:
            scored.append((score, chunk))

    scored.sort(key=lambda pair: pair[0], reverse=True)

    return [
        RetrievedChunk(
            chunk_id=chunk["chunk_id"],
            doc_id=chunk["doc_id"],
            topic=chunk["topic"],
            title=chunk["title"],
            procedure=chunk["procedure"],
            body_region=chunk["body_region"],
            category=chunk["category"],
            days=chunk["days"],
            content=chunk["content"],
            keywords=chunk["keywords"],
            source=chunk["source"],
            distance=None,
        )
        for _, chunk in scored[:limit]
    ]


class ClinicalKnowledgeBase:
    """
    Phase 3: ChromaDB semantic retrieval with a deterministic keyword-based
    offline fallback. See module docstring for the full retrieval flow.
    """

    @classmethod
    def query(
        cls,
        query_text: str,
        procedure: str = _DEFAULT_PROCEDURE,
        limit: int = 2,
    ) -> List[Dict[str, Any]]:
        """Preserved Phase 1 public interface. See retrieve_detailed() for diagnostics."""
        detail = cls.retrieve_detailed(query_text, procedure, limit)
        return [chunk.to_legacy_dict() for chunk in detail.results]

    @classmethod
    def retrieve_detailed(
        cls,
        query_text: str,
        procedure: str = _DEFAULT_PROCEDURE,
        limit: int = 2,
    ) -> RetrievalDetail:
        """
        Same retrieval as query(), plus full diagnostic detail: which chunks
        were retrieved (with distance/metadata) and which retrieval path was
        actually taken.
        """
        semantic = vector_store.query(query_text, procedure=procedure, limit=limit)
        if semantic is not None:
            results = [
                RetrievedChunk(
                    chunk_id=item["chunk_id"],
                    doc_id=item["doc_id"],
                    topic=item["topic"],
                    title=item["title"],
                    procedure=item["procedure"],
                    body_region=item["body_region"],
                    category=item["category"],
                    days=item["days"],
                    content=item["content"],
                    keywords=item["keywords"],
                    source=item["source"],
                    distance=item["distance"],
                )
                for item in semantic
            ]
            return RetrievalDetail(
                query=query_text,
                procedure_filter=procedure,
                results=results,
                retrieval_path="semantic_chroma",
            )

        fallback_results = _keyword_fallback(query_text, procedure, limit)
        return RetrievalDetail(
            query=query_text,
            procedure_filter=procedure,
            results=fallback_results,
            retrieval_path="keyword_fallback",
        )
