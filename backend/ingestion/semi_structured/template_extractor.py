import re
import json
from datetime import datetime
from typing import Dict, Any, List, Tuple, Optional
from common.logger import get_logger
from ingestion.unstructured.llm.gateway import llm_gateway

logger = get_logger(__name__)

class TemplateExtractor:
    """
    Deterministic template extractor for semi-structured documents.
    Extracts regex fields, coerces types, parses line items, runs validation checks,
    and falls back to LLM extraction if required fields are missing (§8 & §9A).
    """
    
    def coerce_value(self, val_str: str, ftype: str) -> Any:
        if not val_str:
            return None
            
        clean_str = val_str.strip()

        if ftype == "money":
            num_str = re.sub(r'[^\d\.]', '', clean_str)
            try:
                return float(num_str) if num_str else 0.0
            except ValueError:
                return 0.0

        elif ftype == "date":
            for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%d/%m/%Y", "%m-%d-%Y", "%d-%m-%Y"):
                try:
                    return datetime.strptime(clean_str, fmt).strftime("%Y-%m-%d")
                except ValueError:
                    continue
            return clean_str

        elif ftype == "integer":
            num_str = re.sub(r'[^\d]', '', clean_str)
            try:
                return int(num_str) if num_str else 0
            except ValueError:
                return 0

        elif ftype == "string":
            first_line = clean_str.split("\n")[0].strip()
            first_line = re.sub(r'(?i)\s+(?:mrn|patient id|summary id|bill no|statement|date|total).*$', '', first_line).strip()
            return first_line if first_line else None

        return clean_str

    def extract(self, text: str, template: Dict[str, Any]) -> Tuple[Dict[str, Any], List[str]]:
        """
        Extracts fields and line items from text using template specification.
        Uses hybrid regex + LLM fallback if regex misses required fields.
        """
        extracted = {}
        errors = []

        fields_def = template.get("fields", [])
        missing_fields = []

        for field in fields_def:
            fname = field.get("name")
            fregex = field.get("regex")
            ftype = field.get("type", "string")
            is_req = field.get("required", False)

            val = None
            if fregex:
                match = re.search(fregex, text)
                if match:
                    val_str = match.group(1) if match.groups() else match.group(0)
                    val = self.coerce_value(val_str, ftype)

            extracted[fname] = val
            if val is None or val == "":
                missing_fields.append((fname, ftype, is_req))

        # LLM Fallback for missing fields
        if missing_fields and text and len(text.strip()) > 10:
            domain = template.get("domain", "medical")
            missing_names = [f[0] for f in missing_fields]
            logger.info(f"Regex missed fields {missing_names} for domain '{domain}'. Triggering LLM extraction fallback.")
            
            system_prompt = (
                f"You are a Clinical & Invoice Information Extraction System. "
                f"Extract the following document fields accurately from the document text: {', '.join(missing_names)}. "
                f"Return JSON object where keys are field names and values are extracted strings or numbers."
            )
            user_prompt = f"DOCUMENT TEXT:\n{text[:3500]}"
            
            try:
                llm_res = llm_gateway.generate_json(system_prompt, user_prompt)
                for fname, ftype, is_req in missing_fields:
                    if fname in llm_res and llm_res[fname]:
                        extracted[fname] = self.coerce_value(str(llm_res[fname]), ftype)
            except Exception as e:
                logger.warning(f"LLM field extraction notice: {e}")

            # Heuristic pattern fallback for remaining missing fields
            remaining_missing = [f for f in missing_fields if not extracted.get(f[0])]
            if remaining_missing:
                self._heuristic_fallback(text, remaining_missing, extracted)

        # Final check for errors
        for field in fields_def:
            fname = field.get("name")
            is_req = field.get("required", False)
            if is_req and (extracted.get(fname) is None or extracted.get(fname) == ""):
                errors.append(f"Required field '{fname}' missing or could not be extracted.")

        # Extract line items table if specified
        line_items_spec = template.get("line_items", {})
        row_regex = line_items_spec.get("row_regex")
        cols = line_items_spec.get("columns", [])

        line_items = []
        if row_regex:
            for match in re.finditer(row_regex, text):
                groups = match.groups()
                if len(groups) >= len(cols):
                    item = {}
                    for i, col_name in enumerate(cols):
                        raw_col_val = (groups[i] or "").strip()
                        if "amount" in col_name or "rate" in col_name or "price" in col_name:
                            item[col_name] = self.coerce_value(raw_col_val, "money")
                        elif "qty" in col_name or "quantity" in col_name:
                            item[col_name] = self.coerce_value(raw_col_val, "integer")
                        else:
                            item[col_name] = raw_col_val
                    line_items.append(item)

        # Fallback line items extraction if regex missed
        if not line_items and text:
            for line in text.splitlines():
                m = re.search(r'([a-zA-Z0-9\s\.-]{3,35})\s+[\$\u20b9\u20ac]?\s*([\d\.,]+)', line)
                if m:
                    desc = m.group(1).strip()
                    amt = self.coerce_value(m.group(2), "money")
                    if amt and isinstance(amt, (int, float)) and amt > 0 and desc.lower() not in ("total", "subtotal", "amount due", "paid", "amount"):
                        line_items.append({"description": desc.title(), "qty": 1, "rate": amt, "amount": amt})
            line_items = line_items[:10]

        extracted["line_items"] = line_items

        # Run template validation checks if configured
        val_spec = template.get("validation", {})
        if "checks" in val_spec:
            total_amt = extracted.get("total_amount")
            if total_amt is not None and line_items:
                items_sum = sum(item.get("amount", 0.0) for item in line_items if isinstance(item.get("amount"), (int, float)))
                if items_sum > 0 and abs(items_sum - total_amt) > 1.0:
                    errors.append(f"Line items sum ({items_sum:.2f}) does not match total amount ({total_amt:.2f}).")

        return extracted, errors

    def _heuristic_fallback(self, text: str, missing_fields: List[Tuple[str, str, bool]], extracted: Dict[str, Any]):
        for fname, ftype, is_req in missing_fields:
            if extracted.get(fname):
                continue
            
            if fname == "total_amount" or ftype == "money":
                m = re.search(r'(?i)(?:total|amount|due|charge|net|paid)[:\s]*[\$\u20b9\u20ac]?\s*([\d\.,]+)', text)
                if not m:
                    m = re.search(r'[\$\u20b9\u20ac]\s*([\d\.,]+)', text)
                if m:
                    extracted[fname] = self.coerce_value(m.group(1), "money")

            elif fname in ("mrn", "patient_id"):
                m = re.search(r'\b(MRN-[0-9A-Z]+|P-[0-9A-Z]+|G-[0-9A-Z]+|#[0-9]{4,})\b', text, re.I)
                if not m:
                    m = re.search(r'(?i)(?:mrn|patient id|guarantor no|guarantor #|guarantor|account no|account #|account|patient #|id no|id #|id)[:\s#-]*([a-z0-9-]+)', text)
                if m:
                    extracted[fname] = m.group(1).upper()

            elif fname in ("bill_no", "invoice_no", "summary_id"):
                m = re.search(r'\b(BILL-[0-9A-Z]+|INV-[0-9A-Z]+|DS-[0-9A-Z]+|#[0-9]{4,})\b', text, re.I)
                if not m:
                    m = re.search(r'(?i)(?:bill\s*no|invoice\s*no|inv\s*#|summary\s*id|record\s*no|statement\s*no)[ \t]*[:#]?[ \t]*([a-z0-9-]+)', text)
                if m:
                    extracted[fname] = m.group(1).upper()

            elif fname == "patient_name":
                m = re.search(r'(?i)(?:patient name|patient\'s name|patient|guarantor name|guarantor|billed to|client)[:\s#-]*([a-zA-Z\s\.]+?)(?=\s*(?:mrn|dob|date|primary|admission|icd|group|\n|$))', text)
                cand_name = None
                if m:
                    cand_name = self.coerce_value(m.group(1), "string")
                if not cand_name:
                    for line in text.splitlines():
                        if re.search(r'(?i)\b(?:patient|guarantor|client)\b', line):
                            sub = re.search(r'\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,3})\b', line)
                            if sub:
                                cand_name = sub.group(1).strip()
                                break
                if cand_name and len(cand_name) > 2 and cand_name.lower() not in ("name", "patient", "summary", "hospital", "total", "guarantor", "patient account", "patient statement"):
                    extracted[fname] = cand_name

            elif fname in ("provider_name", "vendor_name"):
                for line in text.splitlines()[:5]:
                    line_clean = line.strip()
                    if re.search(r'(?i)(?:hospital|clinic|center|medical|institute|college|health|pharmacy|inc|corp|ltd)', line_clean):
                        extracted[fname] = line_clean
                        break

            elif fname == "primary_diagnosis":
                m = re.search(r'(?i)(?:primary diagnosis|admission diagnosis|diagnosis|impression)[:\s]*([a-zA-Z0-9\s,\.]+?)(?=\s*(?:icd|code|date|$))', text)
                if not m:
                    m = re.search(r'(?i)\b(hyperlipidemia|osteoarthritis|hypertension|diabetes|fever|infection|appendicitis|asthma|pneumonia|cardiac arrest|fracture|arrhythmia|migraine|bronchitis|anemia|stroke|gastritis)\b', text)
                if m:
                    val = m.group(1) if m.groups() else m.group(0)
                    extracted[fname] = self.coerce_value(val, "string")

            elif ftype == "date":
                m = re.search(r'(\d{1,2}[/-]\d{1,2}[/-]\d{2,4}|\d{4}-\d{2}-\d{2})', text)
                if m:
                    extracted[fname] = self.coerce_value(m.group(1), "date")

template_extractor = TemplateExtractor()
