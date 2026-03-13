"""
KPI REST API endpoints — wraps existing KPI monitor functions.
"""
from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter()


@router.get("/")
async def list_kpis():
    from mcp_server.skills.kpi_monitor import list_kpi_definitions
    return list_kpi_definitions()


@router.get("/values")
async def get_kpi_values(year: str = "", month: str = ""):
    from mcp_server.skills.kpi_monitor import get_all_kpi_values
    return get_all_kpi_values(year=year, month=month)


class KPICreateRequest(BaseModel):
    kpi_id: str
    name: str
    category: str
    description: str = ""
    source_type: str
    source_params: dict = {}
    kpi_format: str = "number"
    thresholds: dict | None = None


@router.post("/")
async def add_kpi(req: KPICreateRequest):
    from mcp_server.skills.kpi_monitor import add_kpi_definition
    return add_kpi_definition(
        kpi_id=req.kpi_id,
        name=req.name,
        category=req.category,
        description=req.description,
        source_type=req.source_type,
        source_params=req.source_params,
        kpi_format=req.kpi_format,
        thresholds=req.thresholds,
        confirm=True,
    )


@router.delete("/{kpi_id}")
async def remove_kpi(kpi_id: str):
    from mcp_server.skills.kpi_monitor import remove_kpi_definition
    return remove_kpi_definition(kpi_id, confirm=True)
