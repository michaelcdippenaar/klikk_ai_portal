"""
Skills management API — view, edit, and version AI agent skill definitions.

Skills are the tools and widget types available to the AI agent.
Each change creates a version snapshot for rollback capability.

Versions are stored in skills_versions/ directory as timestamped YAML files.
"""
from __future__ import annotations

import ast
import importlib
import json
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from logger import log

router = APIRouter()

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
BACKEND_DIR = Path(__file__).parent.parent
WIDGET_TYPES_FILE = BACKEND_DIR / "widget_types.yaml"
SKILLS_DIR = BACKEND_DIR / "mcp_server" / "skills"
VERSIONS_DIR = BACKEND_DIR.parent / "skills_versions"
MANIFEST_FILE = VERSIONS_DIR / "manifest.json"


# ---------------------------------------------------------------------------
# Helpers — YAML I/O
# ---------------------------------------------------------------------------

def _load_widget_types() -> dict:
    """Load and return the full widget_types.yaml as a dict."""
    if not WIDGET_TYPES_FILE.exists():
        return {"widget_types": {}}
    with open(WIDGET_TYPES_FILE) as f:
        data = yaml.safe_load(f)
    return data or {"widget_types": {}}


def _save_widget_types(data: dict):
    """Write data back to widget_types.yaml."""
    with open(WIDGET_TYPES_FILE, "w") as f:
        yaml.dump(data, f, default_flow_style=False, sort_keys=False, allow_unicode=True)


# ---------------------------------------------------------------------------
# Helpers — Versioning
# ---------------------------------------------------------------------------

def _ensure_versions_dir():
    VERSIONS_DIR.mkdir(parents=True, exist_ok=True)


def _load_manifest() -> list[dict]:
    _ensure_versions_dir()
    if MANIFEST_FILE.exists():
        with open(MANIFEST_FILE) as f:
            return json.load(f)
    return []


def _save_manifest(entries: list[dict]):
    _ensure_versions_dir()
    with open(MANIFEST_FILE, "w") as f:
        json.dump(entries, f, indent=2, default=str)


def _create_version_snapshot(
    description: str,
    changed_by: str = "user",
    skill_name: str = "",
) -> str:
    """Copy current widget_types.yaml into skills_versions/, update manifest.
    Returns the version id (timestamp string).
    """
    _ensure_versions_dir()
    now = datetime.now(timezone.utc)
    ts = now.strftime("%Y%m%dT%H%M%SZ")
    safe_desc = re.sub(r"[^a-zA-Z0-9_-]", "_", description)[:60]
    filename = f"{ts}_{safe_desc}.yaml"

    # Copy current file
    dest = VERSIONS_DIR / filename
    if WIDGET_TYPES_FILE.exists():
        shutil.copy2(WIDGET_TYPES_FILE, dest)
    else:
        dest.write_text("")

    # Update manifest
    manifest = _load_manifest()
    entry = {
        "id": ts,
        "filename": filename,
        "timestamp": now.isoformat(),
        "description": description,
        "changed_by": changed_by,
        "skill_name": skill_name,
    }
    manifest.insert(0, entry)
    _save_manifest(manifest)

    log.info("Skills version snapshot created: %s — %s", ts, description)
    return ts


def _list_versions() -> list[dict]:
    return _load_manifest()


def _get_version(version_id: str) -> str:
    """Return the YAML content of a version snapshot."""
    manifest = _load_manifest()
    entry = next((e for e in manifest if e["id"] == version_id), None)
    if not entry:
        raise HTTPException(404, f"Version {version_id} not found")
    version_file = VERSIONS_DIR / entry["filename"]
    if not version_file.exists():
        raise HTTPException(404, f"Version file missing for {version_id}")
    return version_file.read_text()


def _restore_version(version_id: str):
    """Snapshot current state, then overwrite widget_types.yaml with old version."""
    # Snapshot current state first
    _create_version_snapshot(
        description=f"pre-restore_backup_before_{version_id}",
        changed_by="system",
        skill_name="",
    )
    content = _get_version(version_id)
    WIDGET_TYPES_FILE.write_text(content)
    log.info("Restored widget_types.yaml to version %s", version_id)


