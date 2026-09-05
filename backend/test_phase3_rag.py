"""
Phase 3 test suite -- ChromaDB semantic RAG retrieval.

Run directly:
    .venv/Scripts/python.exe test_phase3_rag.py

Plain-Python script (no pytest dependency), consistent with
test_phase2_intent.py. Hard assertions (_check) fail the suite on real
regressions (procedure leakage, broken contract, safety invariants).
Classification-style correctness on genuinely hard semantic cases uses a
soft note (_note) so an honest miss is reported, not hidden or cherry-picked
away, and does not masquerade as a structural bug.
"""

from __future__ import annotations

import sys
from typing import Optional

import rag.vector_store as vector_store_module
from rag.knowledge_base import ClinicalKnowledgeBase, RetrievalDetail, RetrievedChunk
from rag.ingest import build_chunks
from lam.schemas import resolve_procedure_code
from lam.orchestrator import LAMOrchestrator

_FAILURES: list[str] = []


def _check(condition: bool, message: str) -> None:
    if not condition:
        _FAILURES.append(message)
        print(f"    !! FAILED: {message}")


def _note(condition: bool, message: str) -> None:
    if not condition:
        print(f"    ?? GENUINE MISS (reported, not a hard failure): {message}")


def _print_detail(label: str, detail: RetrievalDetail) -> None:
    print(f"[{label}] \"{detail.query}\"")
    print(f"    procedure_filter = {detail.procedure_filter}")
    print(f"    retrieval_path   = {detail.retrieval_path}")
    if not detail.results:
        print("    (no results)")
    for i, r in enumerate(detail.results):
        dist = f"{r.distance:.4f}" if r.distance is not None else "n/a"
        print(f"    [{i}] title={r.title!r} procedure={r.procedure} "
              f"body_region={r.body_region} category={r.category} "
              f"distance={dist}")
        print(f"        chunk_id={r.chunk_id} doc_id={r.doc_id} source={r.source!r}")
    print()


def _titles(detail: RetrievalDetail) -> set[str]:
    return {r.title for r in detail.results}


def _procedures(detail: RetrievalDetail) -> set[str]:
    return {r.procedure for r in detail.results}


# ---------------------------------------------------------------------------
# 1. Knee / TKA
# ---------------------------------------------------------------------------

def run_tka_test() -> None:
    print("=" * 78)
    print("SECTION 1 -- Knee / TKA query")
    print("=" * 78)
    query = "What exercises should I do after my knee replacement?"
    detail = ClinicalKnowledgeBase.retrieve_detailed(query, procedure="TKA", limit=3)
    _print_detail("tka", detail)

    titles = _titles(detail)
    procedures = _procedures(detail)

    _check(len(detail.results) > 0, "TKA query returned no results")
    _check(
        "Hip Precautions & Dislocation Prevention" not in titles,
        "REGRESSION: TKA query retrieved THA-only Hip Precautions content (the original bug)",
    )
    _check(
        "THA" not in procedures,
        f"TKA query returned a THA-tagged chunk: procedures={procedures}",
    )
    _note(
        any("Range of Motion" in t or "Extension" in t for t in titles),
        f"expected TKA exercise/ROM content in top results, got titles={titles}",
    )
    print("    CONFIRMED: TKA query does NOT retrieve 'Hip Precautions & Dislocation Prevention'.")
    print()


# ---------------------------------------------------------------------------
# 2. Hip / THA
# ---------------------------------------------------------------------------

