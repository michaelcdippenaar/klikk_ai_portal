# Klikk TM1 + PostgreSQL MCP Server

Model Context Protocol server exposing TM1 (Planning Analytics) and PostgreSQL tools.

## Tools available

### TM1 (22 tools)
- **Metadata**: list cubes/dimensions, get elements, attributes, hierarchies, find elements, list processes, get process code, cube rules, views
- **Query**: MDX queries, read views, get cell values
- **Management**: run TI processes, write cells, server info (write ops require `confirm=true`)

### PostgreSQL (7 tools)
- **Query**: SELECT against klikk_financials_v4 or klikk_bi_etl
- **Schema**: list tables, describe columns
- **Shortcuts**: Xero GL sample, share data lookup, share portfolio summary

## Setup

```bash
# Install dependencies (or use the existing backend venv)
pip install -r requirements.txt

# Copy .env and edit connection details
cp .env.example .env
```

## Running

```bash
# stdio transport (for Claude Desktop / Claude Code)
python server.py

# SSE transport (for web clients)
python server.py --sse          # port 8888
python server.py --sse 9000     # custom port
```

## Claude Desktop configuration

Add to `~/.claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "klikk-tm1-pg": {
      "command": "/home/mc/apps/klikk_ai_portal/backend/.venv/bin/python",
      "args": ["/home/mc/apps/klikk_ai_portal/mcp_tm1_server/server.py"],
      "cwd": "/home/mc/apps/klikk_ai_portal/mcp_tm1_server"
    }
  }
}
```

## Claude Code configuration

Add to `.claude/settings.json` or project `CLAUDE.md`:

```json
{
  "mcpServers": {
    "klikk-tm1-pg": {
      "command": "/home/mc/apps/klikk_ai_portal/backend/.venv/bin/python",
      "args": ["/home/mc/apps/klikk_ai_portal/mcp_tm1_server/server.py"],
      "cwd": "/home/mc/apps/klikk_ai_portal/mcp_tm1_server"
    }
  }
}
```
