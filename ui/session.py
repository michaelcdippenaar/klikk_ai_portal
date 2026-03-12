"""
Streamlit session state management for the Klikk Planning Agent UI.
"""
from __future__ import annotations

import streamlit as st


def init_session() -> None:
    """Initialise session state keys on first load."""
    if "messages" not in st.session_state:
        # Each item: {"role": "user"|"assistant", "content": str, "tool_calls": list}
        st.session_state.messages = []
    if "connection_status" not in st.session_state:
        st.session_state.connection_status = None  # None = unchecked
    # Data Explorer state
    if "selected_dimension" not in st.session_state:
        st.session_state.selected_dimension = None
    if "selected_elements" not in st.session_state:
        st.session_state.selected_elements = []  # elements picked from browser for chat context
    if "cube_viewer_last_result" not in st.session_state:
        st.session_state.cube_viewer_last_result = None


def add_user_message(content: str) -> None:
    st.session_state.messages.append({
        "role": "user",
        "content": content,
        "tool_calls": [],
    })


def add_assistant_message(content: str, tool_calls: list) -> None:
    st.session_state.messages.append({
        "role": "assistant",
        "content": content,
        "tool_calls": tool_calls,
    })


def get_history_for_agent() -> list[dict]:
    """Return conversation history in the format expected by core.run_agent."""
    return [
        {"role": m["role"], "content": m["content"]}
        for m in st.session_state.messages
    ]


def clear_history() -> None:
    st.session_state.messages = []
