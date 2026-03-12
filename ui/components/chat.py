"""
Chat message rendering component.
"""
from __future__ import annotations

import streamlit as st
from ui.components.tool_inspector import render_tool_calls


def render_message(msg: dict) -> None:
    """Render a single chat message (user or assistant) with optional tool calls."""
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])
        if msg["role"] == "assistant" and msg.get("tool_calls"):
            render_tool_calls(msg["tool_calls"])


def render_all_messages(messages: list[dict]) -> None:
    """Render the full conversation history."""
    for msg in messages:
        render_message(msg)
