"""
Skill: TM1 Data Query
Read-only tools for querying cube data via MDX and named views.
"""
from __future__ import annotations

import sys
import os
from typing import Any

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
from config import TM1_CONFIG
from TM1py import TM1Service


def tm1_query_mdx(mdx: str, top: int = 1000) -> dict[str, Any]:
    """
    Execute an MDX SELECT statement and return cell data.
    Use this for complex multi-dimensional queries.

    mdx: Full MDX statement, e.g.:
         "SELECT {[version].[actual]} ON 0, {[account].[All_Account].Children} ON 1
          FROM [gl_src_trial_balance]
          WHERE ([year].[2025],[month].[Jul],[entity].[All_Entity],
                 [contact].[All_Contact],[tracking_1].[All_Tracking_1],
                 [tracking_2].[All_Tracking_2],[measure_gl_src_trial_balance].[amount])"
    top: Max rows to return. Default 1000.
    """
    try:
        with TM1Service(**TM1_CONFIG) as tm1:
            cells = tm1.cells.execute_mdx(mdx, top=top)
        result = [{"coordinates": list(k), "value": v} for k, v in cells.items()]
        return {"cells": result, "row_count": len(result)}
    except Exception as e:
        return {"error": str(e)}


def tm1_execute_mdx_rows(mdx: str, top: int = 500) -> dict[str, Any]:
    """
    Execute an MDX query and return results as a table (headers + rows).
    Better for displaying tabular data than tm1_query_mdx.

    mdx: Full MDX SELECT statement.
    top: Max rows. Default 500.
    """
    try:
        with TM1Service(**TM1_CONFIG) as tm1:
            df = tm1.cells.execute_mdx_dataframe(mdx=mdx)
        if df is None or len(df) == 0:
            return {"headers": [], "rows": [], "row_count": 0}
        return {
            "headers": list(df.columns),
            "rows": df.head(top).values.tolist(),
            "row_count": len(df),
        }
    except Exception as e:
        return {"error": str(e)}


def tm1_read_view(cube_name: str, view_name: str) -> dict[str, Any]:
    """
    Read data from a named public view in a TM1 cube.

    cube_name: Exact cube name, e.g. 'gl_src_trial_balance'
    view_name: Exact view name, e.g. 'ops_gl_import_check'
    """
    try:
        with TM1Service(**TM1_CONFIG) as tm1:
            cells = tm1.cells.execute_view(
                cube_name=cube_name,
                view_name=view_name,
                private=False,
            )
        result = [{"coordinates": list(k), "value": v} for k, v in cells.items()]
        return {"cube": cube_name, "view": view_name, "cells": result, "row_count": len(result)}
    except Exception as e:
        return {"error": str(e)}


def tm1_get_cell_value(cube_name: str, coordinates: list) -> dict[str, Any]:
    """
    Read a single cell value from a TM1 cube by coordinate.

    cube_name: Exact cube name.
    coordinates: Ordered list of element names, one per cube dimension.
      Example for gl_src_trial_balance (9 dims):
      ["2025","Jul","actual","Klikk_Org","acc_001","All_Contact","All_Tracking_1","All_Tracking_2","amount"]
    """
    try:
        with TM1Service(**TM1_CONFIG) as tm1:
            value = tm1.cells.get_value(
                cube_name=cube_name,
                elements=",".join(str(c) for c in coordinates),
            )
        return {"cube": cube_name, "coordinates": coordinates, "value": value}
    except Exception as e:
        return {"error": str(e)}


def tm1_list_views(cube_name: str) -> dict[str, Any]:
    """
    List all public views for a given cube.

    cube_name: Exact cube name, e.g. 'cashflow_pln_forecast'
    """
    try:
        with TM1Service(**TM1_CONFIG) as tm1:
            views = tm1.views.get_all(cube_name=cube_name)
        names = [v.name for v in views]
        return {"cube": cube_name, "views": names, "count": len(names)}
    except Exception as e:
        return {"error": str(e)}


# --- Tool schemas for Anthropic Claude tool_use ---

TOOL_SCHEMAS = [
    {
        "name": "tm1_query_mdx",
        "description": "Execute an MDX SELECT statement against the TM1 model and return cell data. Use for complex multi-dimensional queries.",
        "input_schema": {
            "type": "object",
            "properties": {
                "mdx": {"type": "string", "description": "Full MDX SELECT statement"},
                "top": {"type": "integer", "description": "Max rows to return (default 1000)"},
            },
            "required": ["mdx"],
        },
    },
    {
        "name": "tm1_execute_mdx_rows",
        "description": "Execute an MDX query and return results as a table with column headers and rows. Better for displaying data than tm1_query_mdx.",
        "input_schema": {
            "type": "object",
            "properties": {
                "mdx": {"type": "string", "description": "Full MDX SELECT statement"},
                "top": {"type": "integer", "description": "Max rows (default 500)"},
            },
            "required": ["mdx"],
        },
    },
    {
        "name": "tm1_read_view",
        "description": "Read data from a named public TM1 view.",
        "input_schema": {
            "type": "object",
            "properties": {
                "cube_name": {"type": "string", "description": "Exact cube name e.g. 'gl_src_trial_balance'"},
                "view_name": {"type": "string", "description": "Exact view name e.g. 'ops_gl_import_check'"},
            },
            "required": ["cube_name", "view_name"],
        },
    },
    {
        "name": "tm1_get_cell_value",
        "description": "Read a single cell value from a TM1 cube by coordinate tuple.",
        "input_schema": {
            "type": "object",
            "properties": {
                "cube_name": {"type": "string", "description": "Exact cube name"},
                "coordinates": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Ordered element names, one per cube dimension",
                },
            },
            "required": ["cube_name", "coordinates"],
        },
    },
    {
        "name": "tm1_list_views",
        "description": "List all public views available for a given cube.",
        "input_schema": {
            "type": "object",
            "properties": {
                "cube_name": {"type": "string", "description": "Exact cube name"},
            },
            "required": ["cube_name"],
        },
    },
]

TOOL_FUNCTIONS = {
    "tm1_query_mdx": tm1_query_mdx,
    "tm1_execute_mdx_rows": tm1_execute_mdx_rows,
    "tm1_read_view": tm1_read_view,
    "tm1_get_cell_value": tm1_get_cell_value,
    "tm1_list_views": tm1_list_views,
}
