"""
Skill: PostgreSQL Source Data Query
Read-only SQL access to klikk_financials_v4 (Xero GL data) and klikk_bi_etl (BI metrics).
Only SELECT statements are permitted.
"""
from __future__ import annotations

import sys
import os
import re
from typing import Any

import psycopg2
import psycopg2.extras

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
from config import settings

_FINANCIALS_DSN = dict(
    host=settings.pg_financials_host,
    port=settings.pg_financials_port,
    dbname=settings.pg_financials_db,
    user=settings.pg_financials_user,
    password=settings.pg_financials_password,
)

_BI_DSN = dict(
    host=settings.pg_bi_host,
    port=settings.pg_bi_port,
    dbname=settings.pg_bi_db,
    user=settings.pg_bi_user,
    password=settings.pg_bi_password,
)


def _is_select_only(sql: str) -> bool:
    stripped = sql.strip().lstrip("(").upper()
    return stripped.startswith("SELECT") or stripped.startswith("WITH")


def _run_query(dsn: dict, sql: str, limit: int = 100) -> dict[str, Any]:
    if not _is_select_only(sql):
        return {"error": "Only SELECT queries are permitted on PostgreSQL source databases."}
    try:
        with psycopg2.connect(**dsn) as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
                cur.execute(sql)
                rows = cur.fetchmany(limit)
                headers = [desc[0] for desc in cur.description] if cur.description else []
                return {
                    "headers": headers,
                    "rows": [list(r) for r in rows],
                    "row_count": len(rows),
                    "truncated": len(rows) >= limit,
                }
    except Exception as e:
        return {"error": str(e)}


def pg_query_financials(sql: str, limit: int = 100) -> dict[str, Any]:
    """
    Run a read-only SELECT query against klikk_financials_v4 (Xero GL source data).
    Only SELECT statements permitted.

    sql: SQL SELECT statement. Avoid unbounded queries — use LIMIT.
    limit: Max rows to return (default 100, max 1000).
    """
    return _run_query(_FINANCIALS_DSN, sql, min(limit, 1000))


def pg_query_bi(sql: str, limit: int = 100) -> dict[str, Any]:
    """
    Run a read-only SELECT query against klikk_bi_etl (BI ETL metrics database).
    Only SELECT statements permitted.

    sql: SQL SELECT statement.
    limit: Max rows to return (default 100).
    """
    return _run_query(_BI_DSN, sql, min(limit, 1000))


def pg_list_tables(database: str) -> dict[str, Any]:
    """
    List all tables in a PostgreSQL database with their approximate row counts.

    database: 'financials' for klikk_financials_v4, or 'bi' for klikk_bi_etl.
    """
    dsn = _FINANCIALS_DSN if database == "financials" else _BI_DSN
    sql = """
        SELECT
            schemaname,
            tablename,
            pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) AS size,
            n_live_tup AS approx_rows
        FROM pg_stat_user_tables
        ORDER BY schemaname, tablename
    """
    return _run_query(dsn, sql, limit=200)


def pg_describe_table(database: str, table_name: str) -> dict[str, Any]:
    """
    Return column names and data types for a table.
    Use schema.table format if needed, e.g. 'public.xero_cube_xerotrailbalance'.

    database: 'financials' or 'bi'.
    table_name: Table name, optionally schema-qualified.
    """
    dsn = _FINANCIALS_DSN if database == "financials" else _BI_DSN
    # Parse optional schema prefix
    parts = table_name.split(".", 1)
    schema = parts[0] if len(parts) == 2 else "public"
    tname = parts[1] if len(parts) == 2 else parts[0]
    sql = """
        SELECT column_name, data_type, is_nullable, column_default
        FROM information_schema.columns
        WHERE table_schema = %s AND table_name = %s
        ORDER BY ordinal_position
    """
    try:
        with psycopg2.connect(**dsn) as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
                cur.execute(sql, (schema, tname))
                rows = cur.fetchall()
                headers = [desc[0] for desc in cur.description]
                return {
                    "table": table_name,
                    "database": database,
                    "headers": headers,
                    "rows": [list(r) for r in rows],
                    "column_count": len(rows),
                }
    except Exception as e:
        return {"error": str(e)}


