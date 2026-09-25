import os
import pytest
from ingestion.semi_structured.document_templates import template_manager
from ingestion.semi_structured.template_extractor import template_extractor
from ingestion.semi_structured.template_ko_builder import template_ko_builder
from storage.entity_registry_store import EntityRegistryStore
from models.domain import OCRResult, OCRPage

def test_template_classification_signature():
    ocr_res = OCRResult(
        document_id="doc123",
        source_path="data/Medical/bills/med_doc_bill_100001_noisy.jpg",
        full_text="PATIENT ACCOUNT STATEMENT\nPatient Name: John Doe\nMRN: MRN-1039485\nBill Date: 05/22/2026\nTotal Charge: $1200.00",
        normalized_text="PATIENT ACCOUNT STATEMENT\nPatient Name: John Doe\nMRN: MRN-1039485\nBill Date: 05/22/2026\nTotal Charge: $1200.00"
    )

    domain, tmpl, score = template_manager.classify_document(ocr_res)
    assert domain == "medical_bill"
    assert tmpl is not None
    assert score >= 0.5

def test_explicit_domain_override():
    ocr_res = OCRResult(
        document_id="doc123",
        source_path="sample.jpg",
        full_text="Random unclassified text"
    )
    domain, tmpl, score = template_manager.classify_document(ocr_res, explicit_domain="invoice")
    assert domain == "invoice"
    assert tmpl is not None

def test_deterministic_entity_resolution(tmp_path):
    store = EntityRegistryStore(storage_path=str(tmp_path / "entity_registry.json"))
    
    cid1 = store.get_or_create_canonical_id("Patient", "MRN-1039485")
    cid2 = store.get_or_create_canonical_id("Patient", "MRN-1039485")
    
    # Cross-document identity rule (§9A): same MRN produces exact same canonical_id
    assert cid1 == cid2
    assert cid1.startswith("patient_")

def test_template_field_extraction():
    tmpl = template_manager.get_template("medical_bill")
    text = "Patient Name: Amit Singh\nMRN: MRN-1039485\nBill No: BILL-9901\nTotal Charge: $1200.50"
    
    fields, errors = template_extractor.extract(text, tmpl)
    assert fields.get("mrn") == "MRN-1039485"
    assert fields.get("bill_no") == "BILL-9901"
    assert fields.get("total_amount") == 1200.50
    assert len(errors) == 0
