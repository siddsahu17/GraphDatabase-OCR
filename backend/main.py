import os
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from app.api.upload import router as upload_router
from app.api.ingest import router as ingest_router
from app.api.graph import router as graph_router

from api.routers.semi_structured import router as semi_structured_router
from api.routers.retrieval import router as retrieval_router

app = FastAPI(
    title="BodhiECG - FalkorDB Graph & OCR Ingestion Engine",
    version="2.0.0",
    description="Full-stack Knowledge Graph pipeline with semi-structured document OCR, template cascade, entity resolution, and grounded retrieval.",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json"
)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register legacy UI routers
app.include_router(upload_router, prefix="/api", tags=["Document Processing (Legacy)"])
app.include_router(ingest_router, prefix="/api", tags=["Graph Ingestion (Legacy)"])
app.include_router(graph_router, prefix="/api", tags=["Graph Explorer & Schemas (Legacy)"])

# Register BodhiECG Spec Routers (§14.2 & §24)
app.include_router(semi_structured_router, prefix="/api")
app.include_router(retrieval_router, prefix="/api")

# Mount static React frontend dist build
FRONTEND_DIST_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../frontend/dist"))
if os.path.exists(FRONTEND_DIST_DIR):
    assets_dir = os.path.join(FRONTEND_DIST_DIR, "assets")
    if os.path.exists(assets_dir):
        app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")

    @app.get("/")
    async def serve_root():
        index_path = os.path.join(FRONTEND_DIST_DIR, "index.html")
        if os.path.exists(index_path):
            return FileResponse(index_path)
        return {"message": "BodhiECG Knowledge Graph Engine running."}

    @app.get("/{full_path:path}")
    async def serve_react_app(full_path: str):
        # Do NOT intercept FastAPI documentation or API routes
        if full_path in ("docs", "redoc", "openapi.json") or full_path.startswith(("api/", "docs/", "redoc/", "openapi.json")):
            raise HTTPException(status_code=404, detail="Not Found")
            
        file_path = os.path.join(FRONTEND_DIST_DIR, full_path)
        if os.path.exists(file_path) and os.path.isfile(file_path):
            return FileResponse(file_path)
        index_path = os.path.join(FRONTEND_DIST_DIR, "index.html")
        if os.path.exists(index_path):
            return FileResponse(index_path)
        return {"message": "BodhiECG Knowledge Graph Engine running."}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
