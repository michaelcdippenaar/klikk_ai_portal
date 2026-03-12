"""
Document chunking strategies for RAG indexing.

Rules per document type:
- Markdown instructions: split on ## headings (~800 tokens max per chunk)
- current_model_state.md: one chunk per TM1 object (dim/cube/process section)
- TM1 dimension (from live API): one chunk per dimension
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Generator


@dataclass
class Chunk:
    doc_id: str
    source_path: str
    doc_type: str       # instruction | model_state | dimension_structure
    title: str
    content: str
    metadata: dict = field(default_factory=dict)


def chunk_markdown(relative_path: str, text: str) -> Generator[Chunk, None, None]:
    """
    Split a markdown file on ## headings.
    Each ## section becomes one chunk, truncated to 3000 chars.
    """
    sections = re.split(r'\n(?=## )', text)
    for i, section in enumerate(sections):
        section = section.strip()
        if not section:
            continue
        first_line = section.split('\n')[0].lstrip('#').strip()
        title = first_line or f"Section {i}"
        content = section[:3000]
        doc_id = f"{relative_path}#s{i}_{_slugify(title)}"
        yield Chunk(
            doc_id=doc_id,
            source_path=relative_path,
            doc_type="instruction",
            title=title,
            content=content,
            metadata={"section_index": i, "file": relative_path},
        )


def chunk_model_state(relative_path: str, text: str) -> Generator[Chunk, None, None]:
    """
    Split current_model_state.md per TM1 object.
    Sections are ### <name> blocks under ## Dimensions, ## Cubes, ## Processes.
    """
    section_type = "model_state"
    current_name = ""
    current_lines: list[str] = []

    for line in text.split('\n'):
        if line.startswith('## Dimension'):
            section_type = 'dimension_structure'
        elif line.startswith('## Cube'):
            section_type = 'cube_rule'
        elif line.startswith('## Process'):
            section_type = 'process_code'
        elif line.startswith('### '):
            if current_lines and current_name:
                yield _flush_chunk(relative_path, section_type, current_name, current_lines)
            current_name = line.lstrip('#').strip()
            current_lines = [line]
        else:
            current_lines.append(line)

    if current_lines and current_name:
        yield _flush_chunk(relative_path, section_type, current_name, current_lines)


def _flush_chunk(path: str, doc_type: str, name: str, lines: list[str]) -> Chunk:
    content = '\n'.join(lines).strip()[:3000]
    return Chunk(
        doc_id=f"model_state::{doc_type}::{name}",
        source_path=path,
        doc_type=doc_type,
        title=name,
        content=content,
        metadata={"object_name": name, "object_type": doc_type},
    )


def chunk_tm1_dimension(
    dim_name: str,
    elements: list[dict],
    attributes: list[str],
    attribute_values: dict[str, dict[str, str]] | None = None,
    hierarchy_edges: dict[str, list[str]] | None = None,
) -> Chunk:
    """
    Create a single chunk summarising a TM1 dimension's structure.

    Args:
        dim_name: Dimension name.
        elements: List of {"name": ..., "element_type": ...} dicts.
        attributes: List of attribute names.
        attribute_values: Optional dict of {element_name: {attr_name: value}}.
        hierarchy_edges: Optional dict of {parent: [child, ...]} consolidation edges.
    """
    leaf_els = [e for e in elements if e.get("element_type") == "Numeric"]
    consol_els = [e for e in elements if e.get("element_type") == "Consolidated"]
    string_els = [e for e in elements if e.get("element_type") == "String"]
    lines = [
        f"Dimension: {dim_name}",
        f"Total elements: {len(elements)}  ({len(leaf_els)} Numeric, {len(consol_els)} Consolidated, {len(string_els)} String)",
        f"Attributes: {', '.join(attributes) if attributes else 'none'}",
    ]

    # Hierarchy summary — show top-level consolidations and their children
    if hierarchy_edges:
        # Find root consolidations (parents that aren't children of anyone)
        all_children = set()
        for children in hierarchy_edges.values():
            all_children.update(children)
        roots = [p for p in hierarchy_edges if p not in all_children]
        if roots:
            lines.append(f"\nHierarchy roots: {', '.join(roots[:10])}")
            for root in roots[:5]:
                children = hierarchy_edges.get(root, [])
                if children:
                    lines.append(f"  {root} -> {', '.join(children[:15])}")
                    if len(children) > 15:
                        lines.append(f"    ... and {len(children) - 15} more children")

    # Element listing with attribute values for richer context
    if attribute_values and leaf_els:
        lines.append(f"\nLeaf elements with attributes (first 40):")
        for el in leaf_els[:40]:
            el_name = el["name"]
            attrs = attribute_values.get(el_name, {})
            if attrs:
                attr_strs = [f"{k}={v}" for k, v in attrs.items() if v and str(v).strip()]
                if attr_strs:
                    lines.append(f"  {el_name}: {'; '.join(attr_strs[:6])}")
                else:
                    lines.append(f"  {el_name}")
            else:
                lines.append(f"  {el_name}")
        if len(leaf_els) > 40:
            lines.append(f"  ... and {len(leaf_els) - 40} more")
    else:
        lines.append("Sample leaf elements (first 30):")
        for el in leaf_els[:30]:
            lines.append(f"  {el['name']}")
        if len(leaf_els) > 30:
            lines.append(f"  ... and {len(leaf_els) - 30} more")

    # Also list consolidations
    if consol_els:
        lines.append(f"\nConsolidated elements ({len(consol_els)}):")
        for el in consol_els[:20]:
            child_count = len(hierarchy_edges.get(el["name"], [])) if hierarchy_edges else 0
            if child_count:
                lines.append(f"  {el['name']} ({child_count} children)")
            else:
                lines.append(f"  {el['name']}")
        if len(consol_els) > 20:
            lines.append(f"  ... and {len(consol_els) - 20} more")

    content = '\n'.join(lines)
    # Truncate to stay within embedding limits (but allow more than before)
    content = content[:4000]

    return Chunk(
        doc_id=f"tm1_api::dimension::{dim_name}",
        source_path=f"tm1_api::dimension::{dim_name}",
        doc_type="dimension_structure",
        title=f"Dimension: {dim_name}",
        content=content,
        metadata={
            "dim_name": dim_name,
            "total_count": len(elements),
            "leaf_count": len(leaf_els),
            "consol_count": len(consol_els),
            "string_count": len(string_els),
            "attributes": attributes,
        },
    )


def chunk_plain_text(
    source_path: str,
    text: str,
    chunk_size: int = 2500,
) -> Generator[Chunk, None, None]:
    """
    Chunk plain text by paragraph boundaries.
    Used for Google Drive documents, PDFs, and other non-markdown files.
    """
    paragraphs = re.split(r'\n{2,}', text)
    current_chunk: list[str] = []
    current_len = 0
    chunk_idx = 0

    for para in paragraphs:
        para = para.strip()
        if not para:
            continue
        if current_len + len(para) > chunk_size and current_chunk:
            content = "\n\n".join(current_chunk)
            # Use first line as title (truncated)
            title = current_chunk[0][:80] if current_chunk else f"Chunk {chunk_idx}"
            yield Chunk(
                doc_id=f"{source_path}#p{chunk_idx}",
                source_path=source_path,
                doc_type="plain_text",
                title=title,
                content=content[:3000],
                metadata={"chunk_index": chunk_idx, "source": source_path},
            )
            chunk_idx += 1
            current_chunk = []
            current_len = 0
        current_chunk.append(para)
        current_len += len(para)

    # Flush remaining
    if current_chunk:
        content = "\n\n".join(current_chunk)
        title = current_chunk[0][:80] if current_chunk else f"Chunk {chunk_idx}"
        yield Chunk(
            doc_id=f"{source_path}#p{chunk_idx}",
            source_path=source_path,
            doc_type="plain_text",
            title=title,
            content=content[:3000],
            metadata={"chunk_index": chunk_idx, "source": source_path},
        )


def _slugify(text: str) -> str:
    return re.sub(r'[^a-z0-9_]', '_', text.lower())[:40]
