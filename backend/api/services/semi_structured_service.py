import os
import glob
import json
import csv
import io
import tempfile
from typing import Dict, Any, List, Optional
from pipeline.orchestrator import pipeline_orchestrator
from ingestion.semi_structured.document_cache import (
    document_cache,
    STATUS_PENDING,
    STATUS_NEEDS_REVIEW,
    STATUS_INGESTED
)
from ingestion.semi_structured.document_templates import template_manager
from common.logger import get_logger

logger = get_logger(__name__)

class SemiStructuredService:
    """
    Service layer (§3.2) for semi-structured document ingestion & template management.
    Strictly isolated from HTTP router definitions.
    """

    def list_templates(self) -> List[Dict[str, Any]]:
        return template_manager.list_templates()

    def get_template(self, domain: str) -> Optional[Dict[str, Any]]:
        return template_manager.get_template(domain)

    def save_template(self, domain: str, template_data: Dict[str, Any]) -> Dict[str, Any]:
        t_path = os.path.join(template_manager.templates_dir, f"{domain}.json")
        with open(t_path, "w", encoding="utf-8") as f:
            json.dump(template_data, f, indent=2)
        template_manager.reload_templates()
        return {"status": "success", "domain": domain}

    def ingest_file(
        self,
        file_bytes: bytes,
        filename: str,
        domain: Optional[str] = None,
        workspace_id: str = "default"
    ) -> Dict[str, Any]:
        temp_dir = tempfile.gettempdir()
        temp_path = os.path.join(temp_dir, f"upload_{filename}")

        try:
            with open(temp_path, "wb") as f:
                f.write(file_bytes)

            ctx = pipeline_orchestrator.process_document(
                file_path=temp_path,
                domain=domain,
                workspace_id=workspace_id
            )

            rec = document_cache.save_document(
                document_id=ctx.document_id,
                source_path=filename,
                target_status=ctx.status,
                ocr_result_ref={"engine": ctx.ocr_result.engine_used} if ctx.ocr_result else None,
                domain=ctx.domain,
                extracted_fields=ctx.extracted_fields,
                validation_errors=ctx.warnings
            )

            return {
                "document_id": ctx.document_id,
                "status": ctx.status,
                "domain": ctx.domain,
                "pipeline_run_id": ctx.document_id,
                "knowledge_objects_count": len(ctx.knowledge_objects),
                "nodes_count": len(ctx.graph_nodes),
                "edges_count": len(ctx.graph_edges),
                "extracted_fields": ctx.extracted_fields,
                "warnings": ctx.warnings
            }
        finally:
            if os.path.exists(temp_path):
                try:
                    os.remove(temp_path)
                except Exception:
                    pass

    def ingest_path(
        self,
        path: str,
        domain: Optional[str] = None,
        workspace_id: str = "default",
        max_files: int = 50
    ) -> Dict[str, Any]:
        if not os.path.exists(path):
            raise ValueError(f"Path '{path}' does not exist.")

        target_files = []
        if os.path.isfile(path):
            target_files.append(path)
        else:
            for ext in ("*.jpg", "*.jpeg", "*.png", "*.pdf", "*.tif", "*.tiff", "*.txt"):
                target_files.extend(glob.glob(os.path.join(path, ext)))
                target_files.extend(glob.glob(os.path.join(path, "**", ext), recursive=True))

        target_files = list(set(target_files))[:max_files]
        results = []

        for fpath in target_files:
            try:
                ctx = pipeline_orchestrator.process_document(
                    file_path=fpath,
                    domain=domain,
                    workspace_id=workspace_id
                )
                document_cache.save_document(
                    document_id=ctx.document_id,
                    source_path=fpath,
                    target_status=ctx.status,
                    ocr_result_ref={"engine": ctx.ocr_result.engine_used} if ctx.ocr_result else None,
                    domain=ctx.domain,
                    extracted_fields=ctx.extracted_fields,
                    validation_errors=ctx.warnings
                )
                results.append({
                    "file": os.path.basename(fpath),
                    "document_id": ctx.document_id,
                    "status": ctx.status,
                    "domain": ctx.domain,
                    "nodes": len(ctx.graph_nodes),
                    "edges": len(ctx.graph_edges)
                })
            except Exception as e:
                logger.error(f"Failed to ingest file '{fpath}': {e}")
                results.append({
                    "file": os.path.basename(fpath),
                    "status": "error",
                    "error": str(e)
                })

        return {
            "status": "completed",
            "total_files": len(target_files),
            "results": results
        }

    def list_documents(self, status: Optional[str] = None) -> List[Dict[str, Any]]:
        return document_cache.list_documents(status)

    def get_document_status(self, document_id: str) -> Optional[Dict[str, Any]]:
        return document_cache.get_document(document_id)

    def resolve_document(self, document_id: str) -> Dict[str, Any]:
        doc = document_cache.get_document(document_id)
        if not doc:
            raise ValueError(f"Document '{document_id}' not found in cache.")

        rec = document_cache.save_document(
            document_id=document_id,
            source_path=doc.get("source_path", ""),
            target_status=STATUS_INGESTED,
            domain=doc.get("domain"),
            extracted_fields=doc.get("extracted_fields", {}),
            validation_errors=[]
        )
        return {"status": "success", "record": rec}

    def reprocess_document(self, document_id: str, domain: Optional[str] = None) -> Dict[str, Any]:
        doc = document_cache.get_document(document_id)
        if not doc:
            raise ValueError(f"Document '{document_id}' not found in cache.")

        source_path = doc.get("source_path")
        if not source_path or not os.path.exists(source_path):
            return self.resolve_document(document_id)

        ctx = pipeline_orchestrator.process_document(
            file_path=source_path,
            domain=domain or doc.get("domain")
        )
        document_cache.save_document(
            document_id=ctx.document_id,
            source_path=source_path,
            target_status=ctx.status,
            domain=ctx.domain,
            extracted_fields=ctx.extracted_fields,
            validation_errors=ctx.warnings
        )
        return {"status": "success", "document_id": ctx.document_id, "new_status": ctx.status}

    def export_csv(self, status: Optional[str] = None) -> str:
        docs = document_cache.list_documents(status)
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["document_id", "source_path", "status", "domain", "updated_at", "extracted_fields"])

        for d in docs:
            writer.writerow([
                d.get("document_id"),
                d.get("source_path"),
                d.get("status"),
                d.get("domain"),
                d.get("updated_at"),
                json.dumps(d.get("extracted_fields", {}))
            ])
        return output.getvalue()

    def export_json(self, status: Optional[str] = None) -> List[Dict[str, Any]]:
        return document_cache.list_documents(status)

semi_structured_service = SemiStructuredService()