# ---------------------------------------------------------------------------
# Helpers — Tool modules
# ---------------------------------------------------------------------------

MCP_SERVER_DIR = BACKEND_DIR / "mcp_tm1_server"


_SKIP_MODULES = {"config", "requirements", "__init__", "README"}


def _extract_tool_names(source: str) -> list[str]:
    """Extract tool names from Python source using multiple patterns."""
    names: list[str] = []

    # Pattern 1: TOOL_SCHEMAS = [ ... {"name": "tool_name"} ... ]
    schema_match = re.search(r"TOOL_SCHEMAS\s*=\s*\[", source)
    if schema_match:
        found = re.findall(r'"name"\s*:\s*"([^"]+)"', source[schema_match.start():])
        names.extend(found)

    # Pattern 2: TOOL_FUNCTIONS = { "tool_name": ... }
    if not names:
        func_match = re.search(r"TOOL_FUNCTIONS\s*=\s*\{", source)
        if func_match:
            found = re.findall(r'"([a-z_]+)"\s*:', source[func_match.start():])
            names.extend(found)

    # Pattern 3: _register("tool_name", ...) calls (MCP server)
    if not names:
        found = re.findall(r'_register\(\s*"([^"]+)"', source)
        names.extend(found)

    # Pattern 4: Public tool functions (def tm1_*, def pg_*, etc.)
    if not names:
        found = re.findall(r'^def ((?:tm1|pg|sql|report)_[a-z_]+)\s*\(', source, re.MULTILINE)
        names.extend(found)

    return list(dict.fromkeys(names))


def _get_module_docstring(source: str) -> str:
    try:
        tree = ast.parse(source)
        docstring = ast.get_docstring(tree)
        return docstring.strip() if docstring else ""
    except SyntaxError:
        return "(syntax error in module)"


def _scan_directory(directory: Path, source_label: str) -> list[dict]:
    """Scan a directory for Python skill/tool modules."""
    results = []
    if not directory.is_dir():
        return results

    for py_file in sorted(directory.glob("*.py")):
        if py_file.name.startswith("__"):
            continue
        module_name = py_file.stem
        if module_name in _SKIP_MODULES:
            continue
        source = py_file.read_text()

        description = _get_module_docstring(source)
        tool_names = _extract_tool_names(source)

        if not tool_names and not description:
            continue

        results.append({
            "module": module_name,
            "source_label": source_label,
            "file_path": str(py_file),
            "tool_count": len(tool_names),
            "tools": [{"name": n} for n in tool_names],
            "description": description,
        })
    return results


def _get_tool_modules() -> list[dict]:
    """Scan all skill directories and return metadata."""
    modules = []
    modules.extend(_scan_directory(SKILLS_DIR, "mcp_server/skills"))
    modules.extend(_scan_directory(MCP_SERVER_DIR, "mcp_tm1_server"))
    return modules


def _resolve_module_file(module_name: str) -> Path:
    """Find a module file across all known skill directories."""
    for d in (SKILLS_DIR, MCP_SERVER_DIR):
        candidate = d / f"{module_name}.py"
        if candidate.exists():
            return candidate
    raise HTTPException(404, f"Skill module '{module_name}' not found")


def _get_tool_module_detail(module_name: str) -> dict:
    """Return TOOL_SCHEMAS and source for a specific skill module."""
    py_file = _resolve_module_file(module_name)
    source = py_file.read_text()

    tool_schemas = []
    try:
        match = re.search(r"(TOOL_SCHEMAS\s*=\s*\[.*?\n\])", source, re.DOTALL)
        if match:
            list_match = re.search(r"=\s*(\[.*\])", match.group(1), re.DOTALL)
            if list_match:
                tool_schemas = ast.literal_eval(list_match.group(1))
    except Exception as e:
        log.warning("Could not parse TOOL_SCHEMAS for %s: %s", module_name, e)

    description = _get_module_docstring(source)

    return {
        "module": module_name,
        "file_path": str(py_file),
        "description": description,
        "tool_schemas": tool_schemas,
        "source": source,
    }


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------