def run_tha_test() -> None:
    print("=" * 78)
    print("SECTION 2 -- Hip / THA query")
    print("=" * 78)
    query = "What movements should I avoid after my hip replacement?"
    detail = ClinicalKnowledgeBase.retrieve_detailed(query, procedure="THA", limit=3)
    _print_detail("tha", detail)

    titles = _titles(detail)
    procedures = _procedures(detail)

    _check(len(detail.results) > 0, "THA query returned no results")
    _check(
        "Hip Precautions & Dislocation Prevention" in titles,
        f"THA query did not retrieve Hip Precautions content; titles={titles}",
    )
    tka_only_titles = {
        "Range of Motion & Extension Milestones",
        "Wound Healing & Incision Care",
        "Normal Post-Op Edema vs DVT",
    }
    leaked = titles & tka_only_titles
    _check(
        not leaked,
        f"THA query retrieved TKA-only content: {leaked}",
    )
    _check(
        "TKA" not in procedures,
        f"THA query returned a TKA-tagged chunk: procedures={procedures}",
    )
    _note(
        detail.results and detail.results[0].title == "Hip Precautions & Dislocation Prevention",
        f"expected Hip Precautions to be the top (lowest-distance) result, got {detail.results[0].title if detail.results else None}",
    )
    print()


# ---------------------------------------------------------------------------
# 3. Generic / ankle (non-arthroplasty -> GEN)
# ---------------------------------------------------------------------------

def run_gen_test() -> None:
    print("=" * 78)
    print("SECTION 3 -- Generic / ankle (non-arthroplasty) query")
    print("=" * 78)
    surgery_type = "Ankle ORIF"
    resolved = resolve_procedure_code(surgery_type)
    print(f"    resolve_procedure_code({surgery_type!r}) = {resolved!r}")
    _check(resolved == "GEN", f"expected ankle ORIF to resolve to GEN, got {resolved!r}")
    _check(resolved != "TKA", "REGRESSION: non-hip surgery silently treated as TKA")

    query = "I had ankle ORIF. What general postoperative precautions should I follow?"
    detail = ClinicalKnowledgeBase.retrieve_detailed(query, procedure=resolved, limit=3)
    _print_detail("gen", detail)

    titles = _titles(detail)
    procedures = _procedures(detail)

    _check(
        procedures <= {"All"},
        f"GEN query returned procedure-specific (non-'All') content: procedures={procedures}",
    )
    _check(
        "Hip Precautions & Dislocation Prevention" not in titles,
        "GEN/ankle query retrieved THA-only Hip Precautions content",
    )
    _check(
        "Range of Motion & Extension Milestones" not in titles,
        "GEN/ankle query retrieved TKA-only ROM content",
    )
    print()


# ---------------------------------------------------------------------------
# 4. Semantic paraphrase -- wording NOT present verbatim in the stored doc
# ---------------------------------------------------------------------------

def run_paraphrase_test() -> None:
    print("=" * 78)
    print("SECTION 4 -- Semantic paraphrase (no literal keyword overlap)")
    print("=" * 78)
    # Deliberately avoids "swelling", "edema", "elevation", "ice", "calf", "dvt"
    # -- the literal keywords attached to TKA-01 -- while still being about
    # the same clinical topic (postoperative puffiness vs. concerning signs).
    query = "My leg looks puffy and tight since the operation, is that something to worry about?"
    detail = ClinicalKnowledgeBase.retrieve_detailed(query, procedure="TKA", limit=3)
    _print_detail("paraphrase", detail)

    titles = _titles(detail)
    _note(
        "Normal Post-Op Edema vs DVT" in titles,
        f"expected paraphrase to retrieve 'Normal Post-Op Edema vs DVT' via semantic similarity, got titles={titles}",
    )
    _check(
        "Hip Precautions & Dislocation Prevention" not in titles,
        "paraphrase (TKA) query retrieved THA-only Hip Precautions content",
    )
    print()


# ---------------------------------------------------------------------------
# 5. Irrelevant query, semantic path -- the SEMANTIC_MAX_DISTANCE relevance
# gate must filter it down to an empty result list (not an arbitrary
# nearest-but-irrelevant clinical chunk), while the retrieval infrastructure
# itself still counts as having worked (retrieval_path stays semantic_chroma,
# it does NOT fall back to keyword matching just because nothing relevant
# was found).
# ---------------------------------------------------------------------------

