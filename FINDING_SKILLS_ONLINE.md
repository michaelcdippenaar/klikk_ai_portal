# Finding Standard Skills and Tools Online

How to find, evaluate, and add pre-built skills/tools to your AI agent.

---

## 1. Where to find skills

### Anthropic / Claude tool-use examples

- **Anthropic Cookbook**: https://github.com/anthropics/anthropic-cookbook
  - Tool use patterns, function calling, MCP examples.
- **Anthropic tool-use docs**: https://docs.anthropic.com/en/docs/build-with-claude/tool-use

### OpenAI function-calling examples

- **OpenAI Cookbook**: https://github.com/openai/openai-cookbook
  - `examples/How_to_call_functions_with_chat_models.ipynb` and related.
- **OpenAI function-calling docs**: https://platform.openai.com/docs/guides/function-calling

### MCP (Model Context Protocol) servers

MCP is an open standard for connecting AI agents to external tools and data. Any MCP server can provide tools to your agent.

- **Official MCP spec and SDK**: https://github.com/modelcontextprotocol
- **MCP server directory (1,500+ servers)**: https://mcpservers.com
- **Cursor MCP integrations**: https://cursor.com/help/customization/mcp
- **Awesome MCP Servers**: https://github.com/punkpeye/awesome-mcp-servers
- **Smithery (MCP registry)**: https://smithery.ai

Popular MCP servers relevant to your stack:
| Server | What it does |
|--------|-------------|
| **postgres** | SQL queries on Postgres |
| **github** | Repo management, PRs, issues |
| **google-drive** | Read/search Google Drive files |
| **slack** | Send/read Slack messages |
| **playwright** | Browser automation/testing |
| **sentry** | Error tracking |
| **notion** | Knowledge base access |

### LangChain / LangGraph tools

- **LangChain tool directory**: https://python.langchain.com/docs/integrations/tools/
  - Pre-built tools for: Google Search, Wikipedia, Wolfram Alpha, Python REPL, SQL databases, file systems, etc.
- **LangChain Hub**: https://smith.langchain.com/hub
  - Community prompts and chains.

### CrewAI tools

- **CrewAI tools**: https://github.com/crewAIInc/crewAI-tools
  - File read/write, web scrape, PDF search, code interpreter, etc.

### Composio (universal tool platform)

- https://composio.dev
- 250+ pre-built integrations (Gmail, Slack, Jira, GitHub, Google Sheets, etc.) exposed as tool-calling functions.

---

## 2. How to evaluate a skill before adding it

Before integrating any external skill, check:

1. **Schema compatibility** — Does it expose tool schemas in Anthropic or OpenAI format? Your `tool_registry.py` expects Anthropic format (`name`, `description`, `input_schema`) and auto-converts to OpenAI.

2. **Security** — Does it require API keys or credentials? Does it write data or only read? Add safety guards (dry-run, confirmation) for write operations.

3. **Return format** — Your agent expects tool results as JSON dicts. If the tool returns raw text, wrap it.

4. **Dependencies** — Check `requirements.txt` impact. Prefer tools with minimal dependencies.

5. **Error handling** — Does it return `{"error": "..."}` on failure? Your `call_tool()` in `tool_registry.py` expects this pattern.

---

## 3. How to add a new skill to this agent

### Step 1: Create the skill module

Create a new Python file in `backend/mcp_server/skills/`:

```python
# backend/mcp_server/skills/my_new_skill.py
"""
Skill: My New Skill — short description.
"""
from typing import Any

def my_tool_function(param1: str, param2: int = 10) -> dict[str, Any]:
    """What this tool does."""
    try:
        # ... your logic ...
        return {"result": "..."}
    except Exception as e:
        return {"error": str(e)}

TOOL_SCHEMAS = [
    {
        "name": "my_tool_function",
        "description": "Clear description of what this does and when to use it.",
        "input_schema": {
            "type": "object",
            "properties": {
                "param1": {"type": "string", "description": "What param1 is"},
                "param2": {"type": "integer", "description": "What param2 is (default 10)"},
            },
            "required": ["param1"],
        },
    },
]

TOOL_FUNCTIONS = {
    "my_tool_function": my_tool_function,
}
```

### Step 2: Register in tool_registry.py

```python
from mcp_server.skills import my_new_skill

_SKILL_MODULES = [
    # ... existing modules ...
    my_new_skill,
]
```

### Step 3: Add routing keywords (optional but recommended)

In `tool_registry.py`, add an entry to `_KEYWORD_ROUTES`:

```python
_KEYWORD_ROUTES: list[tuple[list[str], list]] = [
    # ... existing routes ...
    (
        ["keyword1", "keyword2", "keyword3"],
        [my_new_skill],
    ),
]
```

### Step 4: Add a system prompt tier (if needed)

If the tool needs specific instructions, add a `TIER_MY_SKILL` block in `system_prompt.py` and a corresponding entry in `_TIER_ROUTES`.

### Step 5: Rebuild and test

```bash
cd /home/mc/apps/klikk_ai_portal
docker compose build --no-cache && docker compose up -d
```

---

## 4. Example: adding a Gmail skill

Using Composio or a custom integration:

```python
# backend/mcp_server/skills/gmail_skill.py
"""Skill: Gmail — read and search emails."""
import imaplib
import email
from typing import Any
from config import settings

def gmail_search(query: str, max_results: int = 10) -> dict[str, Any]:
    """Search Gmail inbox. Returns subject, sender, date for matching emails."""
    # ... IMAP implementation ...
    return {"emails": [...], "count": ...}

def gmail_read_email(message_id: str) -> dict[str, Any]:
    """Read full email content by message ID."""
    # ... implementation ...
    return {"subject": "...", "body": "...", "from": "...", "date": "..."}

TOOL_SCHEMAS = [
    {
        "name": "gmail_search",
        "description": "Search Gmail inbox for emails matching a query.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query (Gmail search syntax)"},
                "max_results": {"type": "integer", "description": "Max emails to return (default 10)"},
            },
            "required": ["query"],
        },
    },
    {
        "name": "gmail_read_email",
        "description": "Read the full content of a specific email by message ID.",
        "input_schema": {
            "type": "object",
            "properties": {
                "message_id": {"type": "string", "description": "Email message ID from gmail_search results"},
            },
            "required": ["message_id"],
        },
    },
]

TOOL_FUNCTIONS = {
    "gmail_search": gmail_search,
    "gmail_read_email": gmail_read_email,
}
```

---

## 5. Useful search queries for finding skills

When searching online for skills for your specific use cases:

| Use case | Search query |
|----------|-------------|
| TM1/Planning Analytics | `TM1 REST API python tool` or `Planning Analytics agent tool` |
| PostgreSQL | `langchain postgres tool` or `MCP server postgres` |
| Gmail | `composio gmail tool function calling` or `MCP server gmail` |
| Google Drive | `langchain google drive tool` or `MCP server google-drive` |
| Web scraping | `langchain web scraper tool` or `MCP server puppeteer` |
| File handling | `crewai file tools` or `langchain file system tool` |
| Xero accounting | `xero API python tool` or `xero agent integration` |
| Financial data | `yfinance tool function calling` or `alpha vantage agent tool` |
| PDF/documents | `langchain document loader` or `unstructured.io tool` |
| Embeddings | `voyage-4-nano self-host` or `huggingface TEI embeddings` |
