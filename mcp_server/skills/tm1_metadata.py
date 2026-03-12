"""
Skill: TM1 Metadata Explorer
Read-only tools for exploring model structure: dimensions, cubes, processes, rules.
"""
from __future__ import annotations

import sys
import os
from typing import Any

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
from config import TM1_CONFIG
from TM1py import TM1Service


def tm1_list_dimensions() -> dict[str, Any]:
    """
    Return all user dimension names (excludes system dimensions starting with }).
    """
    try:
        with TM1Service(**TM1_CONFIG) as tm1:
            all_dims = tm1.dimensions.get_all_names()
        user_dims = [d for d in all_dims if not d.startswith("}")]
        return {"dimensions": sorted(user_dims), "count": len(user_dims)}
    except Exception as e:
        return {"error": str(e)}


def tm1_list_cubes() -> dict[str, Any]:
    """
    Return all user cubes with their dimension lists and whether they have rules.
    Excludes system cubes starting with }.
    """
    try:
        with TM1Service(**TM1_CONFIG) as tm1:
            all_names = tm1.cubes.get_all_names()
            result = []
            for name in sorted(all_names):
                if name.startswith("}"):
                    continue
                cube = tm1.cubes.get(name)
                result.append({
                    "name": name,
                    "dimensions": cube.dimensions,
                    "has_rules": cube.has_rules,
                })
        return {"cubes": result, "count": len(result)}
    except Exception as e:
        return {"error": str(e)}


def tm1_get_dimension_elements(
    dimension_name: str,
    hierarchy_name: str = "",
    element_type: str = "all",
    limit: int = 200,
) -> dict[str, Any]:
    """
    Return elements of a TM1 dimension.

    dimension_name: Exact dimension name, e.g. 'account'
    hierarchy_name: Named hierarchy, e.g. 'Grouping'. Leave empty for default (same as dim name).
    element_type: 'all', 'leaf' (N elements only), or 'consolidated' (C elements only).
    limit: Max elements to return (default 200).
    """
    hier = hierarchy_name if hierarchy_name else dimension_name
    try:
        with TM1Service(**TM1_CONFIG) as tm1:
            elements = tm1.elements.get_elements(dimension_name, hier)
        result = []
        for el in elements:
            et = el.element_type.value
            if element_type == "leaf" and et != "Numeric":
                continue
            if element_type == "consolidated" and et != "Consolidated":
                continue
            result.append({"name": el.name, "element_type": et})
            if len(result) >= limit:
                break
        return {
            "dimension": dimension_name,
            "hierarchy": hier,
            "elements": result,
            "returned": len(result),
            "truncated": len(result) >= limit,
        }
    except Exception as e:
        return {"error": str(e)}


def tm1_get_element_attributes(dimension_name: str) -> dict[str, Any]:
    """
    List all element attributes defined for a dimension (names and types).

    dimension_name: Exact dimension name, e.g. 'account'
    """
    try:
        with TM1Service(**TM1_CONFIG) as tm1:
            attrs = tm1.elements.get_element_attributes(dimension_name, dimension_name)
        result = [{"name": a.name, "attribute_type": a.attribute_type} for a in attrs]
        return {"dimension": dimension_name, "attributes": result}
    except Exception as e:
        return {"error": str(e)}


def tm1_get_element_attribute_value(
    dimension_name: str, element_name: str, attribute_name: str
) -> dict[str, Any]:
    """
    Read a single element attribute value.

    dimension_name: e.g. 'account'
    element_name: e.g. 'acc_001'
    attribute_name: e.g. 'cashflow_category'
    """
    try:
        with TM1Service(**TM1_CONFIG) as tm1:
            value = tm1.elements.get_attribute_value(
                dimension_name=dimension_name,
                hierarchy_name=dimension_name,
                element_name=element_name,
                attribute_name=attribute_name,
            )
        return {
            "dimension": dimension_name,
            "element": element_name,
            "attribute": attribute_name,
            "value": value,
        }
    except Exception as e:
        return {"error": str(e)}


def tm1_list_processes() -> dict[str, Any]:
    """
    Return all custom TI process names with datasource type and parameter signatures.
    Excludes Bedrock (}bedrock prefix) and other system processes.
    """
    try:
        with TM1Service(**TM1_CONFIG) as tm1:
            names = tm1.processes.get_all_names()
            result = []
            for name in sorted(names):
                if name.startswith("}"):
                    continue
                proc = tm1.processes.get(name)
                params = [
                    {"name": p.name, "prompt": p.prompt, "default": str(p.value)}
                    for p in proc.parameters
                ]
                result.append({
                    "name": name,
                    "datasource_type": proc.datasource_type,
                    "parameters": params,
                })
        return {"processes": result, "count": len(result)}
    except Exception as e:
        return {"error": str(e)}


def tm1_get_process_code(process_name: str) -> dict[str, Any]:
    """
    Return the full TI process code (prolog, metadata, data, epilog procedures).

    process_name: Exact process name, e.g. 'cub.gl_src_trial_balance.import'
    """
    try:
        with TM1Service(**TM1_CONFIG) as tm1:
            proc = tm1.processes.get(process_name)
        return {
            "name": process_name,
            "datasource_type": proc.datasource_type,
            "parameters": [
                {"name": p.name, "prompt": p.prompt, "value": str(p.value)}
                for p in proc.parameters
            ],
            "prolog_procedure": proc.prolog_procedure,
            "metadata_procedure": proc.metadata_procedure,
            "data_procedure": proc.data_procedure,
            "epilog_procedure": proc.epilog_procedure,
        }
    except Exception as e:
        return {"error": str(e)}


