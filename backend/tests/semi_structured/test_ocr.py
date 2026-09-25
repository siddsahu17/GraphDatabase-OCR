import os
import pytest
from PIL import Image
import numpy as np

from ingestion.semi_structured.ocr import (
    preprocess_image,
    normalize_ocr_text,
    ocr_cascade,
)
from models.domain import OCRResult, OCRPage

def test_text_normalization_hyphenation():
    raw = "This is a docu-\nment with split words."
    normalized = normalize_ocr_text(raw)
    assert "document" in normalized
    assert "docu-\nment" not in normalized

def test_text_normalization_numeric_ocr_fixes():
    # O -> 0 and l -> 1 inside numeric tokens
    raw = "Invoice No: INV-O123 | Total: $1O.5O | Qty: 1l0"
    normalized = normalize_ocr_text(raw)
    assert "INV-0123" in normalized
    assert "$10.50" in normalized
    assert "110" in normalized

def test_preprocess_image():
    # Create a synthetic 100x100 white image with black text rectangle
    img = Image.new("RGB", (100, 100), color=(255, 255, 255))
    processed = preprocess_image(img)
    assert isinstance(processed, np.ndarray)
    assert processed.shape[0] > 0
    assert processed.shape[1] > 0

def test_ocr_cascade_on_invoice_fixture():
    fixture_path = "data/Invoice/batch1-0001.jpg"
    if not os.path.exists(fixture_path):
        fixture_path = "../data/Invoice/batch1-0001.jpg"

    if not os.path.exists(fixture_path):
        pytest.skip(f"Fixture not found at {fixture_path}")

    res = ocr_cascade.process(fixture_path)
    assert isinstance(res, OCRResult)
    assert res.document_id is not None
    assert len(res.document_id) == 64  # SHA-256 hex digest
    assert res.engine_used in ["pypdf", "docling", "tesseract", "easyocr", "fallback_raw"]
    assert res.page_count >= 1

def test_ocr_cascade_on_medical_bill_fixture():
    fixture_path = "data/Medical/bills/med_doc_bill_100001_noisy.jpg"
    if not os.path.exists(fixture_path):
        fixture_path = "../data/Medical/bills/med_doc_bill_100001_noisy.jpg"

    if not os.path.exists(fixture_path):
        pytest.skip(f"Fixture not found at {fixture_path}")

    res = ocr_cascade.process(fixture_path)
    assert isinstance(res, OCRResult)
    assert res.full_text is not None
    assert res.normalized_text is not None
