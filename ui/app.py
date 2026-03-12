"""
Klikk Planning Agent — Streamlit Web UI

Launch:
    cd /home/mc/tm1_models/klikk_group_planning_v3/agent
    streamlit run ui/app.py --server.address 0.0.0.0 --server.port 8501

Access from any LAN machine: http://192.168.1.194:8501
"""
import sys
import os

_AGENT_ROOT = os.path.dirname(os.path.dirname(__file__))
if _AGENT_ROOT not in sys.path:
    sys.path.insert(0, _AGENT_ROOT)

import streamlit as st
from config import settings
from ui.session import (
    init_session, add_user_message, add_assistant_message,
    get_history_for_agent, clear_history,
)
from ui.components.chat import render_all_messages
from ui.components.tool_inspector import render_tool_calls

# --- Page config ---
st.set_page_config(
    page_title="Klikk Planning Agent",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

init_session()


# ---------------------------------------------------------------------------
#  Helper: format KPI value for st.metric
# ---------------------------------------------------------------------------
def _fmt_kpi(value: float, fmt: str) -> str:
    if fmt == "currency":
        if abs(value) >= 1_000_000:
            return f"R {value / 1_000_000:,.1f}M"
        elif abs(value) >= 1_000:
            return f"R {value / 1_000:,.1f}K"
        return f"R {value:,.2f}"
    elif fmt == "percentage":
        return f"{value:.1f}%"
    return f"{value:,.0f}"


def _status_icon(status: str) -> str:
    return {"ok": "", "warning": " ⚠️", "critical": " 🔴"}.get(status, "")


# ---------------------------------------------------------------------------
#  Sidebar
# ---------------------------------------------------------------------------
with st.sidebar:
    st.title("📊 Klikk Planning Agent")
    st.caption("Klikk Group Planning V3 · TM1 v11.8")
    st.divider()

    provider = settings.ai_provider.lower()
    if provider == "openai":
        st.info(f"AI: **OpenAI** · `{settings.openai_model}`")
    else:
        st.info(f"AI: **Anthropic** · `{settings.anthropic_model}`")

    st.divider()

    st.subheader("Connections")
    if st.button("Test Connections"):
        with st.spinner("Checking..."):
            from mcp_server.skills.validation import (
                test_tm1_connection, test_postgres_connections
            )
            tm1_status = test_tm1_connection()
            pg_status = test_postgres_connections()

        if "error" in tm1_status:
            st.error(f"TM1: {tm1_status['error']}")
        else:
            st.success(f"TM1: {tm1_status.get('server', 'connected')}")

        pg_dbs = pg_status.get("databases", {})
        for db_name, db_result in pg_dbs.items():
            if db_result.get("status") == "connected":
                st.success(f"PG: {db_name}")
            else:
                st.error(f"PG: {db_name} — {db_result.get('error', 'failed')}")

    st.divider()
    if st.button("Clear Chat", type="secondary"):
        clear_history()
        st.rerun()

    st.divider()

    # --- Data Explorer toggle ---
    st.subheader("Data Explorer")
    explorer_mode = st.radio(
        "Panel",
        ["Off", "Dimensions", "Cube Viewer", "Both"],
        key="explorer_mode",
        horizontal=False,
        label_visibility="collapsed",
    )

    st.divider()
    st.caption("TM1: 192.168.1.194:44414")
    st.caption("DB: 192.168.1.235")


# ---------------------------------------------------------------------------
#  Main area — tabs: Chat | KPI Dashboard
# ---------------------------------------------------------------------------
tab_chat, tab_kpis = st.tabs(["💬 Chat", "📈 KPI Dashboard"])

# === CHAT TAB =============================================================
with tab_chat:
    show_explorer = explorer_mode != "Off"

    if show_explorer:
        col_chat, col_explorer = st.columns([3, 2])
    else:
        col_chat = st.container()
        col_explorer = None

    with col_chat:
        # Show context bar if elements are selected from the explorer
        if st.session_state.get("selected_elements"):
            ctx_items = st.session_state.selected_elements
            ctx_text = ", ".join(f"`{e['dimension']}:{e['element']}`" for e in ctx_items)
            ctx_col1, ctx_col2 = st.columns([5, 1])
            with ctx_col1:
                st.info(f"Context: {ctx_text}")
            with ctx_col2:
                if st.button("Clear", key="clear_el_ctx"):
                    st.session_state.selected_elements = []
                    st.rerun()

        render_all_messages(st.session_state.messages)

        if prompt := st.chat_input("Ask anything about the model, data, or analysis..."):
            # Prepend element context if any elements are selected
            if st.session_state.get("selected_elements"):
                ctx = "Context elements: " + ", ".join(
                    f"{e['dimension']}:{e['element']}"
                    for e in st.session_state.selected_elements
                )
                full_prompt = f"[{ctx}]\n\n{prompt}"
                st.session_state.selected_elements = []  # clear after use
            else:
                full_prompt = prompt

            add_user_message(prompt)
            with st.chat_message("user"):
                st.markdown(prompt)

            with st.chat_message("assistant"):
                with st.status("Thinking...", expanded=True) as status:
                    from core import run_agent
                    history = get_history_for_agent()[:-1]
                    response_text, tool_calls = run_agent(full_prompt, history)
                    status.update(
                        label=f"Done ({len(tool_calls)} tool call{'s' if len(tool_calls) != 1 else ''})",
                        state="complete",
                        expanded=False,
                    )
                st.markdown(response_text)
                render_tool_calls(tool_calls)

            add_assistant_message(response_text, tool_calls)

    # === EXPLORER PANEL (right side) =========================================
    if col_explorer is not None:
        with col_explorer:
            if explorer_mode in ("Dimensions", "Both"):
                from ui.components.dimension_browser import render_dimension_browser
                render_dimension_browser()

            if explorer_mode == "Both":
                st.divider()

            if explorer_mode in ("Cube Viewer", "Both"):
                from ui.components.cube_viewer import render_cube_viewer
                render_cube_viewer()

# === KPI DASHBOARD TAB ====================================================
with tab_kpis:
    kpi_view, kpi_manage = st.tabs(["Dashboard", "Manage KPIs"])

    # --- Dashboard sub-tab --------------------------------------------------
    with kpi_view:
        col_refresh, col_yr, col_mo = st.columns([1, 1, 1])
        with col_refresh:
            refresh = st.button("Refresh KPIs", type="primary")
        with col_yr:
            kpi_year = st.text_input("Year", value="", key="kpi_year", placeholder="blank = current")
        with col_mo:
            kpi_month = st.text_input("Month", value="", key="kpi_month", placeholder="blank = current")

        if refresh:
            with st.spinner("Computing KPIs from TM1..."):
                from mcp_server.skills.kpi_monitor import get_all_kpi_values
                kpi_result = get_all_kpi_values(
                    year=kpi_year or "", month=kpi_month or "",
                )
                st.session_state.kpi_data = kpi_result

        kpi_data = st.session_state.get("kpi_data", {})

        if not kpi_data:
            st.info("Click **Refresh KPIs** to load the dashboard.")
        elif "error" in kpi_data:
            st.error(f"Could not load KPIs: {kpi_data['error']}")
        elif "categories" in kpi_data:
            period = kpi_data.get("period", {})
            st.caption(f"Period: **{period.get('month', '?')} {period.get('year', '?')}**")

            for cat_name, cat_kpis in kpi_data["categories"].items():
                st.markdown(f"### {cat_name}")
                cols = st.columns(min(len(cat_kpis), 4))
                for i, kpi in enumerate(cat_kpis):
                    with cols[i % len(cols)]:
                        icon = _status_icon(kpi.get("status", "ok"))
                        display_val = _fmt_kpi(kpi["value"], kpi.get("format", "number"))
                        st.metric(
                            label=f"{kpi['name']}{icon}",
                            value=display_val,
                            help=kpi.get("description", ""),
                        )
                st.divider()

            with st.expander("Raw KPI data (JSON)"):
                st.json(kpi_data)

    # --- Manage KPIs sub-tab ------------------------------------------------
    with kpi_manage:
        st.subheader("Defined KPIs")
        from mcp_server.skills.kpi_monitor import list_kpi_definitions, add_kpi_definition, remove_kpi_definition

        defs = list_kpi_definitions()
        if defs.get("kpi_count", 0) == 0:
            st.info("No KPIs defined yet. Use the form below or ask the agent in Chat.")
        else:
            for cat, items in defs.get("categories", {}).items():
                with st.expander(f"{cat} ({len(items)} KPIs)", expanded=True):
                    for item in items:
                        c1, c2, c3 = st.columns([3, 2, 1])
                        c1.markdown(f"**{item['name']}** (`{item['id']}`)")
                        c2.caption(f"{item['source_type']} · {item['format']}")
                        if c3.button("Remove", key=f"rm_{item['id']}"):
                            result = remove_kpi_definition(item['id'], confirm=True)
                            if result.get("status") == "success":
                                st.success(f"Removed {item['id']}")
                                st.rerun()
                            else:
                                st.error(result.get("error", "Failed"))

        st.divider()
        st.subheader("Add New KPI")
        st.caption(
            "Fill in the form below, or go to the **Chat** tab and say "
            "something like: *\"Add a KPI for monthly rental income\"* — "
            "the agent will ask you the right questions and create it."
        )

        with st.form("add_kpi_form", clear_on_submit=True):
            f_id = st.text_input("KPI ID", placeholder="e.g. gl_rental_income")
            f_name = st.text_input("Display Name", placeholder="e.g. Rental Income")
            f_cat = st.selectbox("Category", ["GL", "Cashflow", "Listed Shares", "Data Quality"])
            f_desc = st.text_input("Description", placeholder="What does this KPI measure?")
            f_source = st.selectbox("Source Type", [
                "gl_by_type", "cashflow_activity", "portfolio", "data_quality", "derived",
            ])
            f_format = st.selectbox("Format", ["currency", "number", "percentage"])

            st.markdown("**Source Parameters** (JSON)")
            f_params_str = st.text_area(
                "source_params",
                value='{"account_types": ["REVENUE"], "sign": -1}',
                height=80,
                help=(
                    'gl_by_type: {"account_types": ["REVENUE"], "sign": -1}\n'
                    'cashflow_activity: {"element": "NET_OPERATING_CASHFLOW"}\n'
                    'portfolio: {"measure": "total_value"}\n'
                    'data_quality: {"check": "unmapped_cashflow_accounts"}\n'
                    'derived: {"formula": "kpi_a - kpi_b"}'
                ),
            )

            st.markdown("**Thresholds** (optional)")
            t_col1, t_col2 = st.columns(2)
            t_warn = t_col1.text_input("Warning below/above", placeholder="e.g. below:0 or above:500000")
            t_crit = t_col2.text_input("Critical below/above", placeholder="e.g. below:-50000")

            submitted = st.form_submit_button("Add KPI", type="primary")

            if submitted and f_id and f_name:
                import json as _json
                try:
                    params = _json.loads(f_params_str) if f_params_str.strip() else {}
                except _json.JSONDecodeError:
                    st.error("Invalid JSON in source_params")
                    params = None

                thresholds = {}
                if t_warn:
                    for part in t_warn.split(","):
                        part = part.strip()
                        if "below:" in part:
                            thresholds["warning_below"] = float(part.split(":")[1])
                        elif "above:" in part:
                            thresholds["warning_above"] = float(part.split(":")[1])
                if t_crit:
                    for part in t_crit.split(","):
                        part = part.strip()
                        if "below:" in part:
                            thresholds["critical_below"] = float(part.split(":")[1])
                        elif "above:" in part:
                            thresholds["critical_above"] = float(part.split(":")[1])

                if params is not None:
                    result = add_kpi_definition(
                        kpi_id=f_id, name=f_name, category=f_cat,
                        description=f_desc, source_type=f_source,
                        source_params=params, kpi_format=f_format,
                        thresholds=thresholds if thresholds else None,
                        confirm=True,
                    )
                    if result.get("status") == "success":
                        st.success(f"Added KPI: {f_name}")
                        st.rerun()
                    else:
                        st.error(result.get("error", "Failed to add KPI"))
