from typing import List, Optional, Dict, Any
from fastapi import APIRouter, HTTPException, UploadFile, File, Form, Query, Body, Response
from fastapi.responses import PlainTextResponse

from api.services.semi_structured_service import semi_structured_service

router = APIRouter(prefix="/semi-structured", tags=["Semi-Structured Ingestion"])

@router.get("/templates")
async def list_templates():
    return semi_structured_service.list_templates()

@router.get("/templates/{domain}")
async def get_template(domain: str):
    tmpl = semi_structured_service.get_template(domain)
    if not tmpl:
        raise HTTPException(status_code=404, detail=f"Template for domain '{domain}' not found.")
    return tmpl

@router.post("/templates/{domain}")
async def save_template(domain: str, payload: Dict[str, Any] = Body(...)):
    return semi_structured_service.save_template(domain, payload)

@router.post("/ingest")
async def ingest_file(
    file: UploadFile = File(...),
    domain: Optional[str] = Form(None),
    workspace_id: str = Form("default")
):
    if not file.filename:
        raise HTTPException(status_code=400, detail="Uploaded file has no filename.")

    file_bytes = await file.read()
    try:
        res = semi_structured_service.ingest_file(
            file_bytes=file_bytes,
            filename=file.filename,
            domain=domain,
            workspace_id=workspace_id
        )
        return res
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/ingest/path")
async def ingest_path(payload: Dict[str, Any] = Body(...)):
    path = payload.get("path")
    if not path:
        raise HTTPException(status_code=400, detail="Missing required 'path' field.")

    domain = payload.get("domain")
    workspace_id = payload.get("workspace_id", "default")
    max_files = int(payload.get("max_files", 50))

    try:
        return semi_structured_service.ingest_path(
            path=path,
            domain=domain,
            workspace_id=workspace_id,
            max_files=max_files
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/documents")
async def list_documents(status: Optional[str] = Query(None)):
    return semi_structured_service.list_documents(status=status)

@router.get("/documents/{document_id}")
async def get_document_status(document_id: str):
    doc = semi_structured_service.get_document_status(document_id)
    if not doc:
        raise HTTPException(status_code=404, detail=f"Document '{document_id}' not found.")
    return doc

@router.post("/resolve/{document_id}")
async def resolve_document(document_id: str):
    try:
        return semi_structured_service.resolve_document(document_id)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/reprocess/{document_id}")
async def reprocess_document(document_id: str, domain: Optional[str] = Body(None)):
    try:
        return semi_structured_service.reprocess_document(document_id, domain=domain)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/export/csv")
async def export_csv(status: Optional[str] = Query(None)):
    csv_str = semi_structured_service.export_csv(status=status)
    return PlainTextResponse(csv_str, media_type="text/csv")

@router.get("/export/json")
async def export_json(status: Optional[str] = Query(None)):
    return semi_structured_service.export_json(status=status)
