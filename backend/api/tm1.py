"""
TM1 REST API endpoints — thin wrappers around existing skill functions.
"""
from __future__ import annotations

from fastapi import APIRouter, Query
from pydantic import BaseModel

router = APIRouter()


# --- Dimensions ---------------------------------------------------------------

@router.get("/dimensions")
async def list_dimensions():
    from mcp_server.skills.tm1_metadata import tm1_list_dimensions
    return tm1_list_dimensions()


@router.get("/dimensions/{name}/elements")
async def get_elements(
    name: str,
    hierarchy: str = "",
    element_type: str = "all",
    limit: int = 500,
    search: str = "",
):
    from mcp_server.skills.tm1_metadata import tm1_get_dimension_elements
    result = tm1_get_dimension_elements(name, hierarchy, element_type, limit)
    if search and "elements" in result:
        search_lower = search.lower()
        result["elements"] = [
            e for e in result["elements"]
            if search_lower in e["name"].lower()
        ]
        result["returned"] = len(result["elements"])
    return result


@router.get("/dimensions/{name}/hierarchy")
async def get_hierarchy(name: str, hierarchy: str = ""):
    from mcp_server.skills.tm1_metadata import tm1_get_hierarchy
    return tm1_get_hierarchy(name, hierarchy)


@router.get("/dimensions/{name}/attributes")
async def get_attributes(name: str):
    from mcp_server.skills.tm1_metadata import tm1_get_element_attributes
    return tm1_get_element_attributes(name)


@router.get("/dimensions/{name}/elements/{element}/attributes/{attribute}")
async def get_attribute_value(name: str, element: str, attribute: str):
    from mcp_server.skills.tm1_metadata import tm1_get_element_attribute_value
    return tm1_get_element_attribute_value(name, element, attribute)


# --- Cubes --------------------------------------------------------------------

@router.get("/cubes")
async def list_cubes():
    from mcp_server.skills.tm1_metadata import tm1_list_cubes
    return tm1_list_cubes()


@router.get("/cubes/{name}/rules")
async def get_cube_rules(name: str):
    from mcp_server.skills.tm1_metadata import tm1_get_cube_rules
    return tm1_get_cube_rules(name)


@router.get("/cubes/{name}/views")
async def list_views(name: str):
    from mcp_server.skills.tm1_query import tm1_list_views
    return tm1_list_views(name)


# --- MDX Query ----------------------------------------------------------------

class MDXRequest(BaseModel):
    mdx: str
    top: int = 500


@router.post("/mdx")
async def execute_mdx(req: MDXRequest):
    from mcp_server.skills.tm1_query import tm1_execute_mdx_rows
    return tm1_execute_mdx_rows(req.mdx, req.top)


@router.post("/mdx/raw")
async def execute_mdx_raw(req: MDXRequest):
    from mcp_server.skills.tm1_query import tm1_query_mdx
    return tm1_query_mdx(req.mdx, req.top)


# --- Cell / View --------------------------------------------------------------

class CellRequest(BaseModel):
    cube: str
    coordinates: list[str] | str


@router.post("/cell")
async def get_cell(req: CellRequest):
    from mcp_server.skills.tm1_query import tm1_get_cell_value
    coords = req.coordinates if isinstance(req.coordinates, list) else [c.strip() for c in req.coordinates.split(",")]
    return tm1_get_cell_value(req.cube, coords)


@router.post("/view")
async def read_view(cube: str, view: str):
    from mcp_server.skills.tm1_query import tm1_read_view
    return tm1_read_view(cube, view)


# --- Natural Language Query (MDX or SQL) --------------------------------------

class NLQueryRequest(BaseModel):
    question: str
    source: str = "auto"  # "tm1", "sql", or "auto"
    execute: bool = True
    limit: int = 200


@router.post("/nl-query")
async def nl_query(req: NLQueryRequest):
    """Convert natural language to MDX or SQL, execute, and return results."""
    import asyncio
    loop = asyncio.get_running_loop()

    if req.source == "sql":
        result = await loop.run_in_executor(None, _run_sql_query, req.question, req.execute, req.limit)
        return result

    if req.source == "tm1":
        result = await loop.run_in_executor(None, _run_tm1_query, req.question)
        return result

    # Auto: try TM1 first, fall back to SQL
    try:
        result = await loop.run_in_executor(None, _run_tm1_query, req.question)
        if result.get("mdx") and not result.get("error"):
            return result
    except Exception:
        pass

    result = await loop.run_in_executor(None, _run_sql_query, req.question, req.execute, req.limit)
    return result


def _run_tm1_query(question: str) -> dict:
    try:
        from mcp_server.skills.mcp_bridge import tm1_build_report
        return tm1_build_report(question)
    except Exception as e:
        return {"error": str(e), "source": "tm1"}


def _run_sql_query(question: str, execute: bool, limit: int) -> dict:
    try:
        from mcp_server.skills.mcp_bridge import sql_build_query
        return sql_build_query(question, execute=execute, limit=limit)
    except Exception as e:
        return {"error": str(e), "source": "sql"}


# --- Server -------------------------------------------------------------------

@router.get("/server")
async def server_info():
    from mcp_server.skills.tm1_management import tm1_get_server_info
    return tm1_get_server_info()


@router.get("/connections")
async def test_connections():
    """Test TM1, PostgreSQL (klikk_financials_db + klikk_bi_etl), and list loaded MCP skill modules."""
    from mcp_server.skills.validation import test_tm1_connection, test_postgres_connections
    from tool_registry import _SKILL_MODULES
    return {
        "tm1": test_tm1_connection(),
        "postgres": test_postgres_connections(),
        "mcp_skills": [m.__name__.split(".")[-1] for m in _SKILL_MODULES],
    }