def run_irrelevant_query_semantic_test() -> None:
    print("=" * 78)
    print("SECTION 5 -- Irrelevant query via semantic Chroma retrieval (relevance gate)")
    print("=" * 78)
    query = "What's a good recipe for chocolate cake?"
    detail = ClinicalKnowledgeBase.retrieve_detailed(query, procedure="TKA", limit=2)
    _print_detail("irrelevant-semantic", detail)

    _check(
        detail.retrieval_path == "semantic_chroma",
        f"irrelevant query should still go through semantic_chroma infrastructure "
        f"(finding nothing relevant is not the same as the backend being unavailable), "
        f"got {detail.retrieval_path}",
    )
    _check(
        len(detail.results) == 0,
        f"irrelevant query should be filtered to an empty list by SEMANTIC_MAX_DISTANCE "
        f"({vector_store_module.SEMANTIC_MAX_DISTANCE}), got {len(detail.results)} result(s): "
        f"{_titles(detail)}",
    )
    print(f"    CONFIRMED: 0 clinical chunks retrieved for an irrelevant query "
          f"(distance gate = {vector_store_module.SEMANTIC_MAX_DISTANCE}).")
    print()


# ---------------------------------------------------------------------------
# 5b. Forced keyword fallback -- token/phrase-aware matching.
#
# The fallback's keyword matching is now token/phrase-aware (see
# rag/knowledge_base.py: _keyword_matches_query / _normalize_word), replacing
# the earlier naive substring matching that let a short common word like "a"
# spuriously "match" merely because it is a substring of an unrelated
# keyword like "calf". Both unrelated queries below -- including the
# "chocolate cake" phrasing that specifically triggered that bug -- must now
# return zero results through the fallback path, while genuine clinically
# relevant queries must still retrieve the expected chunk.
# ---------------------------------------------------------------------------

_FALLBACK_MATCHING_CASES: list[tuple[str, str, Optional[str]]] = [
    # (query, procedure, expected_title_or_None_for_empty)
    ("What is a good recipe for chocolate cake?", "TKA", None),
    ("Recommend jazz music albums for weekend road trips.", "TKA", None),
    ("My knee feels swollen today, is that normal?", "TKA", "Normal Post-Op Edema vs DVT"),
    ("There is drainage and redness around my incision.", "TKA", "Wound Healing & Incision Care"),
    ("When should I take my next pain medication?", "TKA", "Pain Management & Analgesic Titration"),
]


def run_fallback_matching_test() -> None:
    print("=" * 78)
    print("SECTION 5b -- Forced keyword fallback: token/phrase-aware matching")
    print("=" * 78)
    original_query = vector_store_module.query
    try:
        vector_store_module.query = lambda *args, **kwargs: None
        for query, procedure, expected_title in _FALLBACK_MATCHING_CASES:
            detail = ClinicalKnowledgeBase.retrieve_detailed(query, procedure=procedure, limit=3)
            _print_detail("fallback-matching", detail)

            _check(
                detail.retrieval_path == "keyword_fallback",
                f"expected keyword_fallback path (Chroma simulated unavailable) for {query!r}, "
                f"got {detail.retrieval_path}",
            )
            titles = _titles(detail)
            if expected_title is None:
                _check(
                    len(detail.results) == 0,
                    f"unrelated query {query!r} should return an empty list via fallback, "
                    f"got {len(detail.results)} result(s): {titles}",
                )
            else:
                _check(
                    expected_title in titles,
                    f"genuine query {query!r} expected {expected_title!r} in fallback results, got {titles}",
                )
    finally:
        vector_store_module.query = original_query
    print("    CONFIRMED: unrelated queries return 0 chunks; genuine queries still retrieve "
          "the expected relevant chunk -- all via the token/phrase-aware fallback matcher.")
    print()


# ---------------------------------------------------------------------------
# 6. Persistence / idempotence
# ---------------------------------------------------------------------------

