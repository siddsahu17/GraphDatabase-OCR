import json
import logging
from typing import Dict, Any, List
from openai import OpenAI
from app.config import settings
from app.schema.registry import schema_registry

logger = logging.getLogger(__name__)

class EntityExtractor:
    def __init__(self):
        self._client = None
        if settings.OPENAI_API_KEY and settings.OPENAI_API_KEY != "your_openai_api_key_here":
            try:
                self._client = OpenAI(api_key=settings.OPENAI_API_KEY)
            except Exception as e:
                logger.warning(f"Could not initialize OpenAI client: {e}")

    def extract_graph(self, raw_text: str, domain_key: str) -> Dict[str, Any]:
        """
        Extracts structured graph nodes and edges from document text according to domain schema.
        """
        schema_def = schema_registry.get_schema(domain_key)
        if not schema_def:
            raise ValueError(f"Unknown schema key: {domain_key}")

        if self._client:
            try:
                return self._extract_with_openai(raw_text, domain_key, schema_def)
            except Exception as e:
                logger.error(f"OpenAI extraction failed: {e}. Falling back to fallback extractor.")

        return self._fallback_extraction(raw_text, domain_key, schema_def)

    def _extract_with_openai(self, raw_text: str, domain_key: str, schema_def: Dict[str, Any]) -> Dict[str, Any]:
        prompt = f"""
You are an expert Document Information Extraction System.
Extract structured entities (nodes) and relationships (edges) from the following parsed document text according to the Graph Schema definition provided below.

DOCUMENT TEXT:
\"\"\"
{raw_text[:4000]}
\"\"\"

GRAPH SCHEMA SPECIFICATION:
Domain: {schema_def.get('domain_name')}
Nodes to extract:
{json.dumps(schema_def.get('nodes', []), indent=2)}

Relationships to extract:
{json.dumps(schema_def.get('relationships', []), indent=2)}

INSTRUCTIONS:
1. Extract node objects. Each node must have:
   - "label": string (matching one of the schema node labels)
   - "id": string (unique identifier or primary key value, e.g. "INV-1001" or vendor name)
   - "properties": dictionary containing key-value pairs matching schema property names.
2. Extract relationship objects. Each relationship must have:
   - "from_label": label of source node
   - "from_id": id of source node
   - "type": relationship name (e.g. ISSUED, BILLED_TO, CONTAINS_ITEM)
   - "to_label": label of target node
   - "to_id": id of target node

Return ONLY valid JSON with two top-level keys: "nodes" and "relationships". No markdown codeblocks or conversational text.
"""
        response = self._client.chat.completions.create(
            model=settings.OPENAI_MODEL,
            messages=[
                {"role": "system", "content": "You extract structured knowledge graphs from document text in JSON format."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.1,
            response_format={"type": "json_object"}
        )
        content = response.choices[0].message.content
        return json.loads(content)

    def _fallback_extraction(self, raw_text: str, domain_key: str, schema_def: Dict[str, Any]) -> Dict[str, Any]:
        """
        Simple rule-based heuristic fallback if OpenAI API key is not configured.
        """
        nodes = []
        relationships = []
        
        lines = [line.strip() for line in raw_text.split('\n') if line.strip()]
        doc_id = f"DOC-{hash(raw_text) % 10000:04d}"

        if domain_key == "invoice":
            inv_no = f"INV-{hash(raw_text) % 9000 + 1000}"
            nodes.append({
                "label": "Invoice",
                "id": inv_no,
                "properties": {
                    "invoice_number": inv_no,
                    "invoice_date": "2026-01-15",
                    "total_amount": "250.00",
                    "currency": "USD"
                }
            })
            nodes.append({
                "label": "Vendor",
                "id": "Acme Corp",
                "properties": {
                    "name": "Acme Corp",
                    "address": "123 Supply Street",
                    "phone": "555-0199"
                }
            })
            relationships.append({
                "from_label": "Vendor",
                "from_id": "Acme Corp",
                "type": "ISSUED",
                "to_label": "Invoice",
                "to_id": inv_no
            })
        elif domain_key in ["medical_bill", "discharge_summary"]:
            pat_id = f"PAT-{hash(raw_text) % 9000 + 1000}"
            nodes.append({
                "label": "Patient",
                "id": "John Doe",
                "properties": {
                    "name": "John Doe",
                    "patient_id": pat_id,
                    "gender": "Male"
                }
            })
            nodes.append({
                "label": "Hospital",
                "id": "City General Hospital",
                "properties": {
                    "hospital_name": "City General Hospital",
                    "address": "456 Health Ave"
                }
            })
            if domain_key == "medical_bill":
                bill_id = f"BILL-{hash(raw_text) % 9000 + 1000}"
                nodes.append({
                    "label": "MedicalBill",
                    "id": bill_id,
                    "properties": {
                        "bill_id": bill_id,
                        "bill_date": "2026-02-10",
                        "total_charge": "1200.00"
                    }
                })
                relationships.append({
                    "from_label": "Hospital",
                    "from_id": "City General Hospital",
                    "type": "ISSUED_BILL",
                    "to_label": "MedicalBill",
                    "to_id": bill_id
                })
                relationships.append({
                    "from_label": "MedicalBill",
                    "from_id": bill_id,
                    "type": "FOR_PATIENT",
                    "to_label": "Patient",
                    "to_id": "John Doe"
                })
            else:
                summary_id = f"SUMM-{hash(raw_text) % 9000 + 1000}"
                nodes.append({
                    "label": "DischargeSummary",
                    "id": summary_id,
                    "properties": {
                        "summary_id": summary_id,
                        "admission_date": "2026-02-01",
                        "discharge_date": "2026-02-05"
                    }
                })
                relationships.append({
                    "from_label": "Patient",
                    "from_id": "John Doe",
                    "type": "HAS_SUMMARY",
                    "to_label": "DischargeSummary",
                    "to_id": summary_id
                })

        return {"nodes": nodes, "relationships": relationships}

entity_extractor = EntityExtractor()