class WidgetTypeDefinition(BaseModel):
    description: str = ""
    props: dict[str, str] = {}
    default_width: int = 2
    default_height: str = "md"
    auto_mdx: bool = False


class NewWidgetType(BaseModel):
    name: str
    definition: dict[str, Any]


class ChatRequest(BaseModel):
    message: str
    history: list[dict] = []


class ApplyChangesRequest(BaseModel):
    changes: dict[str, Any]


# ---------------------------------------------------------------------------
# Endpoints — List all skills
# ---------------------------------------------------------------------------

@router.get("/")
async def list_skills():
    """List all skills: widget types from YAML + tool modules from Python."""
    # Widget types
    data = _load_widget_types()
    wt_raw = data.get("widget_types", {})
    widget_types = []
    for name, defn in wt_raw.items():
        if not isinstance(defn, dict):
            continue
        widget_types.append({
            "name": name,
            "description": defn.get("description", ""),
            "props": defn.get("props", {}),
            "default_width": defn.get("default_width", 2),
            "default_height": defn.get("default_height", "md"),
            "auto_mdx": defn.get("auto_mdx", False),
        })

    # Tool modules
    tool_modules = _get_tool_modules()

    return {"widget_types": widget_types, "tool_modules": tool_modules}


# ---------------------------------------------------------------------------
# Endpoints — Widget type CRUD
# ---------------------------------------------------------------------------

@router.get("/widget-types")
async def get_widget_types():
    """Return the full widget_types.yaml content as JSON."""
    return _load_widget_types()


@router.put("/widget-types/{type_name}")
async def update_widget_type(type_name: str, definition: WidgetTypeDefinition):
    """Update a single widget type definition. Creates a version snapshot."""
    data = _load_widget_types()
    wt = data.get("widget_types", {})
    if type_name not in wt:
        raise HTTPException(404, f"Widget type '{type_name}' not found")

    _create_version_snapshot(
        description=f"update_{type_name}",
        changed_by="user",
        skill_name=type_name,
    )

    wt[type_name] = definition.model_dump()
    data["widget_types"] = wt
    _save_widget_types(data)

    log.info("Updated widget type: %s", type_name)
    return {"status": "updated", "type_name": type_name, "definition": wt[type_name]}


@router.post("/widget-types")
async def add_widget_type(body: NewWidgetType):
    """Add a new widget type. Creates a version snapshot."""
    data = _load_widget_types()
    wt = data.get("widget_types", {})
    if body.name in wt:
        raise HTTPException(409, f"Widget type '{body.name}' already exists")

    _create_version_snapshot(
        description=f"add_{body.name}",
        changed_by="user",
        skill_name=body.name,
    )

    wt[body.name] = body.definition
    data["widget_types"] = wt
    _save_widget_types(data)

    log.info("Added widget type: %s", body.name)
    return {"status": "created", "type_name": body.name, "definition": body.definition}


@router.delete("/widget-types/{type_name}")
async def delete_widget_type(type_name: str):
    """Remove a widget type. Creates a version snapshot."""
    data = _load_widget_types()
    wt = data.get("widget_types", {})
    if type_name not in wt:
        raise HTTPException(404, f"Widget type '{type_name}' not found")

    _create_version_snapshot(
        description=f"delete_{type_name}",
        changed_by="user",
        skill_name=type_name,
    )

    del wt[type_name]
    data["widget_types"] = wt
    _save_widget_types(data)

    log.info("Deleted widget type: %s", type_name)
    return {"status": "deleted", "type_name": type_name}


# ---------------------------------------------------------------------------
# Endpoints — Tool modules (read-only)
# ---------------------------------------------------------------------------

@router.get("/tools/{module_name}")
async def get_tool_module(module_name: str):
    """Return tool schemas and source code for a skill module."""
    return _get_tool_module_detail(module_name)


@router.get("/tools/{module_name}/source")
async def get_tool_source(module_name: str):
    """Return the raw Python source of a skill module."""
    py_file = _resolve_module_file(module_name)
    return {"module_name": module_name, "source": py_file.read_text()}


