# Klikk AI Portal — Connections

How the portal connects to **klikk_financials_db** (PostgreSQL) and to **MCP servers** (in-process skills).

---

## 1. PostgreSQL: klikk_financials_db

The portal connects to the Klikk Financials database for Xero GL source data (and optionally other financials data). Connection is configured via environment variables.

### Configuration

Set in `backend/.env` (or environment):

| Variable | Description | Example |
|----------|-------------|---------|
| `PG_FINANCIALS_HOST` | PostgreSQL host | `192.168.1.235` |
| `PG_FINANCIALS_PORT` | Port | `5432` |
| **`PG_FINANCIALS_DB`** | **Database name** | **`klikk_financials_db`** or `klikk_financials_v4` |
| `PG_FINANCIALS_USER` | Username | `klikk_user` |
| `PG_FINANCIALS_PASSWORD` | Password | *(required)* |

To use a database named **klikk_financials_db**:

```bash
PG_FINANCIALS_DB=klikk_financials_db
```

The same settings are used for:

- `/api/tm1/connections` (connection test; the response uses the actual DB name from config)
- MCP skills: `postgres_query` (read-only SQL), `validation` (e.g. reconcile_gl_totals)

### Verifying the connection

- **API**: `GET /api/tm1/connections` (requires auth). The `postgres.databases` object will list each configured DB by name (e.g. `klikk_financials_db`, `klikk_bi_etl`).
- **Tools**: The agent can use `test_tm1_connection` (which also runs PostgreSQL checks) and `pg_query_financials` for read-only SQL.

---

## 2. MCP servers (skills)

The portal does **not** connect to external MCP servers over the network. Instead it uses **in-process MCP-style skills**: Python modules under `backend/mcp_server/skills/` that are loaded at startup and registered as agent tools.

### Loaded skill modules

The following are loaded by `tool_registry` and exposed to the AI agent:

- `tm1_query`, `tm1_metadata`, `tm1_management`, `tm1_rest_api` — TM1/Planning Analytics
- `postgres_query` — read-only SQL on klikk_financials and klikk_bi_etl
- `validation` — model verification, GL reconciliation, connection tests
- `pattern_analysis`, `kpi_monitor`, `element_context`
- `web_search`, `google_drive`, `widget_generation`, `paw_integration`, `session_review`

### Verifying MCP skills are “connected”

- **API**: `GET /api/tm1/connections` includes an **`mcp_skills`** array listing the names of all loaded skill modules. If this array is present and non-empty, the portal is “connected” to its MCP skills (they are loaded and available to the agent).

### Adding external MCP servers (optional)

To connect the agent to **external** MCP servers (e.g. over stdio or SSE), you would need to:

1. Add an MCP client (e.g. the `mcp` Python package) and start sessions to those servers.
2. Fetch tool schemas from the MCP servers and register them in `tool_registry` (or a separate dispatch path).
3. Forward agent tool calls to the MCP client and return results.

This is not implemented in the current codebase; the portal only uses the in-process skills listed above.
