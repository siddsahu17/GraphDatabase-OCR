# BodhiECG REST API Reference Manual (§14.2 & §24)

## Overview
Base URL: `http://localhost:8000/api`

## 1. Semi-Structured Document Ingestion API (`/api/semi-structured`)

### GET `/api/semi-structured/templates`
- **Description**: Lists registered template schemas (Invoice, Medical Bill, Discharge Summary).

### GET `/api/semi-structured/templates/{domain}`
- **Description**: Returns template definition JSON for a domain.

### POST `/api/semi-structured/templates/{domain}`
- **Description**: Registers or updates dynamic template schema.

### POST `/api/semi-structured/ingest`
- **Description**: Single-file upload multipart endpoint.
- **Form Data**:
  - `file`: UploadFile (PDF, JPG, PNG, TIF, TXT)
  - `domain` (optional): `invoice` | `medical_bill` | `discharge_summary`
  - `workspace_id`: string (default `"default"`)

### POST `/api/semi-structured/ingest/path`
- **Description**: Batch directory or file path ingestion endpoint.
- **JSON Body**:
  ```json
  {
    "path": "data/Medical/bills",
    "domain": "medical_bill",
    "max_files": 10
  }
  ```

### GET `/api/semi-structured/documents`
- **Query Params**: `status` (optional: `pending` | `needs_review` | `ingested`)
- **Description**: Lists cached document status records.

### GET `/api/semi-structured/documents/{document_id}`
- **Description**: Retrieves full cache status and extracted fields for a document.

### POST `/api/semi-structured/resolve/{document_id}`
- **Description**: Resolves validation issues and marks document status as `ingested`.

### POST `/api/semi-structured/reprocess/{document_id}`
- **Description**: Re-runs OCR and extraction pipeline for a document.

### GET `/api/semi-structured/export/csv`
- **Query Params**: `status` (optional)
- **Description**: Exports extracted document dataset in CSV format.

### GET `/api/semi-structured/export/json`
- **Query Params**: `status` (optional)
- **Description**: Exports extracted document dataset in JSON format.

---

## 2. Grounded Retrieval & Graph Search API (`/api/retrieval`)

### POST `/api/retrieval/grounded`
- **JSON Body**:
  ```json
  {
    "question": "What is the total amount due on invoice #INV-998877?",
    "workspace_id": "default"
  }
  ```
- **Response**: Grounded QA answer with page-level source citations.

### POST `/api/retrieval/nl2cypher`
- **JSON Body**:
  ```json
  {
    "query": "Find all patients diagnosed with chest pain",
    "workspace_id": "default"
  }
  ```
- **Response**: Generated Cypher READ query and execution result from FalkorDB.

### POST `/api/query`
- **JSON Body**:
  ```json
  {
    "query": "Which hospital billed patient John Doe?",
    "workspace_id": "default"
  }
  ```
- **Response**: Unified graph QA retrieval result.