# ---------------------------------------------------------------------------
# Endpoints — Versioning
# ---------------------------------------------------------------------------

@router.get("/versions")
async def list_versions():
    """List all version snapshots (newest first)."""
    versions = _list_versions()
    return {
        "versions": [
            {
                "id": v["id"],
                "timestamp_iso": v.get("timestamp", ""),
                "change_description": v.get("description", ""),
                "changed_by": v.get("changed_by", "unknown"),
                "skill_name": v.get("skill_name", ""),
            }
            for v in versions
        ],
        "count": len(versions),
    }


@router.get("/versions/{version_id}")
async def get_version(version_id: str):
    """Get the full widget_types.yaml content at a specific version."""
    content = _get_version(version_id)
    # Parse YAML so we return structured JSON
    try:
        parsed = yaml.safe_load(content)
    except yaml.YAMLError:
        parsed = None
    return {"version_id": version_id, "content_yaml": content, "content_json": parsed}


@router.post("/versions/{version_id}/restore")
async def restore_version(version_id: str):
    """Restore widget_types.yaml to a previous version. Creates a backup snapshot first."""
    _restore_version(version_id)
    return {"status": "restored", "version_id": version_id}


# ---------------------------------------------------------------------------
# Endpoints — Agent chat for skill editing
# ---------------------------------------------------------------------------

SKILL_CHAT_SYSTEM_PROMPT = """\
You are a skill editor assistant for the Klikk AI Portal.
Your job is to help users create or modify widget type definitions in widget_types.yaml.

The YAML format is:
```yaml
widget_types:
  WidgetName:
    description: "What this widget does — shown to the AI agent"
    props:
      prop_name: "Description of the prop"
    default_width: 2       # 1-4 grid columns
    default_height: md      # sm, md, or lg
    auto_mdx: false         # true if MDX auto-built from cube/rows/columns/slicers
```

Current widget_types.yaml contents:
```yaml
{current_yaml}
```

When the user asks to add or modify a widget type, respond with:
1. A brief explanation of what you'll change
2. The proposed YAML changes as a JSON object with this structure:
   - For adding: {{"action": "add", "name": "WidgetName", "definition": {{...}}}}
   - For updating: {{"action": "update", "name": "ExistingWidgetName", "definition": {{...}}}}
   - For deleting: {{"action": "delete", "name": "WidgetName"}}

Always wrap the JSON in ```json ... ``` code blocks so it can be parsed.
Be helpful, suggest reasonable defaults, and ensure prop descriptions are clear for the AI agent.
"""


@router.post("/chat")
async def skill_chat(req: ChatRequest):
    """Chat endpoint for natural-language skill editing.
    Returns the AI response and any proposed changes (not applied).
    """
    from config import settings

    # Load current YAML for context
    current_yaml = ""
    if WIDGET_TYPES_FILE.exists():
        current_yaml = WIDGET_TYPES_FILE.read_text()

    system_prompt = SKILL_CHAT_SYSTEM_PROMPT.format(current_yaml=current_yaml)

    # Build messages
    messages = []
    for msg in req.history:
        messages.append({"role": msg.get("role", "user"), "content": msg.get("content", "")})
    messages.append({"role": "user", "content": req.message})

    # Call AI
    try:
        provider = settings.ai_provider.upper()
        if provider == "ANTHROPIC":
            response_text = await _call_anthropic(system_prompt, messages, settings)
        else:
            response_text = await _call_openai(system_prompt, messages, settings)
    except Exception as e:
        log.error("Skills chat AI call failed: %s", e, exc_info=True)
        raise HTTPException(502, f"AI provider error: {e}")

    # Try to extract proposed changes from the response
    proposed_changes = _extract_proposed_changes(response_text)

    return {
        "response": response_text,
        "proposed_changes": proposed_changes,
        "applied": False,
    }


