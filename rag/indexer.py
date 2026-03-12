"""
RAG Indexer — reads documentation files and TM1 live metadata,
generates embeddings via VoyageAI, stores in pgvector on klikk_bi_etl.

Usage:
    cd /home/mc/tm1_models/klikk_group_planning_v3/agent
    python rag/indexer.py --full        # re-index everything
    python rag/indexer.py --docs-only   # only documentation markdown files
    python rag/indexer.py --tm1-only    # only live TM1 dimension metadata
"""
from __future__ import annotations

import argparse
import json
import sys
import os
from pathlib import Path

import numpy as np
import psycopg2
import psycopg2.extras
import voyageai
from pgvector.psycopg2 import register_vector
from TM1py import TM1Service

sys.path.insert(0, str(Path(__file__).parent.parent))
from config import settings, TM1_CONFIG
from rag.chunker import Chunk, chunk_markdown, chunk_model_state, chunk_tm1_dimension

PROJECT_ROOT = Path(__file__).parent.parent.parent  # klikk_group_planning_v3/

# Directories to scan for .md files (relative to PROJECT_ROOT)
_MD_SCAN_DIRS = ["instructions", "applications"]
# Additional specific files at project root
_MD_ROOT_FILES = ["README.md"]
# Directories to exclude from recursive scanning
_MD_EXCLUDE_DIRS = {"agent", ".git", "datafiles", "backup", "logfiles", ".venv", "node_modules"}


def discover_md_files() -> list[Path]:
    """Auto-discover all .md files under PROJECT_ROOT in configured directories."""
    found: list[Path] = []
    for scan_dir in _MD_SCAN_DIRS:
        dir_path = PROJECT_ROOT / scan_dir
        if dir_path.is_dir():
            for md_file in sorted(dir_path.rglob("*.md")):
                # Skip files in excluded directories
                if not any(part in _MD_EXCLUDE_DIRS for part in md_file.parts):
                    found.append(md_file)
    for root_file in _MD_ROOT_FILES:
        path = PROJECT_ROOT / root_file
        if path.is_file():
            found.append(path)
    return sorted(set(found))


def get_pg_conn():
    conn = psycopg2.connect(
        host=settings.pg_bi_host,
        port=settings.pg_bi_port,
        dbname=settings.pg_bi_db,
        user=settings.pg_bi_user,
        password=settings.pg_bi_password,
    )
    register_vector(conn)
    return conn


def embed_chunks(
    chunks: list[Chunk], client: voyageai.Client
) -> list[tuple[Chunk, list[float]]]:
    """Batch-embed chunks. VoyageAI limit is 128 texts per call."""
    results: list[tuple[Chunk, list[float]]] = []
    batch_size = 128
    for i in range(0, len(chunks), batch_size):
        batch = chunks[i : i + batch_size]
        texts = [f"{c.title}\n\n{c.content}" for c in batch]
        response = client.embed(
            texts, model=settings.voyage_model, input_type="document"
        )
        for chunk, emb in zip(batch, response.embeddings):
            results.append((chunk, emb))
        print(f"  Embedded {min(i + batch_size, len(chunks))}/{len(chunks)} chunks")
    return results


def upsert_chunks(conn, embedded: list[tuple[Chunk, list[float]]]) -> int:
    sql = f"""
        INSERT INTO {settings.rag_schema}.documents
            (doc_id, source_path, doc_type, title, content, embedding, metadata)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (doc_id) DO UPDATE SET
            content    = EXCLUDED.content,
            embedding  = EXCLUDED.embedding,
            metadata   = EXCLUDED.metadata,
            indexed_at = NOW()
    """
    with conn.cursor() as cur:
        for chunk, emb in embedded:
            cur.execute(
                sql,
                (
                    chunk.doc_id,
                    chunk.source_path,
                    chunk.doc_type,
                    chunk.title,
                    chunk.content,
                    np.array(emb),
                    json.dumps(chunk.metadata),
                ),
            )
    conn.commit()
    return len(embedded)


def collect_doc_chunks() -> list[Chunk]:
    chunks: list[Chunk] = []
    md_files = discover_md_files()
    print(f"  Discovered {len(md_files)} markdown files")
    for doc_path in md_files:
        if not doc_path.exists():
            print(f"  SKIP (not found): {doc_path.name}")
            continue
        text = doc_path.read_text(encoding="utf-8", errors="replace")
        relative = str(doc_path.relative_to(PROJECT_ROOT))
        before = len(chunks)
        if doc_path.name == "current_model_state.md":
            chunks.extend(chunk_model_state(relative, text))
        else:
            chunks.extend(chunk_markdown(relative, text))
        added = len(chunks) - before
        print(f"  {doc_path.name}: {added} chunks")
    return chunks


# Key dimensions whose elements get full attribute values in RAG chunks
_KEY_DIMS_WITH_ATTRS = {
    "account", "entity", "cashflow_activity", "listed_share",
    "month", "version", "contact", "tracking_1", "tracking_2",
}


