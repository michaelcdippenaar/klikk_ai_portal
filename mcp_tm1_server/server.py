"""
MCP Server for TM1 (Planning Analytics) + PostgreSQL.

Exposes TM1 metadata, query, and management tools plus PostgreSQL query tools
via the Model Context Protocol (stdio transport for Claude Desktop/Code,
SSE transport with --sse flag for web clients).

Usage:
    python server.py              # stdio transport (default)
    python server.py --sse        # SSE transport on port 8888
    python server.py --sse 9000   # SSE on custom port
"""
from __future__ import annotations

import asyncio
import json
import logging
import sys
from typing import Any

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool

import tm1_tools
import pg_tools
import report_builder
import sql_builder

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
log = logging.getLogger("mcp_tm1")

# ---------------------------------------------------------------------------
#  Tool registry — each entry maps name -> (function, description, input_schema)
# ---------------------------------------------------------------------------

TOOLS: dict[str, dict[str, Any]] = {}


def _register(name: str, func, description: str, input_schema: dict):
    TOOLS[name] = {"func": func, "description": description, "input_schema": input_schema}


# --- TM1 Metadata ---
_register("tm1_list_cubes", tm1_tools.tm1_list_cubes,
    "List all cubes on the TM1 server with their dimensions.",
    {"type": "object", "properties": {}})

_register("tm1_list_dimensions", tm1_tools.tm1_list_dimensions,
    "List all dimensions on the TM1 server.",
    {"type": "object", "properties": {}})

_register("tm1_get_dimension_elements", tm1_tools.tm1_get_dimension_elements,
    "Get elements of a TM1 dimension. Optionally filter by type or parent.",
    {"type": "object", "properties": {
        "dimension_name": {"type": "string", "description": "Dimension name"},
        "hierarchy_name": {"type": "string", "description": "Hierarchy (default: same as dimension)"},
        "element_type": {"type": "string", "description": "'Numeric', 'String', 'Consolidated', or '' for all"},
        "parent": {"type": "string", "description": "If set, returns children of this consolidated element"},
    }, "required": ["dimension_name"]})

_register("tm1_get_element_attributes", tm1_tools.tm1_get_element_attributes,
    "Get all attribute values for a specific dimension element.",
    {"type": "object", "properties": {
        "dimension_name": {"type": "string"},
        "element_name": {"type": "string"},
        "hierarchy_name": {"type": "string", "description": "Hierarchy (default: same as dimension)"},
    }, "required": ["dimension_name", "element_name"]})

_register("tm1_get_element_attributes_bulk", tm1_tools.tm1_get_element_attributes_bulk,
    "Get attributes for multiple elements at once (batch, max 100).",
    {"type": "object", "properties": {
        "dimension_name": {"type": "string"},
        "elements": {"type": "array", "items": {"type": "string"}, "description": "List of element names"},
        "attributes": {"type": "array", "items": {"type": "string"}, "description": "Attribute names (default: all)"},
        "hierarchy_name": {"type": "string"},
    }, "required": ["dimension_name", "elements"]})

_register("tm1_export_dimension_attributes", tm1_tools.tm1_export_dimension_attributes,
    "Export all elements of a dimension with their aliases and attributes as a flat table. "
    "Use to get a full picture of element metadata (names, aliases, types, custom attributes).",
    {"type": "object", "properties": {
        "dimension_name": {"type": "string", "description": "Dimension name, e.g. 'account', 'entity', 'listed_share'"},
        "hierarchy_name": {"type": "string", "description": "Hierarchy (default: same as dimension)"},
        "element_type": {"type": "string", "description": "'Numeric', 'String', 'Consolidated', or '' for all"},
        "attributes": {"type": "array", "items": {"type": "string"}, "description": "Attribute names to include (default: all)"},
        "limit": {"type": "integer", "description": "Max elements (default 500)"},
    }, "required": ["dimension_name"]})