@router.post("/chat/apply")
async def apply_chat_changes(req: ApplyChangesRequest):
    """Apply proposed changes from the chat endpoint."""
    changes = req.changes
    action = changes.get("action")
    name = changes.get("name")

    if not action or not name:
        raise HTTPException(400, "Changes must include 'action' and 'name'")

    if action == "add":
        definition = changes.get("definition", {})
        if not definition:
            raise HTTPException(400, "Add action requires a 'definition'")
        data = _load_widget_types()
        wt = data.get("widget_types", {})
        if name in wt:
            raise HTTPException(409, f"Widget type '{name}' already exists")

        _create_version_snapshot(
            description=f"chat_add_{name}",
            changed_by="agent",
            skill_name=name,
        )
        wt[name] = definition
        data["widget_types"] = wt
        _save_widget_types(data)
        log.info("Chat applied: added widget type %s", name)
        return {"status": "applied", "action": "add", "type_name": name}

    elif action == "update":
        definition = changes.get("definition", {})
        if not definition:
            raise HTTPException(400, "Update action requires a 'definition'")
        data = _load_widget_types()
        wt = data.get("widget_types", {})
        if name not in wt:
            raise HTTPException(404, f"Widget type '{name}' not found")

        _create_version_snapshot(
            description=f"chat_update_{name}",
            changed_by="agent",
            skill_name=name,
        )
        wt[name] = definition
        data["widget_types"] = wt
        _save_widget_types(data)
        log.info("Chat applied: updated widget type %s", name)
        return {"status": "applied", "action": "update", "type_name": name}

    elif action == "delete":
        data = _load_widget_types()
        wt = data.get("widget_types", {})
        if name not in wt:
            raise HTTPException(404, f"Widget type '{name}' not found")

        _create_version_snapshot(
            description=f"chat_delete_{name}",
            changed_by="agent",
            skill_name=name,
        )
        del wt[name]
        data["widget_types"] = wt
        _save_widget_types(data)
        log.info("Chat applied: deleted widget type %s", name)
        return {"status": "applied", "action": "delete", "type_name": name}

    else:
        raise HTTPException(400, f"Unknown action: {action}")


# ---------------------------------------------------------------------------
# AI provider helpers
# ---------------------------------------------------------------------------

async def _call_anthropic(system_prompt: str, messages: list[dict], settings) -> str:
    """Call Anthropic Claude API."""
    import anthropic

    client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
    response = client.messages.create(
        model=settings.anthropic_model,
        max_tokens=settings.max_tokens,
        system=system_prompt,
        messages=messages,
    )
    return response.content[0].text


async def _call_openai(system_prompt: str, messages: list[dict], settings) -> str:
    """Call OpenAI API with retry on 429 rate limit."""
    import asyncio
    import openai

    client = openai.OpenAI(api_key=settings.openai_api_key)
    full_messages = [{"role": "system", "content": system_prompt}] + messages
    last_err = None
    for attempt in range(4):  # 1 initial + 3 retries
        try:
            response = client.chat.completions.create(
                model=settings.openai_model,
                max_tokens=settings.max_tokens,
                messages=full_messages,
            )
            return response.choices[0].message.content
        except openai.RateLimitError as e:
            last_err = e
            wait = getattr(e, "retry_after", None) or (5.0 * (2**attempt))
            wait = min(float(wait), 60.0)
            log.warning("OpenAI rate limit (429), retry in %.1fs (attempt %d)", wait, attempt + 1)
            await asyncio.sleep(wait)
        except Exception:
            raise
    raise last_err or RuntimeError("OpenAI rate limit exceeded after retries")


def _extract_proposed_changes(response_text: str) -> dict | None:
    """Try to extract JSON proposed changes from AI response text."""
    # Look for ```json ... ``` blocks
    match = re.search(r"```json\s*\n(.*?)\n```", response_text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            pass

    # Fallback: look for any JSON object with "action" key
    match = re.search(r'\{[^{}]*"action"\s*:', response_text)
    if match:
        # Try to find the matching closing brace
        start = match.start()
        depth = 0
        for i, ch in enumerate(response_text[start:], start):
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    try:
                        return json.loads(response_text[start : i + 1])
                    except json.JSONDecodeError:
                        pass
                    break
    return None
