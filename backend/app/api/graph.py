from fastapi import APIRouter, HTTPException, Body
from app.graph.falkor_client import falkor_client
from app.schema.registry import schema_registry

router = APIRouter()

@router.get("/graph-data")
async def get_graph_data():
    """
    Returns nodes and edges from FalkorDB graph for frontend graph visualization.
    """
    return falkor_client.get_all_nodes_and_edges()

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
