import pytest
from models.domain import OCRResult, OCRPage
from ingestion.semi_structured.document_templates import template_manager
from ingestion.semi_structured.template_extractor import template_extractor
from ingestion.semi_structured.template_ko_builder import template_ko_builder
from graph_builder.canonical import canonical_graph_builder

def test_medical_bill_amit_singh_extraction():
    text = """
Lilavati Hospital
Bandra Reclamation, Mumbai, Maharashtra 400050
NPI: 1482950384 | Phone: (555) 019-8372

PATIENT ACCOUNT STATEMENT
Statement Date: 05/22/2026 Primary Insurance: HDFC ERGO General Insurance
Guarantor No: MRN-1039485 Group No: GRP-2960
Patient Name: Amit Singh Primary Diagnosis: Hyperlipidemia
Date of Birth: 1978-11-03 ICD-10 Code: E78.5

Date CPT Description Charges
05/22/2026 0260 IV Therapy $243.00
05/22/2026 99283 Emergency Room Level 3 $801.00
05/22/2026 36415 Venipuncture $15.00

Total Billed Charges: $1508.00
Insurance Adjustments: -$1309.00
PATIENT AMOUNT DUE: $199.00
"""
    tmpl = template_manager.get_template("medical_bill")
    fields, errors = template_extractor.extract(text, tmpl)

    assert fields.get("mrn") == "MRN-1039485"
    assert fields.get("patient_name") == "Amit Singh"
    assert fields.get("provider_name") == "Lilavati Hospital"
    assert fields.get("primary_diagnosis") == "Hyperlipidemia"
    assert fields.get("icd_code") == "E78.5"
    assert fields.get("insurance_name") == "HDFC ERGO General Insurance"
    assert fields.get("total_amount") == 1508.00

    ocr_res = OCRResult(document_id="doc_bill_amit", source_path="bill_amit.jpg", full_text=text, normalized_text=text, pages=[OCRPage(page_number=1, text=text)])
    kos = template_ko_builder.build_knowledge_objects(fields, tmpl, ocr_res)

    patient_ko = next((k for k in kos if k.entity_type == "Patient"), None)
    assert patient_ko is not None
    assert "Amit Singh" in patient_ko.properties["name"]
    assert "MRN-1039485" in patient_ko.properties["name"]

    hospital_ko = next((k for k in kos if k.entity_type == "Hospital"), None)
    assert hospital_ko is not None
    assert hospital_ko.properties["name"] == "Lilavati Hospital"

    condition_ko = next((k for k in kos if k.entity_type == "Condition"), None)
    assert condition_ko is not None
    assert "Hyperlipidemia" in condition_ko.properties["name"]
    assert "E78.5" in condition_ko.properties["name"]


def test_discharge_summary_vikram_reddy_extraction():
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
    tmpl = template_manager.get_template("discharge_summary")
    fields, errors = template_extractor.extract(text, tmpl)

    assert fields.get("mrn") == "MRN-3920184"
    assert fields.get("patient_name") == "Vikram Reddy"
    assert fields.get("provider_name") == "Christian Medical College (CMC)"
    assert fields.get("primary_diagnosis") == "Osteoarthritis of Knee"
    assert fields.get("icd_code") == "M17.9"
    assert fields.get("attending_physician") == "Dr. Jonathan H. Carter, MD"

    ocr_res = OCRResult(document_id="doc_ds_vikram", source_path="ds_vikram.jpg", full_text=text, normalized_text=text, pages=[OCRPage(page_number=1, text=text)])
    kos = template_ko_builder.build_knowledge_objects(fields, tmpl, ocr_res)

    patient_ko = next((k for k in kos if k.entity_type == "Patient"), None)
    assert patient_ko is not None
    assert "Vikram Reddy" in patient_ko.properties["name"]

    doctor_ko = next((k for k in kos if k.entity_type == "Doctor"), None)
    assert doctor_ko is not None
    assert doctor_ko.properties["name"] == "Dr. Jonathan H. Carter, MD"

    meds = [k for k in kos if k.entity_type == "Medication"]
    assert len(meds) >= 2
    med_names = [m.properties["name"] for m in meds]
    assert any("Meloxicam" in m for m in med_names)


def test_cross_document_mrn_and_icd_canonicalization():
    text1 = "Lilavati Hospital\nPatient Name: Amit Singh\nMRN: MRN-1039485\nDiagnosis: Hyperlipidemia\nICD-10: E78.5\nTotal: $500"
    text2 = "CMC Hospital\nPatient Name: Amit Singh\nMRN: MRN-1039485\nDiagnosis: Hyperlipidemia\nICD-10: E78.5\nDischarge Date: 05/22/2026"

    tmpl1 = template_manager.get_template("medical_bill")
    tmpl2 = template_manager.get_template("discharge_summary")

    f1, _ = template_extractor.extract(text1, tmpl1)
    f2, _ = template_extractor.extract(text2, tmpl2)

    ocr1 = OCRResult(document_id="doc1", source_path="doc1.jpg", full_text=text1, normalized_text=text1, pages=[OCRPage(page_number=1, text=text1)])
    ocr2 = OCRResult(document_id="doc2", source_path="doc2.jpg", full_text=text2, normalized_text=text2, pages=[OCRPage(page_number=1, text=text2)])

    kos1 = template_ko_builder.build_knowledge_objects(f1, tmpl1, ocr1)
    kos2 = template_ko_builder.build_knowledge_objects(f2, tmpl2, ocr2)

    p1 = next(k for k in kos1 if k.entity_type == "Patient")
    p2 = next(k for k in kos2 if k.entity_type == "Patient")
    assert p1.canonical_id == p2.canonical_id

    c1 = next(k for k in kos1 if k.entity_type == "Condition")
    c2 = next(k for k in kos2 if k.entity_type == "Condition")
    assert c1.canonical_id == c2.canonical_id


def test_no_chunk_or_page_nodes_in_canonical_graph():
    text = "Lilavati Hospital\nPatient Name: Amit Singh\nMRN: MRN-1039485"
    tmpl = template_manager.get_template("medical_bill")
    fields, _ = template_extractor.extract(text, tmpl)

    ocr_res = OCRResult(document_id="doc1", source_path="doc1.jpg", full_text=text, normalized_text=text, pages=[OCRPage(page_number=1, text=text)])
    kos = template_ko_builder.build_knowledge_objects(fields, tmpl, ocr_res)

    nodes, edges = canonical_graph_builder.build_graph(kos, ocr_res)

    node_labels = {n.label for n in nodes}
    edge_types = {e.type for e in edges}

    # Strict no-chunk and no-page guarantee
    assert "Page" not in node_labels
    assert "Chunk" not in node_labels
    assert "HAS_PAGE" not in edge_types
    assert "HAS_CHUNK" not in edge_types
    assert "MENTIONS" not in edge_types
