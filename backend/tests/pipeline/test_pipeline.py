import os
import pytest
from pipeline.orchestrator import pipeline_orchestrator
from pipeline.engines.semi_structured_engine import SemiStructuredEngine
from models.domain import PipelineContext, OCRResult

def test_pipeline_orchestrator_initialization():
    assert pipeline_orchestrator is not None
    assert len(pipeline_orchestrator.stages) >= 3

def test_semi_structured_engine_run(tmp_path):
    sample_file = tmp_path / "sample_invoice.txt"
    sample_file.write_text("INVOICE #INV-998877\nTotal: $450.00\nDate: 2026-09-24\nBill To: Acme Corp")

    ctx = pipeline_orchestrator.process_document(
        file_path=str(sample_file),
        domain="invoice"
    )

    assert ctx.document_id is not None
    assert ctx.domain == "invoice"
    assert ctx.ocr_result is not None
    assert "INV-998877" in (ctx.ocr_result.full_text or ctx.ocr_result.normalized_text or "")
    assert len(ctx.knowledge_objects) >= 1
    assert len(ctx.graph_nodes) >= 1
    assert ctx.status in ("ingested", "needs_review")
