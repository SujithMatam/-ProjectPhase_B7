"""
Freeze RAG retrieval for every eval query into a contexts file.

Uses the project's existing retriever as-is --
rag.knowledge_base.ClinicalKnowledgeBase.retrieve_detailed() -- imported
read-only, filtered by the query's own procedure code, top_k=4. (Production
ChatAgent retrieves 2; this harness deliberately gives the models 4.) Same
embedding model, procedure filter and distance threshold as backend/rag,
because it IS backend/rag's code.

Two corpus modes:

  default     Retrieve against a COPY of backend/rag/data/chroma_db
              (.chroma_copy/). Opening the store upserts
              rag/data/seed_knowledge.json into it, exactly as the backend does.
  --corpus F  Build a separate scratch Chroma collection from F (a JSON file
              with the same schema as seed_knowledge.json) under
              .chroma_corpus/<sha>/, rebuilt from scratch on every run so it
              holds exactly F's documents.

Both modes redirect backend/rag in THIS process only, by overriding module
globals (rag.vector_store.PERSIST_DIRECTORY / COLLECTION_NAME and, for
--corpus, rag.ingest._DATA_PATH). No file under backend/rag is modified: the
whole backend/rag/data directory is fingerprinted (size + mtime of every file)
before and after, and any change aborts without writing output.

--window-filter  Ask the same retriever for 8 candidates instead of 4, then put
              the chunks whose `days` range contains the query's postop_day
              first (nearest distance first within each group) and keep the
              top 4. A chunk with no usable `days` value (empty, or not "N" /
              "N-M") counts as matching. Every chunk records window_match in
              both modes; the record carries window_filter.

Every context record carries a context_sha256 digest covering the corpus
identity (file sha256), retriever settings, the window_filter flag and the
retrieved chunks, so run_models.py treats a corpus or mode change as stale
even when the chunks retrieved for a query happen to be identical.

Only backend/rag is imported (rag.knowledge_base -> rag.vector_store,
rag.ingest). Nothing from agents/, lam/, triage/, doctor_alert or
patient_database is loaded.

Run with the backend virtualenv (needs chromadb + sentence-transformers):
    ..\\.venv\\Scripts\\python.exe build_context.py [--queries F] [--out F] [--corpus F] [--window-filter]
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from common import (
    BACKEND_DIR,
    CONTEXTS_PATH,
    EVAL_DIR,
    HARNESS_VERSION,
    QUERIES_PATH,
    load_queries,
    query_fingerprint,
    sha256_json,
    sha256_text,
    utc_now,
    write_jsonl_atomic,
)

sys.path.insert(1, str(BACKEND_DIR))  # so `import rag` resolves to backend/rag (read-only use)

RAG_DATA_DIR = BACKEND_DIR / "rag" / "data"
SOURCE_CHROMA_DIR = RAG_DATA_DIR / "chroma_db"
SEED_KNOWLEDGE_PATH = RAG_DATA_DIR / "seed_knowledge.json"
DEFAULT_COPY_DIR = EVAL_DIR / ".chroma_copy"
DEFAULT_CORPUS_INDEX_ROOT = EVAL_DIR / ".chroma_corpus"
COPY_MARKER = ".eval_chroma_copy"
TOP_K = 4
WINDOW_CANDIDATES = 8   # --window-filter: candidates fetched before reordering by post-op window
CORPUS_PROCEDURES = ("TKA", "THA", "All")   # the procedure codes backend/rag filters on


def parse_days(days: Optional[str]) -> Optional[Tuple[int, int]]:
    """'8-21' -> (8, 21), '7' -> (7, 7); None when there is no usable window."""
    text = (days or "").strip()
    match = re.fullmatch(r"(\d+)\s*-\s*(\d+)", text) or re.fullmatch(r"(\d+)", text)
    if not match:
        return None
    low = int(match.group(1))
    high = int(match.group(match.lastindex))
    return (low, high) if low <= high else None


def window_match(days: Optional[str], postop_day: int) -> bool:
    """True when the chunk's days range contains postop_day, or when it has no usable range."""
    window = parse_days(days)
    return window is None or window[0] <= postop_day <= window[1]