def tm1_get_cube_rules(cube_name: str) -> dict[str, Any]:
    """
    Return the rules text for a cube.

    cube_name: Exact cube name, e.g. 'gl_pln_forecast'
    """
    try:
        with TM1Service(**TM1_CONFIG) as tm1:
            cube = tm1.cubes.get(cube_name)
            rules_text = cube.rules.text if cube.has_rules else ""
        return {
            "cube": cube_name,
            "has_rules": cube.has_rules,
            "rules_text": rules_text,
        }
    except Exception as e:
        return {"error": str(e)}


def tm1_get_hierarchy(dimension_name: str, hierarchy_name: str = "") -> dict[str, Any]:
    """
    Return the parent-child structure of a named hierarchy.

    dimension_name: e.g. 'account'
    hierarchy_name: e.g. 'Grouping'. Leave empty to use the default (same as dim name).
    """
    hier = hierarchy_name if hierarchy_name else dimension_name
    try:
        with TM1Service(**TM1_CONFIG) as tm1:
            hierarchy = tm1.hierarchies.get(dimension_name, hier)
        edges = []
        for el in hierarchy.elements.values():
            for child_name, weight in el.components.items():
                edges.append({"parent": el.name, "child": child_name, "weight": weight})
        return {
            "dimension": dimension_name,
            "hierarchy": hier,
            "edges": edges[:500],
            "truncated": len(edges) > 500,
        }
    except Exception as e:
        return {"error": str(e)}


# --- Tool schemas ---

TOOL_SCHEMAS = [
    {
        "name": "tm1_list_dimensions",
        "description": "Return all user dimension names in the TM1 model (excludes system dimensions).",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "tm1_list_cubes",
        "description": "Return all user cubes with their dimension lists and whether they have rules.",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "tm1_get_dimension_elements",
        "description": "Return elements of a TM1 dimension. Can filter to leaf (N) or consolidated (C) elements.",
        "input_schema": {
            "type": "object",
            "properties": {
                "dimension_name": {"type": "string", "description": "Exact dimension name, e.g. 'account'"},
                "hierarchy_name": {"type": "string", "description": "Named hierarchy e.g. 'Grouping'. Leave empty for default."},
                "element_type": {"type": "string", "description": "'all', 'leaf', or 'consolidated'"},
                "limit": {"type": "integer", "description": "Max elements to return (default 200)"},
            },
            "required": ["dimension_name"],
        },
    },
    {
        "name": "tm1_get_element_attributes",
        "description": "List all element attributes defined for a dimension (names and types).",
        "input_schema": {
            "type": "object",
            "properties": {
                "dimension_name": {"type": "string", "description": "Exact dimension name"},
            },
            "required": ["dimension_name"],
        },
    },
    {
        "name": "tm1_get_element_attribute_value",
        "description": "Read a single element attribute value, e.g. get the cashflow_category attribute for account 'acc_001'.",
        "input_schema": {
            "type": "object",
            "properties": {
                "dimension_name": {"type": "string"},
                "element_name": {"type": "string"},
                "attribute_name": {"type": "string"},
            },
            "required": ["dimension_name", "element_name", "attribute_name"],
        },
    },
    {
        "name": "tm1_list_processes",
        "description": "Return all custom TI process names with parameter signatures (excludes Bedrock/system processes).",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "tm1_get_process_code",
        "description": "Return the full TI process code (prolog, metadata, data, epilog) for a named process.",
        "input_schema": {
            "type": "object",
            "properties": {
                "process_name": {"type": "string", "description": "Exact process name, e.g. 'cub.gl_src_trial_balance.import'"},
            },
            "required": ["process_name"],
        },
    },
    {
        "name": "tm1_get_cube_rules",
        "description": "Return the TM1 rules text for a cube.",
        "input_schema": {
            "type": "object",
            "properties": {
                "cube_name": {"type": "string", "description": "Exact cube name, e.g. 'gl_pln_forecast'"},
            },
            "required": ["cube_name"],
        },
    },
    {
        "name": "tm1_get_hierarchy",
        "description": "Return the parent-child structure of a named hierarchy within a dimension.",
        "input_schema": {
            "type": "object",
            "properties": {
                "dimension_name": {"type": "string", "description": "e.g. 'account'"},
                "hierarchy_name": {"type": "string", "description": "e.g. 'Grouping'. Leave empty for default."},
            },
            "required": ["dimension_name"],
        },
    },
]

TOOL_FUNCTIONS = {
    "tm1_list_dimensions": tm1_list_dimensions,
    "tm1_list_cubes": tm1_list_cubes,
    "tm1_get_dimension_elements": tm1_get_dimension_elements,
    "tm1_get_element_attributes": tm1_get_element_attributes,
    "tm1_get_element_attribute_value": tm1_get_element_attribute_value,
    "tm1_list_processes": tm1_list_processes,
    "tm1_get_process_code": tm1_get_process_code,
    "tm1_get_cube_rules": tm1_get_cube_rules,
    "tm1_get_hierarchy": tm1_get_hierarchy,
}
