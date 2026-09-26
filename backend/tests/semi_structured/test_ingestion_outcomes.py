import os
import pytest
from fastapi.testclient import TestClient
from main import app
from models.domain import OCRResult, OCRPage
from pipeline.orchestrator import pipeline_orchestrator
from ingestion.semi_structured.document_templates import template_manager
from ingestion.semi_structured.template_extractor import template_extractor
from ingestion.semi_structured.template_ko_builder import template_ko_builder
from graph_builder.canonical import canonical_graph_builder
from graph.falkordb import falkor_client

client = TestClient(app)

def test_medical_bill_ingestion_full_outcomes(tmp_path):
    text = """
Lilavati Hospital & Research Centre
PATIENT ACCOUNT STATEMENT
Statement Date: 05/22/2026 Primary Insurance: HDFC ERGO General Insurance
Guarantor No: MRN-1039485 Group No: GRP-2960
Patient Name: Amit Singh Primary Diagnosis: Hyperlipidemia
Date of Birth: 1978-11-03 ICD-10 Code: E78.5

Date CPT Description Charges
05/22/2026 0260 IV Therapy $243.00
05/22/2026 99283 Emergency Room Level 3 $801.00

Total Billed Charges: $1044.00
PATIENT AMOUNT DUE: $144.00
"""
    file_path = tmp_path / "bill_amit_singh.txt"
    file_path.write_text(text, encoding="utf-8")

    ctx = pipeline_orchestrator.process_document(file_path=str(file_path), domain="medical_bill")

    assert ctx.status in ("ingested", "needs_review")
    assert ctx.domain == "medical_bill"
    assert ctx.extracted_fields.get("mrn") == "MRN-1039485"
    assert ctx.extracted_fields.get("patient_name") == "Amit Singh"
    assert ctx.extracted_fields.get("provider_name") == "Lilavati Hospital & Research Centre"
    assert ctx.extracted_fields.get("icd_code") == "E78.5"

    node_labels = {n.label for n in ctx.graph_nodes}
    assert "Patient" in node_labels
    assert "Hospital" in node_labels
    assert "MedicalBill" in node_labels
    assert "Condition" in node_labels
    assert "Insurance" in node_labels
    assert "LineItem" in node_labels
    assert "Chunk" not in node_labels
    assert "Page" not in node_labels

    patient_node = next(n for n in ctx.graph_nodes if n.label == "Patient")
    assert "Amit Singh" in patient_node.properties.get("name", "")
    assert "MRN-1039485" in patient_node.properties.get("name", "")

    target_graph = falkor_client.resolve_graph_name(ctx.domain)
    assert target_graph == "medical_graph"


def test_discharge_summary_ingestion_full_outcomes(tmp_path):
    text = """
Christian Medical College (CMC)
DISCHARGE INSTRUCTIONS & CLINICAL SUMMARY

Patient: Vikram Reddy MRN: MRN-3920184 DOB: 1982-09-30

1. CHIEF COMPLAINT & HISTORY OF PRESENT ILLNESS
Patient presented with worsening symptoms consistent with Osteoarthritis of Knee.

2. ADMISSION DIAGNOSIS
Osteoarthritis of Knee (ICD-10: M17.9)

5. DISCHARGE MEDICATIONS
• Meloxicam 15mg PO Daily
• Triamcinolone Acetonide Intra-articular Injection

Electronically Signed By: Date/Time:
Dr. Jonathan H. Carter, MD 05/22/2026 00:00 PST
"""
    file_path = tmp_path / "ds_vikram_reddy.txt"
    file_path.write_text(text, encoding="utf-8")

    ctx = pipeline_orchestrator.process_document(file_path=str(file_path), domain="discharge_summary")

    assert ctx.extracted_fields.get("mrn") == "MRN-3920184"
    assert ctx.extracted_fields.get("patient_name") == "Vikram Reddy"
    assert ctx.extracted_fields.get("attending_physician") == "Dr. Jonathan H. Carter, MD"
    assert ctx.extracted_fields.get("icd_code") == "M17.9"

    doc_node = next(n for n in ctx.graph_nodes if n.label == "Doctor")
    assert doc_node.properties.get("name") == "Dr. Jonathan H. Carter, MD"

    med_nodes = [n for n in ctx.graph_nodes if n.label == "Medication"]
    assert len(med_nodes) >= 2

    target_graph = falkor_client.resolve_graph_name(ctx.domain)
    assert target_graph == "medical_graph"