def apply_window_filter(chunks: List[Dict[str, Any]], keep: int) -> List[Dict[str, Any]]:
    """Window-matching chunks first, nearest distance first within each group; keep the top `keep`."""
    def key(chunk: Dict[str, Any]):
        distance = chunk["distance"] if chunk["distance"] is not None else float("inf")
        return (not chunk["window_match"], distance, chunk["retriever_rank"])
    return sorted(chunks, key=key)[:keep]


def _fingerprint(root: Path) -> Dict[str, Tuple[int, int]]:
    if not root.exists():
        return {}
    fingerprint = {}
    for path in sorted(root.rglob("*")):
        if path.is_file():
            stat = path.stat()
            fingerprint[str(path.relative_to(root))] = (stat.st_size, stat.st_mtime_ns)
    return fingerprint


def _guard_outside_rag_data(target: Path, flag: str) -> None:
    source = RAG_DATA_DIR.resolve()
    if target == source or source in target.parents or target in source.parents:
        raise SystemExit(f"ERROR: {flag} must be outside {RAG_DATA_DIR} and not a parent of it.")


def _claim_dir(target: Path) -> None:
    """Allow only an empty/absent directory or one this script created (marker file)."""
    if target.exists() and any(target.iterdir()) and not (target / COPY_MARKER).exists():
        raise SystemExit(f"ERROR: {target} exists and was not created by build_context.py; refusing to use it.")


def _prepare_copy(copy_dir: Path, refresh: bool) -> str:
    target = copy_dir.resolve()
    _guard_outside_rag_data(target, "--chroma-copy-dir")
    _claim_dir(target)
    marker = target / COPY_MARKER
    if refresh and marker.exists():
        shutil.rmtree(target)
    if marker.exists():
        return "reused existing copy (use --refresh-copy to re-copy)"
    if SOURCE_CHROMA_DIR.exists():
        shutil.copytree(SOURCE_CHROMA_DIR, target, dirs_exist_ok=True)
        origin = "copied from rag/data/chroma_db"
    else:
        target.mkdir(parents=True, exist_ok=True)
        origin = "rag/data/chroma_db absent; index built from seed_knowledge.json inside the copy"
    marker.write_text(f"created by build_context.py at {utc_now()}\n", encoding="utf-8")
    return origin


def _prepare_fresh_index(index_dir: Path) -> None:
    target = index_dir.resolve()
    _guard_outside_rag_data(target, "--corpus-index-dir")
    _claim_dir(target)
    if target.exists():
        shutil.rmtree(target)
    target.mkdir(parents=True)
    (target / COPY_MARKER).write_text(f"created by build_context.py at {utc_now()}\n", encoding="utf-8")


