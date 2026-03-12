"""
Cube Viewer component.
Interactive panel for browsing TM1 cube data with dimension slicers.
Calls TM1 tool functions directly (not through the agent loop) for instant responses.
"""
from __future__ import annotations

import streamlit as st
import pandas as pd

from mcp_server.skills.tm1_metadata import (
    tm1_list_cubes,
    tm1_get_dimension_elements,
)
from mcp_server.skills.tm1_query import tm1_execute_mdx_rows


# ---------------------------------------------------------------------------
#  Cached wrappers for TM1 calls (5-minute TTL)
# ---------------------------------------------------------------------------

@st.cache_data(ttl=300, show_spinner=False)
def _cached_list_cubes():
    return tm1_list_cubes()


@st.cache_data(ttl=300, show_spinner=False)
def _cached_get_elements(dim_name: str, el_type: str, limit: int):
    return tm1_get_dimension_elements(dim_name, element_type=el_type, limit=limit)


# ---------------------------------------------------------------------------
#  Main render function
# ---------------------------------------------------------------------------

def render_cube_viewer():
    """Render the interactive cube data viewer panel."""
    st.markdown("### Cube Viewer")

    # 1. Cube selector
    cubes_result = _cached_list_cubes()
    if "error" in cubes_result:
        st.error(f"Cannot load cubes: {cubes_result['error']}")
        return

    cube_list = cubes_result["cubes"]
    cube_names = [c["name"] for c in cube_list]

    selected_cube = st.selectbox(
        "Cube",
        cube_names,
        key="cube_viewer_select",
    )

    if not selected_cube:
        return

    # Find cube dimensions
    cube_info = next(c for c in cube_list if c["name"] == selected_cube)
    dims = cube_info["dimensions"]
    has_rules = cube_info.get("has_rules", False)

    st.caption(
        f"Dims: {len(dims)} · "
        f"{'Has rules' if has_rules else 'No rules'}"
    )

    # 2. Pick Row and Column dimensions
    st.markdown("**Layout**")
    col_row, col_col = st.columns(2)
    with col_row:
        # Default row dim: second-to-last dimension
        default_row = max(0, len(dims) - 2)
        row_dim = st.selectbox(
            "Rows",
            dims,
            index=default_row,
            key=f"cv_row_{selected_cube}",
        )
    with col_col:
        # Default col dim: last dimension (usually the measure)
        col_dim = st.selectbox(
            "Columns",
            dims,
            index=len(dims) - 1,
            key=f"cv_col_{selected_cube}",
        )

    # 3. Slicer elements for all other dimensions
    slicer_dims = [d for d in dims if d not in (row_dim, col_dim)]

    if slicer_dims:
        st.markdown("**Slicer elements**")
        slicer_values: dict[str, str] = {}

        # Compact layout: 3 columns
        slicer_cols = st.columns(min(len(slicer_dims), 3))
        for i, dim in enumerate(slicer_dims):
            with slicer_cols[i % len(slicer_cols)]:
                els_result = _cached_get_elements(dim, "all", 200)
                if "error" in els_result:
                    slicer_values[dim] = ""
                    st.text_input(dim, value="", key=f"cv_sl_{selected_cube}_{dim}")
                    continue

                el_names = [e["name"] for e in els_result["elements"]]

                # Default: first consolidated element, else first element
                default_idx = 0
                for j, e in enumerate(els_result["elements"]):
                    if e["element_type"] == "Consolidated":
                        default_idx = j
                        break

                selected_el = st.selectbox(
                    dim,
                    el_names,
                    index=min(default_idx, len(el_names) - 1),
                    key=f"cv_sl_{selected_cube}_{dim}",
                )
                slicer_values[dim] = selected_el
    else:
        slicer_values = {}

    # 4. Row/Column member selection
    st.markdown("**Member selection**")
    mc_row, mc_col = st.columns(2)

    with mc_row:
        row_els = _cached_get_elements(row_dim, "all", 200)
        row_el_names = [e["name"] for e in row_els.get("elements", [])] if "error" not in row_els else []
        # Default: first consolidated
        row_default = 0
        for j, e in enumerate(row_els.get("elements", [])):
            if e["element_type"] == "Consolidated":
                row_default = j
                break
        row_parent = st.selectbox(
            f"Expand ({row_dim})",
            row_el_names,
            index=min(row_default, max(0, len(row_el_names) - 1)),
            key=f"cv_rowp_{selected_cube}",
            help="Children of this element will appear as rows",
        )

    with mc_col:
        col_els = _cached_get_elements(col_dim, "all", 200)
        col_el_names = [e["name"] for e in col_els.get("elements", [])] if "error" not in col_els else []
        col_default = 0
        for j, e in enumerate(col_els.get("elements", [])):
            if e["element_type"] == "Consolidated":
                col_default = j
                break
        col_parent = st.selectbox(
            f"Expand ({col_dim})",
            col_el_names,
            index=min(col_default, max(0, len(col_el_names) - 1)),
            key=f"cv_colp_{selected_cube}",
            help="Children of this element will appear as columns",
        )

    # 5. Max rows control
    max_rows = st.slider("Max rows", 10, 500, 100, step=10, key=f"cv_maxrows_{selected_cube}")

    # 6. Load Data button
    if st.button("Load Data", type="primary", key=f"cv_load_{selected_cube}"):
        # Build MDX
        row_set = f"{{[{row_dim}].[{row_parent}].Children}}"
        col_set = f"{{[{col_dim}].[{col_parent}].Children}}"

        where_parts = []
        for dim in slicer_dims:
            el = slicer_values.get(dim, "")
            if el:
                where_parts.append(f"[{dim}].[{el}]")

        mdx = f"SELECT {col_set} ON 0, {row_set} ON 1 FROM [{selected_cube}]"
        if where_parts:
            mdx += f" WHERE ({','.join(where_parts)})"

        with st.spinner("Querying TM1..."):
            result = tm1_execute_mdx_rows(mdx, top=max_rows)

        if "error" in result:
            st.error(result["error"])
        elif result.get("row_count", 0) == 0:
            st.info("No data returned for this slice.")
        else:
            headers = result["headers"]
            rows = result["rows"]
            df = pd.DataFrame(rows, columns=headers)

            # Store result in session for reference
            st.session_state.cube_viewer_last_result = {
                "cube": selected_cube,
                "mdx": mdx,
                "row_count": result["row_count"],
            }

            # Display
            st.dataframe(df, use_container_width=True, height=min(400, 35 * len(df) + 40))
            st.caption(f"{result['row_count']} rows · MDX query executed successfully")

            # Show MDX for reference
            with st.expander("MDX Query", expanded=False):
                st.code(mdx, language="sql")
