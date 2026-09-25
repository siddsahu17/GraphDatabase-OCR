import os
from typing import Dict, Any, Optional
from models.domain import PipelineContext
from ingestion.semi_structured.ocr import ocr_cascade
from ingestion.semi_structured.document_templates import template_manager
from ingestion.semi_structured.template_extractor import template_extractor
from ingestion.semi_structured.template_ko_builder import template_ko_builder
from ingestion.semi_structured.business_schema import business_schema_extractor
from common.logger import get_logger

logger = get_logger(__name__)

class SemiStructuredEngine:
    """
    Semi-Structured Engine Plugin (§6.4 & §6A.4).
    Orchestrates OCR cascade, document classification, template or generic extraction, and KO creation.
    """
    def run(
        self,
        file_path: str,
        explicit_domain: Optional[str] = None,
        workspace_id: str = "default"
    ) -> PipelineContext:

        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File not found: {file_path}")

        # 1. OCR Cascade
        ocr_res = ocr_cascade.process(file_path)

        # 2. Document Classification
        domain, tmpl, score = template_manager.classify_document(ocr_res, explicit_domain)

        ctx = PipelineContext(
            document_id=ocr_res.document_id,
            source_path=file_path,
            workspace_id=workspace_id,
            ocr_result=ocr_res,
            domain=domain or "generic",
            template_name=domain
        )

        # 3. Extraction Branch (Template vs Generic)
        if tmpl is not None:
            logger.info(f"Using Template Extraction branch for domain '{domain}' (score: {score:.2f})")
            fields, errors = template_extractor.extract(ocr_res.normalized_text or ocr_res.full_text, tmpl)
            ctx.extracted_fields = fields
            
            val_status = "approved"
            if errors:
                val_status = "needs_review"
                ctx.status = "needs_review"
                for err in errors:
                    ctx.add_warning(err)

            kos = template_ko_builder.build_knowledge_objects(fields, tmpl, ocr_res, val_status)
            ctx.knowledge_objects = kos
        else:
            logger.info("Using Generic LLM Business Schema Extraction branch")
            kos = business_schema_extractor.extract_generic_kos(ocr_res, workspace_id)
            ctx.knowledge_objects = kos

        return ctx

semi_structured_engine = SemiStructuredEngine()
