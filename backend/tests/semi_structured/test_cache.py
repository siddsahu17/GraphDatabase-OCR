import os
import pytest
from ingestion.semi_structured.document_cache import (
    DocumentCache,
    STATUS_PENDING,
    STATUS_NEEDS_REVIEW,
    STATUS_INGESTED,
)
from common.exceptions import ValidationException

def test_document_cache_lifecycle(tmp_path):
    cache_dir = tmp_path / "cache"
    upload_dir = tmp_path / "uploads"
    cache = DocumentCache(cache_dir=str(cache_dir), upload_dir=str(upload_dir))

    doc_id = "test_doc_001"
    src_path = "data/Invoice/batch1-0001.jpg"

    # 1. Save new document -> pending
    rec1 = cache.save_document(
        document_id=doc_id,
        source_path=src_path,
        target_status=STATUS_PENDING,
        domain="invoice"
    )
    assert rec1["status"] == STATUS_PENDING
    assert rec1["document_id"] == doc_id

    # 2. Transition pending -> ingested
    rec2 = cache.save_document(
        document_id=doc_id,
        source_path=src_path,
        target_status=STATUS_INGESTED
    )
    assert rec2["status"] == STATUS_INGESTED

    # 3. Illegal transition: new directly to ingested (should raise ValidationException)
    with pytest.raises(ValidationException):
        cache.save_document(
            document_id="illegal_doc",
            source_path=src_path,
            target_status=STATUS_INGESTED
        )
