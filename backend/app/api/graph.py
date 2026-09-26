from typing import Optional, Dict, Any
from fastapi import APIRouter, HTTPException, Body, Query
from graph.falkordb import falkor_client
from app.schema.registry import schema_registry

router = APIRouter()

@router.get("/graph-data")
async def get_graph_data(domain: Optional[str] = Query(None)):
    """
    Returns nodes and edges from FalkorDB graph for frontend graph visualization.
    Domain parameter can be 'invoice', 'medical', 'all', or None.
    """
    return falkor_client.get_all_nodes_and_edges(graph_name=domain)

@router.get("/schemas")
async def get_schemas():
    """
    Returns all registered graph schema templates (invoice, medical_bill, discharge_summary).
    """
    return schema_registry.get_all_schemas()

@router.post("/schemas/{schema_key}")
async def update_schema(schema_key: str, payload: dict = Body(...)):
    """
    Registers or updates a dynamic graph schema template.
    """
    schema_registry.register_schema(schema_key, payload)
    return {"status": "success", "message": f"Schema '{schema_key}' updated successfully."}

@router.post("/reset-graph")
async def reset_graph(domain: Optional[str] = Query("all")):
    """
    Clears old graph nodes and edges in FalkorDB to allow clean connected re-ingestion.
    """
    if domain == "all":
        falkor_client.delete_graph("medical_graph")
        falkor_client.delete_graph("invoice_graph")
        return {"status": "success", "message": "All domain graphs reset successfully."}
    else:
        falkor_client.delete_graph(domain)
        return {"status": "success", "message": f"Graph '{domain}' reset successfully."}