def collect_tm1_chunks() -> list[Chunk]:
    chunks: list[Chunk] = []
    print("  Connecting to TM1...")
    with TM1Service(**TM1_CONFIG) as tm1:
        dim_names = [
            d
            for d in tm1.dimensions.get_all_names()
            if not d.startswith("}")
        ]
        print(f"  Found {len(dim_names)} user dimensions")
        for dim_name in dim_names:
            try:
                elements = tm1.elements.get_elements(dim_name, dim_name)
                el_list = [
                    {"name": e.name, "element_type": e.element_type.value}
                    for e in elements
                ]
                attrs = [
                    a.name
                    for a in tm1.elements.get_element_attributes(dim_name, dim_name)
                ]

                # For key dimensions, also fetch attribute values and hierarchy
                attr_values = None
                hierarchy_edges = None

                if dim_name in _KEY_DIMS_WITH_ATTRS and attrs:
                    print(f"    Fetching attributes for {dim_name} ({len(el_list)} elements)...")
                    attr_values = {}
                    for el in elements:
                        el_attrs = {}
                        for attr_name in attrs:
                            try:
                                val = tm1.elements.get_attribute_value(
                                    dim_name, dim_name, el.name, attr_name,
                                )
                                if val is not None and str(val).strip():
                                    el_attrs[attr_name] = str(val)
                            except Exception:
                                pass
                        if el_attrs:
                            attr_values[el.name] = el_attrs

                # Always fetch hierarchy edges for richer structure info
                try:
                    hierarchy = tm1.hierarchies.get(dim_name, dim_name)
                    hierarchy_edges = {}
                    for el in hierarchy.elements.values():
                        if el.components:
                            hierarchy_edges[el.name] = list(el.components.keys())
                except Exception:
                    pass

                chunks.append(chunk_tm1_dimension(
                    dim_name, el_list, attrs,
                    attribute_values=attr_values,
                    hierarchy_edges=hierarchy_edges,
                ))
                print(f"  ✓ {dim_name}: {len(el_list)} elements"
                      f"{f', {len(attr_values)} with attrs' if attr_values else ''}"
                      f"{f', {len(hierarchy_edges)} consolidations' if hierarchy_edges else ''}")
            except Exception as e:
                print(f"  WARNING: could not index dimension {dim_name}: {e}")
    print(f"  TM1 dimension chunks: {len(chunks)}")
    return chunks


def run_element_indexing(dimensions: list[str] | None = None) -> None:
    """
    Per-element vectorization for specified dimensions (or all key dimensions).
    Each element gets its own document with full attribute profile + hierarchy info.
    Uses the element_context skill's index_dimension_elements function.
    """
    from mcp_server.skills.element_context import index_dimension_elements, index_all_key_dimensions

    if dimensions:
        for dim in dimensions:
            print(f"\n  Indexing elements of '{dim}'...")
            result = index_dimension_elements(dim)
            if "error" in result:
                print(f"    ERROR: {result['error']}")
            else:
                print(f"    ✓ {result.get('elements_indexed', 0)} elements indexed, "
                      f"{result.get('attributes_per_element', 0)} attributes each")
    else:
        print("\n  Indexing all key dimensions (account, entity, cashflow_activity, listed_share, month, version)...")
        result = index_all_key_dimensions()
        print(f"  ✓ {result.get('total_elements', 0)} total elements indexed across "
              f"{result.get('dimensions_indexed', 0)} dimensions")
        for dim, detail in result.get("details", {}).items():
            if detail.get("error"):
                print(f"    {dim}: ERROR — {detail['error']}")
            else:
                print(f"    {dim}: {detail.get('elements_indexed', 0)} elements")


def main() -> None:
    parser = argparse.ArgumentParser(description="Index documents into pgvector RAG store")
    parser.add_argument("--full", action="store_true", help="Re-index everything (docs + TM1 dims + elements)")
    parser.add_argument("--docs-only", action="store_true", help="Only index documentation files")
    parser.add_argument("--tm1-only", action="store_true", help="Only index TM1 dimension-level metadata")
    parser.add_argument("--elements", action="store_true",
                        help="Index per-element profiles for key dimensions (account, entity, etc.)")
    parser.add_argument("--element-dims", nargs="*", metavar="DIM",
                        help="Index per-element profiles for specific dimension(s)")
    args = parser.parse_args()

    if not settings.voyage_api_key:
        print("ERROR: VOYAGE_API_KEY not set in .env")
        sys.exit(1)

    # Per-element indexing mode
    if args.elements or args.element_dims:
        print("\n=== Per-Element Vectorization ===")
        run_element_indexing(args.element_dims or None)
        if not args.full:
            return

    voyage_client = voyageai.Client(api_key=settings.voyage_api_key)
    conn = get_pg_conn()

    chunks: list[Chunk] = []

    if not args.tm1_only:
        print("\nCollecting documentation chunks...")
        chunks.extend(collect_doc_chunks())

    if not args.docs_only:
        print("\nCollecting TM1 metadata chunks...")
        chunks.extend(collect_tm1_chunks())

    if not chunks:
        print("No chunks collected. Exiting.")
        return

    print(f"\nTotal chunks to embed: {len(chunks)}")
    print("Embedding via VoyageAI...")
    embedded = embed_chunks(chunks, voyage_client)

    print("\nUpserting into pgvector...")
    count = upsert_chunks(conn, embedded)
    conn.close()
    print(f"\nDone. {count} chunks indexed into {settings.rag_schema}.documents")

    # If --full, also run per-element indexing
    if args.full:
        print("\n=== Per-Element Vectorization (key dimensions) ===")
        run_element_indexing(None)


if __name__ == "__main__":
    main()