def _load_corpus(path: Path) -> Tuple[List[Dict[str, Any]], bytes]:
    """Validate a seed_knowledge.json-shaped corpus; fail loudly on any problem."""
    raw = path.read_bytes()
    try:
        docs = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise SystemExit(f"ERROR: --corpus {path}: not valid UTF-8 JSON ({exc})")
    if not isinstance(docs, list) or not docs:
        raise SystemExit(f"ERROR: --corpus {path}: expected a non-empty JSON list of documents")
    errors, seen = [], set()
    for index, doc in enumerate(docs):
        where = f"document #{index}"
        if not isinstance(doc, dict):
            errors.append(f"{where}: not an object")
            continue
        doc_id = doc.get("id")
        where = f"document #{index} ({doc_id!r})"
        if not (isinstance(doc_id, str) and doc_id.strip()):
            errors.append(f"{where}: id must be a non-empty string")
        elif doc_id in seen:
            errors.append(f"{where}: duplicate id")
        seen.add(doc_id)
        for key in ("topic", "content"):
            if not (isinstance(doc.get(key), str) and doc[key].strip()):
                errors.append(f"{where}: {key} must be a non-empty string")
        if not isinstance(doc.get("days"), str):
            errors.append(f"{where}: days must be a string (e.g. \"1-14\")")
        if doc.get("procedure") not in CORPUS_PROCEDURES:
            errors.append(f"{where}: procedure must be one of {CORPUS_PROCEDURES} (anything else is never retrieved)")
        keywords = doc.get("keywords")
        if not (isinstance(keywords, list) and all(isinstance(k, str) for k in keywords)):
            errors.append(f"{where}: keywords must be a list of strings")
    if errors:
        raise SystemExit(f"ERROR: --corpus {path} has schema problems:\n  " + "\n  ".join(errors))
    return docs, raw


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Freeze RAG context for each eval query.")
    parser.add_argument("--queries", type=Path, default=QUERIES_PATH)
    parser.add_argument("--out", type=Path, default=CONTEXTS_PATH)
    parser.add_argument("--corpus", type=Path, help="JSON corpus (seed_knowledge.json schema) to index in a scratch collection")
    parser.add_argument("--chroma-copy-dir", type=Path, default=DEFAULT_COPY_DIR, help="default mode: where the store copy lives")
    parser.add_argument("--corpus-index-root", type=Path, default=DEFAULT_CORPUS_INDEX_ROOT, help="--corpus mode: scratch index root")
    parser.add_argument("--refresh-copy", action="store_true", help="default mode: re-copy rag/data/chroma_db first")
    parser.add_argument("--top-k", type=int, default=TOP_K)
    parser.add_argument(
        "--window-filter", action="store_true",
        help=f"fetch {WINDOW_CANDIDATES} candidates, rank chunks whose days range contains postop_day first, keep --top-k",
    )
    parser.add_argument(
        "--allow-keyword-fallback", action="store_true",
        help="write contexts even if ChromaDB/sentence-transformers is unavailable (keyword ranking)",
    )
    args = parser.parse_args(argv)

    try:
        queries = load_queries(args.queries)
    except (OSError, ValueError) as exc:
        print(exc)
        return 2
    if not queries:
        print(f"No queries yet: fill in {args.queries.name} (the all-empty template row is ignored).")
        return 1

    before = _fingerprint(RAG_DATA_DIR)

    from rag import ingest, vector_store  # read-only use of project code; globals overridden in-process only

    if args.corpus:
        corpus_path = args.corpus.resolve()
        docs, raw = _load_corpus(corpus_path)
        corpus_sha = sha256_text(raw.decode("utf-8"))
        index_dir = args.corpus_index_root / corpus_sha[:16]
        _prepare_fresh_index(index_dir)
        ingest._DATA_PATH = corpus_path
        vector_store.PERSIST_DIRECTORY = index_dir.resolve()
        vector_store.COLLECTION_NAME = f"eval_corpus_{corpus_sha[:16]}"
        corpus_info = {"kind": "custom_corpus", "path": str(corpus_path), "sha256": corpus_sha, "n_documents": len(docs)}
        index_origin = f"fresh scratch collection at {index_dir.resolve()}"
    else:
        seed_text = SEED_KNOWLEDGE_PATH.read_text(encoding="utf-8")
        index_origin = _prepare_copy(args.chroma_copy_dir, args.refresh_copy)
        vector_store.PERSIST_DIRECTORY = args.chroma_copy_dir.resolve()
        corpus_info = {
            "kind": "rag_store_copy",
            "path": "rag/data/seed_knowledge.json",
            "sha256": sha256_text(seed_text),
            "n_documents": len(json.loads(seed_text)),
        }
    print(f"Corpus: {corpus_info['kind']} {corpus_info['path']} (sha256 {corpus_info['sha256'][:16]}, "
          f"{corpus_info['n_documents']} documents)")
    print(f"Index:  {index_origin}")

    from rag.knowledge_base import ClinicalKnowledgeBase

    semantic_available = vector_store.is_available()
    if not semantic_available and not args.allow_keyword_fallback:
        print(
            "ERROR: the ChromaDB / sentence-transformers backend did not load, so retrieval would "
            "silently use keyword fallback. Run with backend/.venv's python, or pass "
            "--allow-keyword-fallback to accept that."
        )
        return 2

    expected_chunks = len(ingest.build_chunks())
    collection_count = vector_store.collection_count() if semantic_available else None
    if collection_count is not None and collection_count != expected_chunks:
        print(f"WARNING: the index holds {collection_count} chunks but the corpus produces {expected_chunks}; "
              "it contains entries that are no longer in the corpus (upserts never delete).")

    # Deterministic retriever settings -- part of every record's context digest.
    retriever = {
        "retriever": "rag.knowledge_base.ClinicalKnowledgeBase.retrieve_detailed",
        "embedding_model": vector_store.MODEL_NAME,
        "semantic_max_distance": vector_store.SEMANTIC_MAX_DISTANCE,
        "collection_name": vector_store.COLLECTION_NAME,
        "collection_count": collection_count,
        "corpus_chunk_count": expected_chunks,
    }

    candidate_k = max(WINDOW_CANDIDATES, args.top_k) if args.window_filter else args.top_k
    if args.window_filter:
        print(f"Window filter: {candidate_k} candidates per query, window-matching chunks first, keep {args.top_k}")

    records = []
    built_at = utc_now()
    unparsed_days = set()
    for query in queries:
        detail = ClinicalKnowledgeBase.retrieve_detailed(
            query["query"], procedure=query["procedure"], limit=candidate_k,
        )
        chunks = []
        for rank, chunk in enumerate(detail.results, start=1):
            if parse_days(chunk.days) is None:
                unparsed_days.add(f"{chunk.doc_id}={chunk.days!r}")
            chunks.append({
                "rank": rank,
                "chunk_id": chunk.chunk_id,
                "doc_id": chunk.doc_id,
                "topic": chunk.topic,
                "procedure": chunk.procedure,
                "days": chunk.days,
                "window_match": window_match(chunk.days, query["postop_day"]),
                "distance": chunk.distance,
                "content": chunk.content,
            })
        if args.window_filter:
            for chunk in chunks:
                chunk["retriever_rank"] = chunk["rank"]
            chunks = apply_window_filter(chunks, args.top_k)
            for rank, chunk in enumerate(chunks, start=1):
                chunk["rank"] = rank
        digest_basis = {
            "corpus": corpus_info,
            "retriever": retriever,
            "top_k": args.top_k,
            "window_filter": args.window_filter,
            "candidate_k": candidate_k,
            "procedure_filter": detail.procedure_filter,
            "retrieval_path": detail.retrieval_path,
            "chunks": chunks,
        }
        records.append({
            "id": query["id"],
            "domain": query["domain"],
            "procedure": query["procedure"],
            "postop_day": query["postop_day"],
            "answerability": query["answerability"],
            "query": query["query"],
            "query_sha256": query_fingerprint(query),
            "context_sha256": sha256_json(digest_basis),
            "top_k": args.top_k,
            "window_filter": args.window_filter,
            "candidate_k": candidate_k,
            "procedure_filter": detail.procedure_filter,
            "retrieval_path": detail.retrieval_path,
            "n_chunks": len(chunks),
            "n_window_mismatch": sum(1 for c in chunks if not c["window_match"]),
            "chunks": chunks,
            "corpus": corpus_info,
            "retriever_meta": {**retriever, "index_origin": index_origin},
            "built_at": built_at,
            "harness_version": HARNESS_VERSION,
        })
        found = ", ".join(
            (f"{c['doc_id']}({c['distance']:.3f})" if c["distance"] is not None else c["doc_id"])
            + ("" if c["window_match"] else "*")
            for c in chunks
        ) or "- (nothing within the distance threshold)"
        print(f"  {query['id']:<14} {query['procedure']}  {detail.retrieval_path:<16} {len(chunks)}: {found}")
    print("  (* = chunk's days range does not contain the query's postop_day)")
    if unparsed_days:
        print(f"  note: no usable days range (treated as matching): {', '.join(sorted(unparsed_days))}")

    if _fingerprint(RAG_DATA_DIR) != before:
        print("ERROR: backend/rag/data changed during this run; output NOT written. Investigate before continuing.")
        return 3

    write_jsonl_atomic(args.out, records)
    print(f"Wrote {len(records)} context record(s) to {args.out}")
    print("backend/rag/data unchanged (fingerprint verified).")
    print("Check each query's answerability label against the chunks actually retrieved.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