def pg_get_xero_gl_sample(year: int, month: int, limit: int = 50) -> dict[str, Any]:
    """
    Fetch a sample of Xero GL trial balance entries for a given year and month.
    Useful for understanding what raw source data looks like.

    year: Calendar year, e.g. 2025
    month: Month number 1-12
    limit: Max rows (default 50)
    """
    sql = """
        SELECT year, month, organisation_id, account_code, account_name,
               contact_name, tracking_option_1, tracking_option_2,
               amount, balance_to_date
        FROM xero_cube_xerotrailbalance
        WHERE year = %(year)s AND month = %(month)s
        LIMIT %(limit)s
    """
    try:
        with psycopg2.connect(**_FINANCIALS_DSN) as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
                cur.execute(sql, {"year": year, "month": month, "limit": limit})
                rows = cur.fetchall()
                headers = [desc[0] for desc in cur.description]
                return {
                    "headers": headers,
                    "rows": [list(r) for r in rows],
                    "row_count": len(rows),
                    "year": year,
                    "month": month,
                }
    except Exception as e:
        return {"error": str(e)}


# --- Tool schemas ---

TOOL_SCHEMAS = [
    {
        "name": "pg_query_financials",
        "description": "Run a read-only SELECT query against klikk_financials_v4 (Xero GL source data). SELECT only.",
        "input_schema": {
            "type": "object",
            "properties": {
                "sql": {"type": "string", "description": "SELECT statement (use LIMIT to avoid large results)"},
                "limit": {"type": "integer", "description": "Max rows to return (default 100, max 1000)"},
            },
            "required": ["sql"],
        },
    },
    {
        "name": "pg_query_bi",
        "description": "Run a read-only SELECT query against klikk_bi_etl (BI ETL metrics). SELECT only.",
        "input_schema": {
            "type": "object",
            "properties": {
                "sql": {"type": "string", "description": "SELECT statement"},
                "limit": {"type": "integer", "description": "Max rows (default 100)"},
            },
            "required": ["sql"],
        },
    },
    {
        "name": "pg_list_tables",
        "description": "List all tables in klikk_financials_v4 or klikk_bi_etl with sizes and row counts.",
        "input_schema": {
            "type": "object",
            "properties": {
                "database": {"type": "string", "description": "'financials' for klikk_financials_v4, 'bi' for klikk_bi_etl"},
            },
            "required": ["database"],
        },
    },
    {
        "name": "pg_describe_table",
        "description": "Return column names and data types for a PostgreSQL table.",
        "input_schema": {
            "type": "object",
            "properties": {
                "database": {"type": "string", "description": "'financials' or 'bi'"},
                "table_name": {"type": "string", "description": "Table name, e.g. 'xero_cube_xerotrailbalance' or 'public.my_table'"},
            },
            "required": ["database", "table_name"],
        },
    },
    {
        "name": "pg_get_xero_gl_sample",
        "description": "Fetch a sample of Xero GL trial balance rows from PostgreSQL for a given year and month.",
        "input_schema": {
            "type": "object",
            "properties": {
                "year": {"type": "integer", "description": "Calendar year, e.g. 2025"},
                "month": {"type": "integer", "description": "Month number 1-12"},
                "limit": {"type": "integer", "description": "Max rows (default 50)"},
            },
            "required": ["year", "month"],
        },
    },
]

TOOL_FUNCTIONS = {
    "pg_query_financials": pg_query_financials,
    "pg_query_bi": pg_query_bi,
    "pg_list_tables": pg_list_tables,
    "pg_describe_table": pg_describe_table,
    "pg_get_xero_gl_sample": pg_get_xero_gl_sample,
}