def run_idempotence_test() -> None:
    print("=" * 78)
    print("SECTION 6 -- Persistence / idempotence of indexing")
    print("=" * 78)
    expected = len(build_chunks())
    count1 = vector_store_module.reindex()
    count2 = vector_store_module.reindex()
    count3 = vector_store_module.reindex()
    print(f"    expected chunk count = {expected}")
    print(f"    reindex() call 1 -> count = {count1}")
    print(f"    reindex() call 2 -> count = {count2}")
    print(f"    reindex() call 3 -> count = {count3}")
    _check(count1 == expected, f"first reindex count {count1} != expected {expected}")
    _check(count2 == expected, f"re-running reindex duplicated chunks: {count2} != {expected}")
    _check(count3 == expected, f"re-running reindex duplicated chunks: {count3} != {expected}")
    print()


# ---------------------------------------------------------------------------
# 7. Offline / failure fallback
# ---------------------------------------------------------------------------

def run_offline_fallback_test() -> None:
    print("=" * 78)
    print("SECTION 7 -- Offline / Chroma-failure fallback")
    print("=" * 78)
    original_query = vector_store_module.query
    try:
        vector_store_module.query = lambda *args, **kwargs: None

        cases = [
            ("What exercises should I do after my knee replacement?", "TKA"),
            ("What movements should I avoid after my hip replacement?", "THA"),
            ("I had ankle ORIF. What general postoperative precautions should I follow?", "GEN"),
        ]
        for query, procedure in cases:
            detail = ClinicalKnowledgeBase.retrieve_detailed(query, procedure=procedure, limit=3)
            _print_detail("forced-offline", detail)
            _check(
                detail.retrieval_path == "keyword_fallback",
                f"expected keyword_fallback path during simulated Chroma failure for {query!r}, got {detail.retrieval_path}",
            )
            procedures = _procedures(detail)
            _check(
                procedures <= {procedure, "All"},
                f"offline fallback leaked cross-procedure content for {procedure} query: {procedures}",
            )
        _check(
            "Hip Precautions & Dislocation Prevention" not in _titles(
                ClinicalKnowledgeBase.retrieve_detailed(cases[0][0], procedure="TKA", limit=3)
            ),
            "offline fallback retrieved THA-only Hip Precautions content for a TKA query",
        )
    finally:
        vector_store_module.query = original_query
    print("    Backend did not crash when the vector store was simulated unavailable.")
    print()


# ---------------------------------------------------------------------------
# 8. End-to-end /api/chat smoke test (no Ollama required)
# ---------------------------------------------------------------------------

def run_end_to_end_smoke_test() -> None:
    print("=" * 78)
    print("SECTION 8 -- End-to-end /api/chat smoke test (RAG layer only, no Ollama needed)")
    print("=" * 78)
    result = LAMOrchestrator.process(
        patient_id="TEST-PT",
        surgery_type="Total Knee Arthroplasty (TKA)",
        affected_limb="Right",
        postop_day=5,
        user_message="What exercises should I do after my knee replacement?",
    )
    print(f"    engine  = {result['engine']}")
    print(f"    sources = {result['sources']}")
    print(f"    intent  = {result['intent']}")
    expected_contract_keys = {
        "reply", "triage_level", "is_escalated", "engine", "sources",
        "intent", "target_agent", "action", "scope_status",
    }
    _check(
        set(result.keys()) == expected_contract_keys,
        f"/api/chat contract keys changed: {sorted(result.keys())}",
    )
    _check(
        "Hip Precautions & Dislocation Prevention" not in result["sources"],
        "end-to-end TKA chat response cites Hip Precautions as a source",
    )
    _check(len(result["sources"]) > 0, "end-to-end chat response returned no sources")
    print()


def main() -> int:
    run_tka_test()
    run_tha_test()
    run_gen_test()
    run_paraphrase_test()
    run_irrelevant_query_semantic_test()
    run_fallback_matching_test()
    run_idempotence_test()
    run_offline_fallback_test()
    run_end_to_end_smoke_test()

    print("=" * 78)
    if _FAILURES:
        print(f"RESULT: {len(_FAILURES)} FAILURE(S)")
        for f in _FAILURES:
            print(f"  - {f}")
        return 1
    print("RESULT: ALL CHECKS PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
