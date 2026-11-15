"""
Vector DB Viewer & Explorer for ChromaDB.

Run via:
  python backend/rag/view_vector_db.py
"""

from __future__ import annotations

import sys
from pathlib import Path

# Path to the local ChromaDB persistent folder
CHROMA_DIR = Path(__file__).resolve().parent / "data" / "chroma_db"
COLLECTION_NAME = "orthosync_clinical_knowledge"


def view_chroma():
    print("=" * 70)
    print("CHROMADB VECTOR STORE VIEWER")
    print(f"Database Directory: {CHROMA_DIR}")
    print("=" * 70)

    if not CHROMA_DIR.exists():
        print(f"[!] ChromaDB directory does not exist at: {CHROMA_DIR}")
        return

    try:
        import chromadb
    except ImportError:
        print("[!] chromadb is not installed in your Python environment.")
        print("Install it with: pip install chromadb")
        return

    client = chromadb.PersistentClient(path=str(CHROMA_DIR))
    
    # List collections
    collections = client.list_collections()
    col_names = [c.name for c in collections]
    print(f"Collections Found: {col_names}\n")

    if COLLECTION_NAME not in col_names:
        print(f"[!] Collection '{COLLECTION_NAME}' not found.")
        return

    collection = client.get_collection(name=COLLECTION_NAME)
    total_count = collection.count()
    print(f"Collection: '{COLLECTION_NAME}'")
    print(f"Total Vector Embeddings: {total_count}")
    print("-" * 70)

    # Fetch all documents, metadatas, and IDs
    results = collection.get(include=["metadatas", "documents"])

    ids = results.get("ids", [])
    docs = results.get("documents", [])
    metas = results.get("metadatas", [])

    for i, (doc_id, doc_content, meta) in enumerate(zip(ids, docs, metas), 1):
        print(f"[{i:02d}] ID: {doc_id}")
        if meta:
            print(f"     Procedure:   {meta.get('procedure', 'N/A')}")
            print(f"     Topic:       {meta.get('topic', 'N/A')}")
            print(f"     Category:    {meta.get('category', 'N/A')}")
            print(f"     Post-Op Days:{meta.get('days', 'N/A')}")
            if "keywords" in meta:
                print(f"     Keywords:    {meta.get('keywords')}")
        print(f"     Document Content:\n     \"{doc_content.strip()}\"")
        print("-" * 70)


if __name__ == "__main__":
    view_chroma()
