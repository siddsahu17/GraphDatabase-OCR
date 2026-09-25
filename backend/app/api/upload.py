import os
import shutil
import tempfile
from typing import List
from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from app.ocr.docling_parser import doc_parser
from app.ocr.extractor import entity_extractor

router = APIRouter()

TEMP_DIR = tempfile.gettempdir()

@router.post("/process-images")
async def process_images(
    files: List[UploadFile] = File(...),
    domain: str = Form("invoice")
):
    """
    Processes multiple uploaded image files:
    1. Runs Docling layout & text extraction on each file.
    2. Runs Entity Extraction to build combined Nodes and Relationships graph schema.
    3. Returns aggregated JSON graph preview.
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

            # 1. Parse image using Docling
            ocr_result = doc_parser.parse_document(temp_path)
            raw_text = ocr_result.get("raw_text", "")
            combined_text.append(f"--- File: {file.filename} ---\n{raw_text}")

            # 2. Extract Graph Entities
            extracted_graph = entity_extractor.extract_graph(raw_text, domain)
            
            nodes = extracted_graph.get("nodes", [])
            rels = extracted_graph.get("relationships", [])

            combined_nodes.extend(nodes)
            combined_rels.extend(rels)

            file_results.append({
                "filename": file.filename,
                "nodes_count": len(nodes),
                "rels_count": len(rels),
                "parser": ocr_result.get("parser")
            })
        except Exception as e:
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
    res = await process_images(files=[file], domain=domain)
    return res
