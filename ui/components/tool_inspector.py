"""
Tool call inspector component.
Renders each tool call as a collapsible expander showing inputs and results.
"""
from __future__ import annotations

import json

import streamlit as st


def render_tool_calls(tool_calls: list) -> None:
    """Render a list of ToolCall objects as collapsible expanders."""
    if not tool_calls:
        return
    for tc in tool_calls:
        label = f"Tool: `{tc.name}`"
        with st.expander(label, expanded=False):
            col1, col2 = st.columns(2)
            with col1:
                st.markdown("**Input**")
                st.json(tc.input)
            with col2:
                st.markdown("**Result**")
                if isinstance(tc.result, dict):
                    if "error" in tc.result:
                        st.error(tc.result["error"])
                    else:
                        st.json(tc.result)
                else:
                    st.code(str(tc.result))