def test_invoice_ingestion_full_outcomes(tmp_path):
    text = """
INVOICE
Invoice No: INV-90214 Date: 2026-05-15
Vendor: Acme Supplies Inc.
Billed To: Global Tech Solutions

Widget Type A   10  $50.00  $500.00
Service Hour    5   $100.00 $500.00

Total Amount: $1000.00
"""
    file_path = tmp_path / "invoice_acme.txt"
    file_path.write_text(text, encoding="utf-8")

    ctx = pipeline_orchestrator.process_document(file_path=str(file_path), domain="invoice")

    assert ctx.domain == "invoice"
    assert ctx.extracted_fields.get("invoice_no") == "INV-90214"
    assert ctx.extracted_fields.get("total_amount") == 1000.00

    node_labels = {n.label for n in ctx.graph_nodes}
    assert "Vendor" in node_labels
    assert "Customer" in node_labels
    assert "Invoice" in node_labels
    assert "LineItem" in node_labels

    target_graph = falkor_client.resolve_graph_name(ctx.domain)
    assert target_graph == "invoice_graph"


def test_multi_document_patient_canonicalization():
    text1 = "Lilavati Hospital\nPatient Name: Amit Singh\nMRN: MRN-1039485\nDiagnosis: Hyperlipidemia\nICD-10: E78.5\nTotal: $500"
    text2 = "CMC Hospital\nPatient Name: Amit Singh\nMRN: MRN-1039485\nDiagnosis: Hyperlipidemia\nICD-10: E78.5\nDischarge Date: 05/22/2026"
    text3 = "Apollo Hospital\nPatient Name: Amit Singh\nMRN: MRN-1039485\nDiagnosis: Hyperlipidemia\nICD-10: E78.5\nTotal: $750"

    tmpl1 = template_manager.get_template("medical_bill")
    tmpl2 = template_manager.get_template("discharge_summary")

    f1, _ = template_extractor.extract(text1, tmpl1)
    f2, _ = template_extractor.extract(text2, tmpl2)
    f3, _ = template_extractor.extract(text3, tmpl1)

    ocr1 = OCRResult(document_id="doc1", source_path="doc1.jpg", full_text=text1, normalized_text=text1, pages=[OCRPage(page_number=1, text=text1)])
    ocr2 = OCRResult(document_id="doc2", source_path="doc2.jpg", full_text=text2, normalized_text=text2, pages=[OCRPage(page_number=1, text=text2)])
    ocr3 = OCRResult(document_id="doc3", source_path="doc3.jpg", full_text=text3, normalized_text=text3, pages=[OCRPage(page_number=1, text=text3)])

    kos1 = template_ko_builder.build_knowledge_objects(f1, tmpl1, ocr1)
    kos2 = template_ko_builder.build_knowledge_objects(f2, tmpl2, ocr2)
    kos3 = template_ko_builder.build_knowledge_objects(f3, tmpl1, ocr3)

    p1 = next(k for k in kos1 if k.entity_type == "Patient")
    p2 = next(k for k in kos2 if k.entity_type == "Patient")
    p3 = next(k for k in kos3 if k.entity_type == "Patient")

    assert p1.canonical_id == p2.canonical_id == p3.canonical_id

    c1 = next(k for k in kos1 if k.entity_type == "Condition")
    c2 = next(k for k in kos2 if k.entity_type == "Condition")
    c3 = next(k for k in kos3 if k.entity_type == "Condition")

    assert c1.canonical_id == c2.canonical_id == c3.canonical_id


