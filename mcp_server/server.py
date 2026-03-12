"""
FastMCP Server for Klikk Group Planning V3 Agent.

Run standalone (for Claude Desktop / MCP Inspector):
    cd /home/mc/tm1_models/klikk_group_planning_v3/agent
    python mcp_server/server.py

Or via fastmcp CLI:
    fastmcp run mcp_server/server.py
    fastmcp dev mcp_server/server.py   # opens MCP Inspector
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from fastmcp import FastMCP
from mcp_server.skills import (
    tm1_query,
    tm1_metadata,
    tm1_management,
    postgres_query,
    pattern_analysis,
    kpi_monitor,
    validation,
    element_context,
    web_search,
    google_drive,
)

mcp = FastMCP(
    name="klikk-planning-agent",
    instructions=(
        "You are an AI analyst for the Klikk Group Planning V3 TM1 financial planning model. "
        "Use tools to query TM1 data and metadata, analyse GL and cashflow data, query PostgreSQL "
        "source databases, monitor KPIs, and search the web for external context. "
        "Use element context tools to vectorise dimension elements and accumulate knowledge as you learn. "
        "IMPORTANT: All write operations (tm1_run_process, tm1_write_cell, tm1_update_element_attribute) "
        "require confirm=True — always show a dry-run first and ask the user before confirming."
    ),
)

# Register all skill modules
for skill_module in [
    tm1_query,
    tm1_metadata,
    tm1_management,
    postgres_query,
    pattern_analysis,
    kpi_monitor,
    validation,
    element_context,
    web_search,
    google_drive,
]:
    for func in skill_module.TOOL_FUNCTIONS.values():
        mcp.tool(func)

if __name__ == "__main__":
    mcp.run()