_register("tm1_get_hierarchy", tm1_tools.tm1_get_hierarchy,
    "Get hierarchy structure showing parent-child relationships (tree view).",
    {"type": "object", "properties": {
        "dimension_name": {"type": "string"},
        "hierarchy_name": {"type": "string"},
        "max_depth": {"type": "integer", "description": "Max depth to traverse (default 3)"},
    }, "required": ["dimension_name"]})

_register("tm1_find_element", tm1_tools.tm1_find_element,
    "Search for elements by substring across element names AND alias/attribute values. "
    "Case-insensitive. Finds 'Stellenbosch Municipality' even when the element name is a GUID.",
    {"type": "object", "properties": {
        "search_term": {"type": "string", "description": "Text to search for (e.g. 'Stellenbosch', 'Absa', 'rent')"},
        "dimension_name": {"type": "string", "description": "Limit search to this dimension (default: all)"},
        "search_aliases": {"type": "boolean", "description": "Also search alias/attribute values (default true)"},
    }, "required": ["search_term"]})

_register("tm1_validate_elements", tm1_tools.tm1_validate_elements,
    "Check which element names exist in a dimension and which don't.",
    {"type": "object", "properties": {
        "dimension_name": {"type": "string"},
        "element_names": {"type": "array", "items": {"type": "string"}},
        "hierarchy_name": {"type": "string"},
    }, "required": ["dimension_name", "element_names"]})

_register("tm1_list_processes", tm1_tools.tm1_list_processes,
    "List all TI processes on the server.",
    {"type": "object", "properties": {}})

_register("tm1_get_process_code", tm1_tools.tm1_get_process_code,
    "Get the code (Prolog, Metadata, Data, Epilog) of a TI process.",
    {"type": "object", "properties": {
        "process_name": {"type": "string"},
    }, "required": ["process_name"]})

_register("tm1_get_cube_rules", tm1_tools.tm1_get_cube_rules,
    "Get the rules of a TM1 cube.",
    {"type": "object", "properties": {
        "cube_name": {"type": "string"},
    }, "required": ["cube_name"]})

_register("tm1_list_views", tm1_tools.tm1_list_views,
    "List all saved views for a cube.",
    {"type": "object", "properties": {
        "cube_name": {"type": "string"},
    }, "required": ["cube_name"]})

# --- TM1 Query ---
_register("tm1_query_mdx", tm1_tools.tm1_query_mdx,
    "Execute an MDX query and return results with element coordinates.",
    {"type": "object", "properties": {
        "mdx": {"type": "string", "description": "MDX query"},
        "top_records": {"type": "integer", "description": "Max results (default 100)"},
    }, "required": ["mdx"]})

_register("tm1_execute_mdx_rows", tm1_tools.tm1_execute_mdx_rows,
    "Execute MDX and return as flat row-based records (dataframe style).",
    {"type": "object", "properties": {
        "mdx": {"type": "string", "description": "MDX query"},
    }, "required": ["mdx"]})

_register("tm1_read_view", tm1_tools.tm1_read_view,
    "Read data from a saved TM1 view.",
    {"type": "object", "properties": {
        "cube_name": {"type": "string"},
        "view_name": {"type": "string"},
        "private": {"type": "boolean", "description": "Read private view (default false)"},
    }, "required": ["cube_name", "view_name"]})

_register("tm1_get_cell_value", tm1_tools.tm1_get_cell_value,
    "Get a single cell value from a cube given element coordinates.",
    {"type": "object", "properties": {
        "cube_name": {"type": "string"},
        "elements": {"type": "array", "items": {"type": "string"}, "description": "Element coordinates"},
    }, "required": ["cube_name", "elements"]})

# --- TM1 Management ---
_register("tm1_run_process", tm1_tools.tm1_run_process,
    "Execute a TI process. Requires confirm=true for safety.",
    {"type": "object", "properties": {
        "process_name": {"type": "string"},
        "parameters": {"type": "object", "description": "Process parameters as key-value pairs"},
        "confirm": {"type": "boolean", "description": "Must be true to execute (safety gate)"},
    }, "required": ["process_name", "confirm"]})

