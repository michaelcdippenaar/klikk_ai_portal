# Agent skills — Klikk AI Portal

All skills (tools and widget types) available to the AI agent. The agent uses these via the tool registry ([backend/tool_registry.py](backend/tool_registry.py)) and widget definitions ([backend/widget_types.yaml](backend/widget_types.yaml)).

---

## 1. Skill modules (Python tools)

Defined under `backend/mcp_server/skills/`. Each module exposes `TOOL_SCHEMAS` and `TOOL_FUNCTIONS` used by the agent.

| Module | Purpose |
|--------|--------|
| **tm1_query** | TM1 data query: MDX execution, named views, cell values (read-only). |
| **tm1_metadata** | TM1 metadata: cubes, dimensions, hierarchies, elements, processes. |
| **tm1_management** | TM1 management: processes, chores, sandboxes (where supported). |
| **tm1_rest_api** | TM1 REST API: server status, message log, transaction log, sessions, threads, sandboxes, MDX cellset, write values, error log, cube info. |
| **postgres_query** | PostgreSQL (klikk_financials): run read-only SQL for GL and BI data. |
| **pattern_analysis** | Pattern / anomaly analysis on data. |
| **kpi_monitor** | KPI definitions and monitoring. |
| **validation** | Data or rule validation. |
| **element_context** | TM1 element context: save/retrieve learned elements for RAG. |
| **web_search** | Web search for real-time info (e.g. stock price, news). |
| **google_drive** | Google Drive integration. |
| **widget_generation** | Create dashboard widgets from `widget_types.yaml` (single tool: `create_dashboard_widget`). |
| **paw_integration** | PAW (Planning Analytics Workspace) embed URLs and integration. |

---

## 2. TM1 REST API tools (tm1_rest_api)

These are the 12 tools from the TM1 REST skill (direct OData-style API; no TM1py):

| Tool | Description |
|------|-------------|
| **tm1_rest_server_status** | Server health: product version, server name, active sessions, thread summary. |
| **tm1_rest_message_log** | Message log (debugging MDX/TI errors). Filter by level, logger, timestamp. |
| **tm1_rest_transaction_log** | Transaction/audit log: who wrote what and when. Filter by cube, timestamp. |
| **tm1_rest_active_sessions** | List active TM1 sessions (user, ID, connection details). |
| **tm1_rest_active_threads** | Active threads: what is running, blocked, or holding locks. |
| **tm1_rest_sandbox_list** | List all sandboxes. |
| **tm1_rest_sandbox_create** | Create a sandbox (name). |
| **tm1_rest_sandbox_delete** | Delete a sandbox by name. |
| **tm1_rest_execute_mdx_cellset** | Execute MDX via REST; return full cellset with axes and cells. |
| **tm1_rest_write_values** | Write cell values to a cube (confirm=True to apply; default dry-run). |
| **tm1_rest_error_log** | Error log file listing (filenames, sizes, timestamps). |
| **tm1_rest_cube_info** | Cube details: dimensions, views, rules preview, last data update. |

---

## 3. Widget types (create_dashboard_widget)

The agent can create these widget types via the **create_dashboard_widget** tool. Definitions are in `backend/widget_types.yaml`.

| Widget type | Description |
|-------------|-------------|
| **CubeViewer** | AG Grid table from cube slice (MDX); auto_mdx from cube/rows/columns/slicers. |
| **DimensionTree** | Hierarchical tree of a TM1 dimension. |
| **DimensionEditor** | Editable element attributes table for a dimension. |
| **KPICard** | Single metric card with trend and status colour. |
| **LineChart** | Time series line chart (ECharts). |
| **BarChart** | Bar chart for comparisons (ECharts). |
| **PieChart** | Pie/donut chart (ECharts). |
| **PivotTable** | Pivot with row/column grouping; auto_mdx. |
| **DataGrid** | Generic table from inline data (no TM1). |
| **MDXEditor** | Interactive MDX editor with live results. |
| **DimensionSetEditor** | Two-panel set builder for a dimension; generates MDX set. |
| **PAWCubeViewer** | Embedded PAW cube viewer (writeback). |
| **PAWDimensionEditor** | Embedded PAW dimension/subset editor. |
| **PAWBook** | Embedded PAW book/sheet. |

---

## 4. Summary

- **13 skill modules** supply tools (TM1, Postgres, web search, KPI, validation, element context, Google Drive, widget generation, PAW).
- **tm1_rest_api** alone exposes **12 tools** (server status, logs, sessions, threads, sandboxes, MDX cellset, write, error log, cube info).
- **1 widget tool**: **create_dashboard_widget** with **14 widget types** from YAML.
- To see the full list of tool names at runtime: `from tool_registry import list_tool_names` → `list_tool_names()`.
- To manage widget types and versions: use the **/api/skills/** endpoints (list, widget-types CRUD, versions, chat for skill editing).
