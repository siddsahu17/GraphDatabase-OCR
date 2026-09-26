import os
import shutil
import tempfile
from typing import List
from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from pipeline.orchestrator import pipeline_orchestrator
from common.logger import get_logger

logger = get_logger(__name__)
router = APIRouter()
TEMP_DIR = tempfile.gettempdir()

@router.post("/process-images")
async def process_images(
    files: List[UploadFile] = File(...),
    domain: str = Form("invoice")
):
    """
    Processes multiple uploaded document files via canonical PipelineOrchestrator:
    1. Runs OCR Cascade (pypdf / docling / OpenCV preprocessing + Tesseract).
    2. Runs Entity Alignment & Resolution.
    3. Builds Graph Nodes & Edges for domain graph.
    4. Returns aggregated JSON graph preview for frontend drag-and-drop UI.
    """
    if not files:
        raise HTTPException(status_code=400, detail="No files uploaded.")

    combined_nodes = []
    combined_rels = []
    file_results = []
    combined_text = []

    for file in files:
        if not file.filename:
            continue

        temp_path = os.path.join(TEMP_DIR, f"upload_{file.filename}")
        try:
            with open(temp_path, "wb") as buffer:
                shutil.copyfileobj(file.file, buffer)

            # Process document through canonical PipelineOrchestrator
            ctx = pipeline_orchestrator.process_document(
                file_path=temp_path,
                domain=domain
            )

            ocr_txt = ""
            if ctx.ocr_result:
                ocr_txt = ctx.ocr_result.full_text or ctx.ocr_result.normalized_text or f"Document File: {file.filename}"
            else:
                ocr_txt = f"Document File: {file.filename}"

            combined_text.append(f"--- File: {file.filename} ---\n{ocr_txt}")

            nodes = [
                {
                    "id": n.id,
                    "label": n.label,
                    "properties": n.properties
                }
                for n in ctx.graph_nodes
            ]
            rels = [
                {
                    "from_id": e.from_id,
                    "from_label": e.from_label,
                    "type": e.type,
                    "to_id": e.to_id,
                    "to_label": e.to_label
                }
                for e in ctx.graph_edges
            ]

            combined_nodes.extend(nodes)
            combined_rels.extend(rels)

            file_results.append({
                "filename": file.filename,
                "document_id": ctx.document_id,
                "status": ctx.status,
                "nodes_count": len(nodes),
                "rels_count": len(rels),
                "parser": ctx.ocr_result.engine_used if ctx.ocr_result else "fallback"
            })
        except Exception as e:
            logger.error(f"Error processing uploaded file '{file.filename}': {e}")
            file_results.append({
                "filename": file.filename,
                "error": str(e)
            })
        finally:
            if os.path.exists(temp_path):
                try:
                    os.remove(temp_path)
                except Exception:
                    pass

    return {
        "status": "success",
        "domain": domain,
        "files_processed": len(file_results),
        "file_details": file_results,
        "parsed_text": "\n\n".join(combined_text),
        "graph": {
            "nodes": combined_nodes,
            "relationships": combined_rels
        }
    }

@router.post("/process-image")
async def process_image(
    file: UploadFile = File(...),
    domain: str = Form("invoice")
):
    return await process_images(files=[file], domain=domain)