_register("tm1_write_cell", tm1_tools.tm1_write_cell,
    "Write a value to a single TM1 cell. Requires confirm=true for safety.",
    {"type": "object", "properties": {
        "cube_name": {"type": "string"},
        "elements": {"type": "array", "items": {"type": "string"}},
        "value": {"description": "Value to write (number or string)"},
        "confirm": {"type": "boolean", "description": "Must be true to write (safety gate)"},
    }, "required": ["cube_name", "elements", "value", "confirm"]})

_register("tm1_get_server_info", tm1_tools.tm1_get_server_info,
    "Get TM1 server info (name, active users).",
    {"type": "object", "properties": {}})

# --- PostgreSQL ---
_register("pg_query_financials", pg_tools.pg_query_financials,
    "Run a read-only SELECT against klikk_financials_v4 (Xero GL, investments, Investec portfolio). SELECT only.",
    {"type": "object", "properties": {
        "sql": {"type": "string", "description": "SELECT statement (use LIMIT)"},
        "limit": {"type": "integer", "description": "Max rows (default 100, max 1000)"},
    }, "required": ["sql"]})

_register("pg_list_tables", pg_tools.pg_list_tables,
    "List all tables in klikk_financials_v4 or klikk_bi_etl with sizes and row counts.",
    {"type": "object", "properties": {
        "database": {"type": "string", "description": "'financials' or 'bi'"},
    }, "required": ["database"]})

_register("pg_describe_table", pg_tools.pg_describe_table,
    "Return column names and data types for a PostgreSQL table.",
    {"type": "object", "properties": {
        "database": {"type": "string", "description": "'financials' or 'bi'"},
        "table_name": {"type": "string", "description": "Table name, e.g. 'xero_cube_xerotrailbalance'"},
    }, "required": ["database", "table_name"]})

_register("pg_get_xero_gl_sample", pg_tools.pg_get_xero_gl_sample,
    "Fetch sample Xero GL trial balance rows for a given year/month.",
    {"type": "object", "properties": {
        "year": {"type": "integer", "description": "Calendar year"},
        "month": {"type": "integer", "description": "Month 1-12"},
        "limit": {"type": "integer", "description": "Max rows (default 50)"},
    }, "required": ["year", "month"]})

_register("pg_get_share_data", pg_tools.pg_get_share_data,
    "Fetch detailed data for a specific share by symbol or name (fuzzy match). Returns holdings, dividends, prices, transactions.",
    {"type": "object", "properties": {
        "symbol_search": {"type": "string", "description": "Share symbol (e.g. 'ABG.JO') or name (e.g. 'Absa')"},
        "include": {"type": "string", "description": "Comma-separated: holdings,dividends,prices,transactions,performance"},
    }, "required": ["symbol_search"]})

_register("pg_get_share_summary", pg_tools.pg_get_share_summary,
    "Fetch summary of all tracked shares with latest prices and Investec positions.",
    {"type": "object", "properties": {
        "limit": {"type": "integer", "description": "Max rows (default 50)"},
    }})

# --- Report Builder ---
_register("tm1_build_report", report_builder.tm1_build_report,
    "Build and execute a TM1 report from natural language. "
    "Examples: 'trial balance by account for 2025 actual', "
    "'share holdings by share for Klikk 2025', "
    "'cashflow summary by activity for 2025'. "
    "Auto-detects cube, resolves element names via aliases, builds MDX, and returns data.",
    {"type": "object", "properties": {
        "query": {"type": "string", "description": "Natural language report request"},
        "cube_name": {"type": "string", "description": "Override auto-detected cube (optional)"},
        "rows_dimension": {"type": "string", "description": "Force dimension on rows (optional)"},
        "columns_dimension": {"type": "string", "description": "Force dimension on columns (optional)"},
        "measure": {"type": "string", "description": "Force measure element (optional)"},
        "top_n": {"type": "integer", "description": "Max rows (default 50)"},
    }, "required": ["query"]})

