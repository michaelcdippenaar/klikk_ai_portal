"""
Skill: TM1 Management
Write operations: run TI processes, write cell values, update element attributes.
ALL write operations require confirm=True to execute.
Without confirm=True, they return a dry-run preview and do nothing.
"""
from __future__ import annotations

import sys
import os
from typing import Any

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
from config import TM1_CONFIG
from TM1py import TM1Service


def tm1_run_process(
    process_name: str,
    parameters: dict | None = None,
    confirm: bool = False,
) -> dict[str, Any]:
    """
    Execute a TI process on the TM1 server.
    Set confirm=True to actually run. Without it, returns a dry-run preview.

    process_name: Exact process name, e.g. 'cub.gl_src_trial_balance.import'
    parameters: Dict of parameter name -> value, e.g. {"pYear": "2025", "pMonth": "Jul"}
    confirm: Must be True to execute. Default False (safe dry-run).
    """
    params = parameters or {}
    if not confirm:
        return {
            "status": "dry_run",
            "process_name": process_name,
            "parameters": params,
            "message": "Dry run only. Set confirm=True to actually execute this process.",
        }
    try:
        with TM1Service(**TM1_CONFIG) as tm1:
            success, status, _ = tm1.processes.execute_with_return(
                process_name=process_name,
                **{k: v for k, v in params.items()},
            )
        return {
            "status": "success" if success else "failed",
            "process_name": process_name,
            "parameters": params,
            "tm1_status": status,
        }
    except Exception as e:
        return {"status": "error", "process_name": process_name, "error": str(e)}


def tm1_write_cell(
    cube_name: str,
    coordinates: list,
    value: float,
    confirm: bool = False,
) -> dict[str, Any]:
    """
    Write a value to a single cell in a TM1 cube.
    Set confirm=True to actually write. Without it, returns a dry-run preview.

    cube_name: Exact cube name.
    coordinates: Ordered element names, one per cube dimension.
    value: Numeric value to write.
    confirm: Must be True to write. Default False.
    """
    if not confirm:
        return {
            "status": "dry_run",
            "cube": cube_name,
            "coordinates": coordinates,
            "value": value,
            "message": "Dry run only. Set confirm=True to write.",
        }
    try:
        with TM1Service(**TM1_CONFIG) as tm1:
            tm1.cells.write_value(
                value=value,
                cube_name=cube_name,
                element_tuple=coordinates,
            )
        return {
            "status": "success",
            "cube": cube_name,
            "coordinates": coordinates,
            "value": value,
        }
    except Exception as e:
        return {"status": "error", "error": str(e)}


def tm1_update_element_attribute(
    dimension_name: str,
    element_name: str,
    attribute_name: str,
    value: str,
    confirm: bool = False,
) -> dict[str, Any]:
    """
    Update a single element attribute value.
    Set confirm=True to actually update.

    dimension_name: e.g. 'account'
    element_name: e.g. 'acc_001'
    attribute_name: e.g. 'cashflow_category'
    value: New value (string; TM1 will cast numeric attributes automatically).
    confirm: Must be True to write.
    """
    if not confirm:
        return {
            "status": "dry_run",
            "dimension": dimension_name,
            "element": element_name,
            "attribute": attribute_name,
            "new_value": value,
            "message": "Dry run only. Set confirm=True to update.",
        }
    try:
        with TM1Service(**TM1_CONFIG) as tm1:
            tm1.elements.update_element_attribute(
                dimension_name=dimension_name,
                hierarchy_name=dimension_name,
                element_name=element_name,
                attribute_name=attribute_name,
                value=value,
            )
        return {
            "status": "success",
            "dimension": dimension_name,
            "element": element_name,
            "attribute": attribute_name,
            "new_value": value,
        }
    except Exception as e:
        return {"status": "error", "error": str(e)}


def tm1_get_server_info() -> dict[str, Any]:
    """
    Return TM1 server information: version, active users, last data update.
    No confirmation required — read-only.
    """
    try:
        with TM1Service(**TM1_CONFIG) as tm1:
            info = tm1.server.get_server_name()
            active = tm1.monitoring.get_active_session_count()
        return {"server_name": info, "active_sessions": active}
    except Exception as e:
        return {"error": str(e)}


# --- Tool schemas ---

TOOL_SCHEMAS = [
    {
        "name": "tm1_run_process",
        "description": (
            "Execute a TI process on the TM1 server. "
            "IMPORTANT: set confirm=True to actually run. Without it this is a safe dry-run preview."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "process_name": {"type": "string", "description": "Exact process name, e.g. 'cub.gl_src_trial_balance.import'"},
                "parameters": {
                    "type": "object",
                    "description": "Parameter name->value dict, e.g. {\"pYear\": \"2025\", \"pMonth\": \"Jul\"}",
                    "additionalProperties": {"type": "string"},
                },
                "confirm": {"type": "boolean", "description": "Must be true to actually execute. Default false."},
            },
            "required": ["process_name"],
        },
    },
    {
        "name": "tm1_write_cell",
        "description": (
            "Write a numeric value to a single TM1 cube cell. "
            "IMPORTANT: set confirm=True to actually write."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "cube_name": {"type": "string"},
                "coordinates": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Ordered element names matching cube dimension order",
                },
                "value": {"type": "number", "description": "Numeric value to write"},
                "confirm": {"type": "boolean", "description": "Must be true to write"},
            },
            "required": ["cube_name", "coordinates", "value"],
        },
    },
    {
        "name": "tm1_update_element_attribute",
        "description": (
            "Update a TM1 element attribute value. "
            "IMPORTANT: set confirm=True to actually update."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "dimension_name": {"type": "string"},
                "element_name": {"type": "string"},
                "attribute_name": {"type": "string"},
                "value": {"type": "string", "description": "New attribute value"},
                "confirm": {"type": "boolean", "description": "Must be true to update"},
            },
            "required": ["dimension_name", "element_name", "attribute_name", "value"],
        },
    },
    {
        "name": "tm1_get_server_info",
        "description": "Return TM1 server name and active session count.",
        "input_schema": {"type": "object", "properties": {}},
    },
]

TOOL_FUNCTIONS = {
    "tm1_run_process": tm1_run_process,
    "tm1_write_cell": tm1_write_cell,
    "tm1_update_element_attribute": tm1_update_element_attribute,
    "tm1_get_server_info": tm1_get_server_info,
}
