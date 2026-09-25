from typing import Dict, Any
from fastapi import APIRouter, HTTPException, Body
from api.services.retrieval_service import retrieval_service

router = APIRouter(tags=["Grounded Retrieval & Graph Search"])

@router.post("/retrieval/grounded")
async def grounded_retrieval(payload: Dict[str, Any] = Body(...)):
    question = payload.get("question") or payload.get("query")
    if not question:
        raise HTTPException(status_code=400, detail="Missing 'question' or 'query' field.")
    
    workspace_id = payload.get("workspace_id", "default")
    return retrieval_service.grounded_qa(question=question, workspace_id=workspace_id)

@router.post("/retrieval/nl2cypher")
async def nl2cypher(payload: Dict[str, Any] = Body(...)):
    query = payload.get("query") or payload.get("question")
    if not query:
        raise HTTPException(status_code=400, detail="Missing 'query' field.")
    
    workspace_id = payload.get("workspace_id", "default")
    return retrieval_service.nl2cypher(query=query, workspace_id=workspace_id)

@router.post("/query")
async def general_query(payload: Dict[str, Any] = Body(...)):
    query = payload.get("query") or payload.get("question")
    if not query:
        raise HTTPException(status_code=400, detail="Missing 'query' field.")

    workspace_id = payload.get("workspace_id", "default")
    return retrieval_service.execute_query(query=query, workspace_id=workspace_id)