_register("tm1_resolve_report_elements", report_builder.tm1_resolve_report_elements,
    "Resolve natural language references to TM1 elements. "
    "Use to preview what the report builder would match before running a full report.",
    {"type": "object", "properties": {
        "query": {"type": "string", "description": "Text containing element references"},
        "dimension_name": {"type": "string", "description": "Limit search to this dimension (optional)"},
    }, "required": ["query"]})

_register("tm1_list_report_cubes", report_builder.tm1_list_report_cubes,
    "List available cube profiles for natural language reporting with their keywords and dimensions.",
    {"type": "object", "properties": {}})

# --- SQL Builder ---
_register("sql_build_query", sql_builder.sql_build_query,
    "Build and execute a SQL query from natural language against klikk_financials_v4. "
    "Knows the database schema (Xero GL, Investec portfolio, market data, bank transactions). "
    "Examples: 'total expenses by account for 2025', 'top 10 shares by value', "
    "'dividends received this year', 'latest portfolio holdings'. "
    "Auto-detects relevant tables, builds SQL, and executes.",
    {"type": "object", "properties": {
        "question": {"type": "string", "description": "Natural language query, e.g. 'total expenses by account for 2025'"},
        "tables": {"type": "array", "items": {"type": "string"}, "description": "Override auto-detected tables (optional)"},
        "execute": {"type": "boolean", "description": "Execute the query (default true). Set false to only see the SQL."},
        "limit": {"type": "integer", "description": "Max rows (default 100)"},
    }, "required": ["question"]})

_register("sql_list_tables_schema", sql_builder.sql_list_tables_schema,
    "List all known PostgreSQL tables with descriptions, columns, and query keywords. "
    "Use this to understand what financial data is available before building queries.",
    {"type": "object", "properties": {}})


# ---------------------------------------------------------------------------
#  MCP Server
# ---------------------------------------------------------------------------

app = Server("klikk-tm1-pg")


@app.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(name=name, description=t["description"], inputSchema=t["input_schema"])
        for name, t in TOOLS.items()
    ]


@app.call_tool()
async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
    if name not in TOOLS:
        return [TextContent(type="text", text=json.dumps({"error": f"Unknown tool: {name}"}))]

    func = TOOLS[name]["func"]
    try:
        result = await asyncio.to_thread(func, **arguments)
    except Exception as e:
        result = {"error": str(e)}

    text = json.dumps(result, default=str, indent=2)
    # Truncate very large results
    if len(text) > 50_000:
        text = text[:50_000] + "\n... (truncated)"
    return [TextContent(type="text", text=text)]


async def main():
    use_sse = "--sse" in sys.argv
    if use_sse:
        from mcp.server.sse import SseServerTransport
        from starlette.applications import Starlette
        from starlette.routing import Route
        import uvicorn

        sse = SseServerTransport("/messages/")

        async def handle_sse(request):
            async with sse.connect_sse(request.scope, request.receive, request._send) as streams:
                await app.run(streams[0], streams[1], app.create_initialization_options())

        starlette_app = Starlette(routes=[
            Route("/sse", endpoint=handle_sse),
            Route("/messages/", endpoint=sse.handle_post_message, methods=["POST"]),
        ])

        port = 8888
        idx = sys.argv.index("--sse")
        if idx + 1 < len(sys.argv):
            try:
                port = int(sys.argv[idx + 1])
            except ValueError:
                pass

        log.info("Starting MCP SSE server on port %d", port)
        config = uvicorn.Config(starlette_app, host="0.0.0.0", port=port, log_level="info")
        server = uvicorn.Server(config)
        await server.serve()
    else:
        log.info("Starting MCP stdio server (TM1 + PostgreSQL)")
        async with stdio_server() as (read_stream, write_stream):
            await app.run(read_stream, write_stream, app.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(main())
