import os
import glob
from typing import Dict, Any, List
from fastapi import APIRouter, HTTPException, Body
from app.graph.builder import cypher_builder
from app.ocr.docling_parser import doc_parser
from app.ocr.extractor import entity_extractor

router = APIRouter()

@router.post("/ingest-graph")
async def ingest_graph(payload: Dict[str, Any] = Body(...)):
    """
    Ingests extracted nodes and relationships into FalkorDB.
    """
    graph_data = payload.get("graph", payload)
    if not graph_data or not isinstance(graph_data, dict):
        raise HTTPException(status_code=400, detail="Invalid payload. Must contain 'nodes' and 'relationships'.")

    result = cypher_builder.ingest_graph_data(graph_data)
    return result

@router.post("/batch-ingest")
async def batch_ingest(payload: Dict[str, Any] = Body(...)):
    """
    Batch processes dataset images from the project 'data/' directory.
    """
    target_category = payload.get("category", "Invoice")  # "Invoice", "Medical/bills", or "Medical/discharge_summaries"
    max_count = int(payload.get("max_count", 5))

    base_data_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../data"))
    target_dir = os.path.join(base_data_dir, target_category)

    if not os.path.exists(target_dir):
        raise HTTPException(status_code=404, detail=f"Directory not found: {target_dir}")

    image_files = glob.glob(os.path.join(target_dir, "*.jpg")) + glob.glob(os.path.join(target_dir, "*.png"))
    image_files = image_files[:max_count]

    domain_key = "invoice"
    if "bill" in target_category.lower():
        domain_key = "medical_bill"
    elif "discharge" in target_category.lower():
        domain_key = "discharge_summary"

    processed = []
    total_nodes = 0
    total_rels = 0

    for img_path in image_files:
        try:
            filename = os.path.basename(img_path)
            # 1. Parse OCR
            parsed = doc_parser.parse_document(img_path)
            raw_text = parsed.get("raw_text", "")
            
            # 2. Extract Entities
            graph_data = entity_extractor.extract_graph(raw_text, domain_key)
            
            # 3. Ingest into FalkorDB
            ingest_res = cypher_builder.ingest_graph_data(graph_data)

            processed.append({
                "filename": filename,
                "status": "success",
                "nodes": ingest_res.get("nodes_ingested", 0),
                "relationships": ingest_res.get("relationships_ingested", 0)
            })
            total_nodes += ingest_res.get("nodes_ingested", 0)
            total_rels += ingest_res.get("relationships_ingested", 0)
        except Exception as e:
            processed.append({
                "filename": os.path.basename(img_path),
                "status": "error",
                "error": str(e)
            })

    return {
        "status": "completed",
        "category": target_category,
        "processed_count": len(processed),
        "total_nodes_ingested": total_nodes,
        "total_relationships_ingested": total_rels,
        "details": processed
    }
