# BodhiECG Codebase Architecture Guide

## System Overview
BodhiECG is a Knowledge Graph Ingestion Engine built to transform semi-structured medical bills, commercial invoices, and clinical discharge summaries into a queryable FalkorDB graph.

## Architectural Layers (§3.2 & §24)

1. **Config & Common Substrate**:
   - `config/settings.py`: Centralized Pydantic settings loading `.env`. `HF_HUB_DISABLE_SYMLINKS=1` set automatically for Windows compatibility.
   - `common/logger.py`: Structured logging formatting.
   - `common/exceptions.py`: Domain exception hierarchy (`OCRError`, `TemplateError`, `GraphDatabaseError`, `ValidationException`).

2. **Domain Models**:
   - `models/domain.py`: Strong Pydantic models for `OCRResult`, `OCRPage`, `SemanticObject`, `GraphNode`, `GraphEdge`, and `PipelineContext`.

3. **Semi-Structured Ingestion Engine**:
   - `ingestion/semi_structured/ocr.py`: OCR Cascade (Text Reader -> `pypdf` Fast Path -> `docling` Fallback -> OpenCV/Tesseract Preprocessing -> `EasyOCR` Fallback) + `normalize_ocr_text`.
   - `ingestion/semi_structured/document_cache.py`: Document lifecycle store tracking `pending`, `needs_review`, and `ingested` states.
   - `ingestion/semi_structured/document_templates.py`: Template signature classifier for invoice, medical bill, and discharge summary.
   - `ingestion/semi_structured/template_extractor.py` & `template_ko_builder.py`: Deterministic field extraction and KO construction.
   - `ingestion/semi_structured/kv_extraction.py` & `business_schema.py`: LLM Gateway generic schema generator.

4. **Identity & Storage**:
   - `storage/entity_registry_store.py`: Identity map producing deterministic canonical IDs for business keys (e.g. MRN, Invoice No, Bill No).

5. **Canonical Pipeline Orchestrator**:
   - `pipeline/orchestrator.py`: Single entry-point `PipelineOrchestrator` executing canonical 16-stage pipeline.
   - `pipeline/engines/semi_structured_engine.py`: Engine handling template vs LLM extraction routing based on signature confidence.
   - `pipeline/stages/canonical_stages.py`: Stages for Ingestion, KO Generation, Review, Resolution, Alignment, Graph Construction, Persistence, Validation, Indexing, and Retrieval Readiness.

6. **FalkorDB Graph Layer**:
   - `graph/falkordb.py`: `FalkorGraphClient` executing idempotent Cypher MERGE queries with `(:Document)`, `(:Page)`, `(:Chunk)` provenance.
   - `graph/label_resolver.py`: Node/Relationship label canonicalization.

7. **Retrieval Substrate**:
   - `ingestion/unstructured/graph/indexes.py` & `retrieval_substrate.py`: HNSW / Full-text indexing manager.
   - `ingestion/unstructured/graph/context.py`: Grounded GraphRAG engine generating citations per `document_id` and `page_number`.

8. **Service Layer & REST Routers (§3.2)**:
   - `api/services/semi_structured_service.py` & `retrieval_service.py`: Business logic strictly decoupled from HTTP endpoints.
   - `api/routers/semi_structured.py` & `retrieval.py`: FastAPI routes serving `/api/semi-structured/*` and `/api/retrieval/*`.
