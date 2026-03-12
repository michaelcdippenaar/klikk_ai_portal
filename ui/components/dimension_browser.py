"""
Dimension Browser component.
Interactive panel for browsing TM1 dimensions, elements, and attributes.
Calls TM1 tool functions directly (not through the agent loop) for instant responses.
"""
from __future__ import annotations

import streamlit as st

from mcp_server.skills.tm1_metadata import (
    tm1_list_dimensions,
    tm1_get_dimension_elements,
    tm1_get_element_attributes,
    tm1_get_element_attribute_value,
    tm1_get_hierarchy,
)


# ---------------------------------------------------------------------------
#  Cached wrappers for TM1 calls (5-minute TTL)
# ---------------------------------------------------------------------------

@st.cache_data(ttl=300, show_spinner=False)
def _cached_list_dimensions():
    return tm1_list_dimensions()


@st.cache_data(ttl=300, show_spinner=False)
def _cached_get_elements(dim_name: str, el_type: str, limit: int):
    return tm1_get_dimension_elements(dim_name, element_type=el_type, limit=limit)


@st.cache_data(ttl=300, show_spinner=False)
def _cached_get_attributes(dim_name: str):
    return tm1_get_element_attributes(dim_name)


@st.cache_data(ttl=300, show_spinner=False)
def _cached_get_attribute_value(dim_name: str, element_name: str, attr_name: str):
    return tm1_get_element_attribute_value(dim_name, element_name, attr_name)


@st.cache_data(ttl=300, show_spinner=False)
def _cached_get_hierarchy(dim_name: str):
    return tm1_get_hierarchy(dim_name)


# ---------------------------------------------------------------------------
#  Main render function
# ---------------------------------------------------------------------------

def render_dimension_browser():
    """Render the interactive dimension browser panel."""
    st.markdown("### Dimension Browser")

    # 1. Dimension selector
    dims_result = _cached_list_dimensions()
    if "error" in dims_result:
        st.error(f"Cannot load dimensions: {dims_result['error']}")
        return

    dim_names = dims_result["dimensions"]
    selected_dim = st.selectbox(
        "Dimension",
        dim_names,
        index=dim_names.index(st.session_state.get("selected_dimension", dim_names[0]))
            if st.session_state.get("selected_dimension") in dim_names else 0,
        key="dim_browser_select",
    )
    st.session_state.selected_dimension = selected_dim

    if not selected_dim:
        return

    # 2. Element type filter + search
    col_type, col_search = st.columns([1, 2])
    with col_type:
        el_type = st.selectbox(
            "Type",
            ["all", "leaf", "consolidated"],
            key="dim_browser_type",
        )
    with col_search:
        search = st.text_input(
            "Filter",
            key="dim_browser_search",
            placeholder="Type to filter...",
        )

    # 3. Load elements
    with st.spinner("Loading elements..."):
        elements_result = _cached_get_elements(selected_dim, el_type, 500)

    if "error" in elements_result:
        st.error(elements_result["error"])
        return

    elements = elements_result["elements"]

    # Apply search filter
    if search:
        search_lower = search.lower()
        elements = [e for e in elements if search_lower in e["name"].lower()]

    total = elements_result.get("total", len(elements))
    shown = len(elements)
    truncated = elements_result.get("truncated", False)

    st.caption(
        f"Showing {min(shown, 100)} of {total} elements"
        + (" (filtered)" if search else "")
        + (" — limit reached" if truncated else "")
    )

    # 4. Get attribute names for this dimension
    attrs_result = _cached_get_attributes(selected_dim)
    attr_names = []
    if "error" not in attrs_result:
        attr_names = [a["name"] for a in attrs_result.get("attributes", [])]

    # 5. Render element list (capped at 100 for performance)
    for el in elements[:100]:
        el_name = el["name"]
        el_type_short = el["element_type"][:1]  # N, C, or S
        type_icon = {"N": "", "C": "", "S": ""}.get(el_type_short, "")

        with st.expander(f"{type_icon} {el_name}  `{el_type_short}`", expanded=False):
            # Show attributes
            if attr_names:
                # Display attributes in a compact grid
                attr_cols = st.columns(min(len(attr_names), 3))
                for i, attr in enumerate(attr_names[:9]):  # Max 9 attributes shown
                    val_result = _cached_get_attribute_value(selected_dim, el_name, attr)
                    val = val_result.get("value", "") if "error" not in val_result else "—"
                    if val is None:
                        val = ""
                    with attr_cols[i % len(attr_cols)]:
                        st.markdown(f"**{attr}:** {val}")

            # "Use in chat" button
            if st.button(f"Use in chat", key=f"use_{selected_dim}_{el_name}"):
                if "selected_elements" not in st.session_state:
                    st.session_state.selected_elements = []
                st.session_state.selected_elements.append({
                    "dimension": selected_dim,
                    "element": el_name,
                })
                st.toast(f"Added {selected_dim}:{el_name} to context")

    # 6. Hierarchy tree (optional)
    if st.checkbox("Show hierarchy", key="dim_browser_show_hier"):
        _render_hierarchy(selected_dim)


# ---------------------------------------------------------------------------
#  Hierarchy tree renderer
# ---------------------------------------------------------------------------

def _render_hierarchy(dim_name: str):
    """Render a collapsible hierarchy tree for the dimension."""
    with st.spinner("Loading hierarchy..."):
        hier_result = _cached_get_hierarchy(dim_name)

    if "error" in hier_result:
        st.error(hier_result["error"])
        return

    edges = hier_result.get("edges", [])
    if not edges:
        st.info("No hierarchy edges found.")
        return

    # Build parent -> children dict
    tree: dict[str, list[str]] = {}
    for edge in edges:
        tree.setdefault(edge["parent"], []).append(edge["child"])

    # Find roots (parents not appearing as anyone's child)
    all_children_set = {e["child"] for e in edges}
    roots = [p for p in tree if p not in all_children_set]

    if not roots:
        st.warning("No root consolidations found.")
        return

    st.caption(f"Hierarchy roots: {len(roots)}")
    for root in roots[:10]:
        _render_tree_node(root, tree, depth=0)


def _render_tree_node(node: str, tree: dict, depth: int):
    """Recursively render a hierarchy tree node with indentation."""
    indent = "&nbsp;&nbsp;&nbsp;&nbsp;" * depth
    children = tree.get(node, [])
    if children:
        st.markdown(f"{indent}**{node}** ({len(children)})", unsafe_allow_html=True)
        if depth < 3:  # Limit depth to prevent overwhelming display
            for child in children[:25]:
                _render_tree_node(child, tree, depth + 1)
            if len(children) > 25:
                deeper_indent = "&nbsp;&nbsp;&nbsp;&nbsp;" * (depth + 1)
                st.markdown(f"{deeper_indent}*... and {len(children) - 25} more*", unsafe_allow_html=True)
    else:
        st.markdown(f"{indent}{node}", unsafe_allow_html=True)