def test_multi_patient_shared_disease_node():
    text1 = "Lilavati Hospital\nPatient Name: Amit Singh\nMRN: MRN-1001\nDiagnosis: Hyperlipidemia\nICD-10: E78.5\nTotal: $500"
    text2 = "Lilavati Hospital\nPatient Name: Raji Kumar\nMRN: MRN-2002\nDiagnosis: Hyperlipidemia\nICD-10: E78.5\nTotal: $600"

    tmpl = template_manager.get_template("medical_bill")

    f1, _ = template_extractor.extract(text1, tmpl)
    f2, _ = template_extractor.extract(text2, tmpl)

    ocr1 = OCRResult(document_id="doc1", source_path="doc1.jpg", full_text=text1, normalized_text=text1, pages=[OCRPage(page_number=1, text=text1)])
    ocr2 = OCRResult(document_id="doc2", source_path="doc2.jpg", full_text=text2, normalized_text=text2, pages=[OCRPage(page_number=1, text=text2)])

    kos1 = template_ko_builder.build_knowledge_objects(f1, tmpl, ocr1)
    kos2 = template_ko_builder.build_knowledge_objects(f2, tmpl, ocr2)

    p1 = next(k for k in kos1 if k.entity_type == "Patient")
    p2 = next(k for k in kos2 if k.entity_type == "Patient")

    # Patient IDs must be distinct
    assert p1.canonical_id != p2.canonical_id

    c1 = next(k for k in kos1 if k.entity_type == "Condition")
    c2 = next(k for k in kos2 if k.entity_type == "Condition")

    # Condition IDs must be identical for same ICD code (canonical disease node)
    assert c1.canonical_id == c2.canonical_id


def test_heuristic_fallback_extraction():
    text = "INVOICE STATEMENT\nSeller: Acme Global\nClient: Tech Corp\nInv #: INV-77112\nDate: 2026-08-10\nTotal Due: $3500.00"
    tmpl = template_manager.get_template("invoice")
    fields, errors = template_extractor.extract(text, tmpl)

    assert fields.get("invoice_no") == "INV-77112"
    assert fields.get("total_amount") == 3500.00


def test_doctor_title_casing_variations():
    names = [
        ("dr. john doe, md", "Dr. John Doe, MD"),
        ("Dr. Sarah Smith, DO, PhD", "Dr. Sarah Smith, DO, PhD"),
        ("DR. ALEX BROWN, MBBS", "Dr. Alex Brown, MBBS")
    ]
    for raw, expected in names:
        formatted = template_ko_builder._format_doctor_name(raw)
        assert formatted == expected


def test_api_process_images_upload(tmp_path):
    fpath = tmp_path / "test_bill.txt"
    fpath.write_text("Lilavati Hospital\nPatient Name: Amit Singh\nMRN: MRN-1039485\nTotal: $1500.00")

    with open(fpath, "rb") as f:
        response = client.post(
            "/api/process-images",
            files={"files": ("test_bill.txt", f, "text/plain")},
            data={"domain": "medical_bill"}
        )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert data["files_processed"] == 1
    assert "graph" in data
    assert len(data["graph"]["nodes"]) >= 1


def test_api_semi_structured_ingest_path(tmp_path):
    fpath = tmp_path / "sample_inv.txt"
    fpath.write_text("Invoice No: INV-12345\nTotal: $100.00\nVendor: Acme")

    response = client.post(
        "/api/semi-structured/ingest/path",
        json={"path": str(tmp_path), "domain": "invoice"}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "completed"
    assert data["total_files"] >= 1


def test_nonexistent_file_ingestion_raises_error():
    with pytest.raises(FileNotFoundError):
        pipeline_orchestrator.process_document(file_path="non_existent_path_12345.png")


def test_empty_file_ingestion_fallback(tmp_path):
    fpath = tmp_path / "empty_doc.txt"
    fpath.write_text("   \n   \n")

    ctx = pipeline_orchestrator.process_document(file_path=str(fpath))
    assert ctx.document_id is not None
    assert len(ctx.knowledge_objects) >= 0


def test_unknown_domain_override_fallback(tmp_path):
    fpath = tmp_path / "unknown_domain.txt"
    fpath.write_text("Some random text without matching signatures.")

    ctx = pipeline_orchestrator.process_document(file_path=str(fpath), domain="non_existent_domain_xyz")
    assert ctx.document_id is not None
    assert ctx.domain == "generic"

