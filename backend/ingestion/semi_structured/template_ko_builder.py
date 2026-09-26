from typing import Dict, Any, List
from models.domain import SemanticObject, Confidence, OCRResult
from storage.entity_registry_store import entity_registry_store
from common.logger import get_logger

logger = get_logger(__name__)

class TemplateKOBuilder:
    """
    Constructs Knowledge Objects (SemanticObject) from template-extracted fields (§8 & §9A).
    Enforces deterministic identity resolution across domain entities to build a unified connected graph.
    """
    
    def _format_doctor_name(self, doc_str: str) -> str:
        import re
        if not doc_str:
            return ""
        words = doc_str.strip().split()
        medical_acronyms = {"md", "do", "mbbs", "phd", "rn", "facs", "facp", "np", "pa", "ms", "bs", "dso"}
        formatted_words = []
        for word in words:
            clean_word = re.sub(r'[^a-zA-Z]', '', word).lower()
            if clean_word == "phd":
                formatted = re.sub(r'[a-zA-Z]+', "PhD", word)
                formatted_words.append(formatted)
            elif clean_word in medical_acronyms:
                formatted = re.sub(r'[a-zA-Z]+', clean_word.upper(), word)
                formatted_words.append(formatted)
            elif word.lower() in ("dr.", "dr"):
                formatted_words.append("Dr.")
            elif word.isupper() and len(word) <= 3:
                formatted_words.append(word)
            else:
                formatted_words.append(word.capitalize())
        return " ".join(formatted_words)

    
    def _format_organization_name(self, org_str: str) -> str:
        import re
        if not org_str:
            return ""
        cleaned = org_str.strip()
        words = cleaned.split()
        formatted = []
        for w in words:
            if re.match(r'^\([A-Z0-9-]+\)$', w):
                formatted.append(w)
            elif w.isupper() and len(w) <= 5:
                formatted.append(w)
            elif any(c.isupper() for c in w) and any(c.islower() for c in w):
                formatted.append(w)
            else:
                formatted.append(w.capitalize())
        return " ".join(formatted)

    def _format_text_name(self, text_str: str) -> str:
        if not text_str:
            return ""
        cleaned = text_str.strip()
        if any(c.isupper() for c in cleaned) and any(c.islower() for c in cleaned):
            return cleaned
        return cleaned.title()

    def build_knowledge_objects(
        self,
        extracted_fields: Dict[str, Any],
        template: Dict[str, Any],
        ocr_result: OCRResult,
        validation_status: str = "approved"
    ) -> List[SemanticObject]:
        
        entities_spec = template.get("entities", [])
        relationships_spec = template.get("relationships", [])
        domain = template.get("domain", "template_generic")
        
        kos: List[SemanticObject] = []
        entity_canonical_map: Dict[str, str] = {}

        provenance_base = {
            "document_id": ocr_result.document_id,
            "source_path": ocr_result.source_path,
            "page_number": 1,
            "engine_used": ocr_result.engine_used,
            "template_domain": domain,
            "extraction_method": "template_hybrid"
        }

        # 1. Build Entity SemanticObjects with Shared Canonical Resolution
        for espec in entities_spec:
            etype = espec.get("type", "Entity")
            bkeys = espec.get("business_key", [])
            prop_names = espec.get("properties", [])

            # Construct business key string deterministically
            bkey_val = None
            display_name = None

            doc_short = ocr_result.document_id[:8]

            if etype == "Patient":
                mrn = extracted_fields.get("mrn")
                pname = extracted_fields.get("patient_name")
                if mrn:
                    clean_mrn = str(mrn).strip().upper()
                    bkey_val = f"mrn_{clean_mrn.lower()}"
                    if pname:
                        clean_pname = self._format_text_name(str(pname))
                        display_name = f"{clean_pname} (MRN: {clean_mrn})"
                    else:
                        display_name = f"Patient {clean_mrn}"
                elif pname:
                    clean_pname = self._format_text_name(str(pname))
                    bkey_val = f"name_{clean_pname.lower()}"
                    display_name = clean_pname
                else:
                    bkey_val = f"patient_{doc_short}"
                    display_name = f"Patient ({doc_short})"

            elif etype == "Condition":
                diag = extracted_fields.get("primary_diagnosis") or extracted_fields.get("admission_diagnosis")
                icd = extracted_fields.get("icd_code")
                if icd:
                    clean_icd = str(icd).strip().upper()
                    bkey_val = f"icd_{clean_icd.lower()}"
                    if diag:
                        clean_diag = self._format_text_name(str(diag))
                        display_name = f"{clean_diag} ({clean_icd})"
                    else:
                        display_name = f"Condition {clean_icd}"
                elif diag:
                    clean_diag = self._format_text_name(str(diag))
                    bkey_val = f"diag_{clean_diag.lower()}"
                    display_name = clean_diag
                else:
                    bkey_val = f"condition_{doc_short}"
                    display_name = "Condition (General Diagnosis)"

            elif etype == "Hospital":
                prov = extracted_fields.get("provider_name")
                if prov:
                    clean_prov = self._format_organization_name(str(prov))
                    bkey_val = f"hospital_{clean_prov.lower()}"
                    display_name = clean_prov
                else:
                    bkey_val = f"hospital_{doc_short}"
                    display_name = "Hospital (Medical Center)"

            elif etype == "Insurance":
                ins = extracted_fields.get("insurance_name")
                grp = extracted_fields.get("group_no")
                if ins:
                    clean_ins = self._format_organization_name(str(ins))
                    bkey_val = f"ins_{clean_ins.lower()}"
                    if grp:
                        display_name = f"{clean_ins} (Group: {grp})"
                    else:
                        display_name = clean_ins
                else:
                    bkey_val = f"insurance_{doc_short}"
                    display_name = "Primary Insurance"

            elif etype == "Doctor":
                doc = extracted_fields.get("attending_physician")
                if doc:
                    clean_doc = self._format_doctor_name(str(doc))
                    bkey_val = f"doc_{clean_doc.lower()}"
                    display_name = clean_doc
                else:
                    bkey_val = f"doctor_{doc_short}"
                    display_name = "Attending Physician"

            elif etype == "Vendor":
                vname = extracted_fields.get("vendor_name")
                vtax = extracted_fields.get("vendor_tax_id")
                if vtax:
                    clean_vtax = str(vtax).strip().upper()
                    bkey_val = f"tax_{clean_vtax.lower()}"
                    if vname:
                        clean_vname = self._format_organization_name(str(vname))
                        display_name = f"{clean_vname} (Tax ID: {clean_vtax})"
                    else:
                        display_name = f"Vendor {clean_vtax}"
                elif vname:
                    clean_vname = self._format_organization_name(str(vname))
                    bkey_val = f"vendor_{clean_vname.lower()}"
                    display_name = clean_vname
                else:
                    bkey_val = f"vendor_{doc_short}"
                    display_name = "Vendor (Primary)"

            elif etype == "Customer":
                cname = extracted_fields.get("customer_name")
                if cname:
                    clean_cname = self._format_organization_name(str(cname))
                    bkey_val = f"customer_{clean_cname.lower()}"
                    display_name = clean_cname
                else:
                    bkey_val = f"customer_{doc_short}"
                    display_name = "Customer (Primary)"

            else:
                # Per-document record entities (DischargeSummary, MedicalBill, Invoice)
                bkey_parts = []
                for bk in bkeys:
                    v = extracted_fields.get(bk)
                    if v:
                        bkey_parts.append(str(v).strip())
                
                doc_short = ocr_result.document_id[:8]
                total_amt = extracted_fields.get("total_amount")
                amt_str = f" (${total_amt:.2f})" if isinstance(total_amt, (int, float)) and total_amt > 0 else ""

                if etype == "MedicalBill":
                    bill_no = extracted_fields.get("bill_no")
                    clean_bno = str(bill_no).strip().upper() if bill_no else ""
                    if clean_bno and clean_bno not in ("STATEMENT", "ACCOUNT", "BILL", "PATIENT STATEMENT", "PATIENT ACCOUNT STATEMENT"):
                        bkey_val = f"bill_{clean_bno.lower()}"
                        display_name = f"Bill #{clean_bno}{amt_str}"
                    else:
                        bkey_val = f"bill_{doc_short}"
                        display_name = f"Medical Bill Statement{amt_str}"

                elif etype == "DischargeSummary":
                    sum_id = extracted_fields.get("summary_id")
                    diag = extracted_fields.get("primary_diagnosis")
                    clean_sid = str(sum_id).strip().upper() if sum_id else ""
                    if clean_sid and clean_sid not in ("SUMMARY", "DISCHARGE", "RECORD", "DISCHARGE SUMMARY", "SUMMARY ID"):
                        bkey_val = f"ds_{clean_sid.lower()}"
                        display_name = f"Discharge Summary #{clean_sid}"
                    elif diag:
                        bkey_val = f"ds_{doc_short}"
                        display_name = f"Discharge Summary ({str(diag).title()})"
                    else:
                        bkey_val = f"ds_{doc_short}"
                        display_name = "Clinical Discharge Summary"

                elif etype == "Invoice":
                    inv_no = extracted_fields.get("invoice_no")
                    clean_ino = str(inv_no).strip().upper() if inv_no else ""
                    if clean_ino and clean_ino not in ("INVOICE", "STATEMENT", "BILL"):
                        bkey_val = f"inv_{clean_ino.lower()}"
                        display_name = f"Invoice #{clean_ino}{amt_str}"
                    else:
                        bkey_val = f"inv_{doc_short}"
                        display_name = f"Commercial Invoice{amt_str}"
                else:
                    if bkey_parts:
                        bkey_val = f"{etype.lower()}_{'-'.join(bkey_parts)}"
                        display_name = f"{etype} {'-'.join(bkey_parts)}"
                    else:
                        bkey_val = f"{etype.lower()}_{doc_short}"
                        display_name = f"{etype} Record"

            # Deterministic Identity Resolution (§9A)
            canonical_id = entity_registry_store.get_or_create_canonical_id(etype, bkey_val)
            entity_canonical_map[etype] = canonical_id

            # Gather entity properties
            props = {}
            for pname_key in prop_names:
                if pname_key in extracted_fields and extracted_fields[pname_key] is not None:
                    props[pname_key] = extracted_fields[pname_key]
            
            props["id"] = canonical_id
            
            # Ensure a clean readable name property exists
            readable_name = (
                display_name or
                props.get("patient_name") or
                props.get("provider_name") or
                props.get("vendor_name") or
                props.get("primary_diagnosis") or
                props.get("bill_no") or
                props.get("invoice_no") or
                props.get("name") or
                f"{etype} Record"
            )
            props["name"] = str(readable_name)

            kos.append(SemanticObject(
                canonical_id=canonical_id,
                entity=str(readable_name),
                entity_type=etype,
                properties=props,
                relationships=[],
                confidence=Confidence(overall=1.0 if validation_status == "approved" else 0.7),
                provenance=provenance_base,
                validation_status=validation_status
            ))

        # 2. Build LineItem KOs from extracted line items
        line_items = extracted_fields.get("line_items", [])
        parent_cid = entity_canonical_map.get("MedicalBill") or entity_canonical_map.get("Invoice")
        parent_type = "MedicalBill" if "MedicalBill" in entity_canonical_map else "Invoice"

        if line_items and parent_cid:
            doc_short = ocr_result.document_id[:8]
            for idx, item in enumerate(line_items, 1):
                desc = item.get("description", f"Line Item #{idx}")
                amt = item.get("amount", 0.0)
                li_bkey = f"li_{doc_short}_{idx}"
                li_canonical_id = entity_registry_store.get_or_create_canonical_id("LineItem", li_bkey)

                li_name = f"{desc} (${amt:.2f})" if isinstance(amt, (int, float)) and amt > 0 else desc
                li_props = {
                    "id": li_canonical_id,
                    "name": li_name,
                    "description": desc,
                    "qty": item.get("qty", 1),
                    "rate": item.get("rate", amt),
                    "amount": amt
                }

                li_ko = SemanticObject(
                    canonical_id=li_canonical_id,
                    entity=li_name,
                    entity_type="LineItem",
                    properties=li_props,
                    relationships=[],
                    confidence=Confidence(overall=1.0 if validation_status == "approved" else 0.7),
                    provenance=provenance_base,
                    validation_status=validation_status
                )
                kos.append(li_ko)

                # Connect parent record to LineItem
                for parent_ko in kos:
                    if parent_ko.canonical_id == parent_cid:
                        parent_ko.relationships.append({
                            "from_label": parent_type,
                            "from_id": parent_cid,
                            "type": "HAS_LINE_ITEM",
                            "to_label": "LineItem",
                            "to_id": li_canonical_id,
                            "properties": {"amount": amt}
                        })

        # 3. Build Medication KOs from extracted medications string
        meds_text = extracted_fields.get("medications")
        ds_cid = entity_canonical_map.get("DischargeSummary")
        if meds_text and ds_cid:
            med_lines = [line.strip(" •-\t") for line in str(meds_text).splitlines() if line.strip(" •-\t")]
            for idx, med_str in enumerate(med_lines, 1):
                if len(med_str) < 3:
                    continue
                med_bkey = f"med_{med_str.lower()}"
                med_cid = entity_registry_store.get_or_create_canonical_id("Medication", med_bkey)
                
                med_ko = SemanticObject(
                    canonical_id=med_cid,
                    entity=med_str.title(),
                    entity_type="Medication",
                    properties={"id": med_cid, "name": med_str.title()},
                    relationships=[],
                    confidence=Confidence(overall=1.0 if validation_status == "approved" else 0.7),
                    provenance=provenance_base,
                    validation_status=validation_status
                )
                kos.append(med_ko)

                for parent_ko in kos:
                    if parent_ko.canonical_id == ds_cid:
                        parent_ko.relationships.append({
                            "from_label": "DischargeSummary",
                            "from_id": ds_cid,
                            "type": "PRESCRIBED",
                            "to_label": "Medication",
                            "to_id": med_cid,
                            "properties": {}
                        })

        # 4. Build Relationships
        for rel_spec in relationships_spec:
            from_type = rel_spec.get("from")
            to_type = rel_spec.get("to")
            rel_type = rel_spec.get("type", "RELATED_TO")
            rel_prop_names = rel_spec.get("properties", [])

            from_cid = entity_canonical_map.get(from_type)
            to_cid = entity_canonical_map.get(to_type)

            rel_props = {}
            for rp in rel_prop_names:
                if rp in extracted_fields and extracted_fields[rp] is not None:
                    rel_props[rp] = extracted_fields[rp]

            if from_cid and to_cid:
                for ko in kos:
                    if ko.canonical_id == from_cid:
                        ko.relationships.append({
                            "from_label": from_type,
                            "from_id": from_cid,
                            "type": rel_type,
                            "to_label": to_type,
                            "to_id": to_cid,
                            "properties": rel_props
                        })

        return kos

template_ko_builder = TemplateKOBuilder()
