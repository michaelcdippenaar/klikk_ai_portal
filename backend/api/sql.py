"""
SQL Explorer API — read-only SQL access for the frontend SQLEditor widget.
Proxies to the same PostgreSQL databases as the agent's postgres_query skill.
"""
from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from mcp_server.skills.postgres_query import (
    pg_query_financials,
    pg_list_tables,
    pg_describe_table,
)

router = APIRouter()


class SQLRequest(BaseModel):
    database: str = "financials"  # "financials" or "bi"
    sql: str
    limit: int = 200


@router.get("/databases")
async def list_databases():
    """List available databases."""
    return {
        "databases": [
            {"id": "financials", "name": "klikk_financials_v4", "description": "Xero GL, investments, Investec portfolio"},
            {"id": "bi", "name": "klikk_bi_etl", "description": "BI ETL metrics, RAG vectors"},
        ]
    }


@router.get("/tables/{database}")
async def list_tables(database: str):
    """List tables in a database with row counts."""
    result = pg_list_tables(database)
    if "error" in result:
        return result
    return result


@router.get("/tables/{database}/{table_name}/columns")
async def describe_table(database: str, table_name: str):
    """Get column schema for a table."""
    result = pg_describe_table(database, table_name)
    if "error" in result:
        return result
    return result


@router.post("/execute")
async def execute_sql(req: SQLRequest):
    """Execute a read-only SQL query."""
    func = pg_query_financials
    result = func(req.sql, min(req.limit, 1000))
    return result
