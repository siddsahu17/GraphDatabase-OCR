import os
import json
from typing import Dict, Any, List, Optional, Tuple
from common.logger import get_logger
from ingestion.unstructured.llm.gateway import llm_gateway
from ingestion.semi_structured.kv_extraction import kv_extractor
from models.domain import OCRResult, SemanticObject, Confidence

logger = get_logger(__name__)

class BusinessSchemaExtractor:
    """
    Generic branch business schema extractor (§6A.4).
    Uses LLM Gateway + Workspace Semantic Memory to extract structured KOs from generic document layout.
    """

    def load_semantic_memory(self, workspace_id: str = "default") -> Dict[str, Any]:
        path = os.path.abspath(f"data/workspaces/semantic_memory/{workspace_id}.json")
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                return {}
        return {}

    def extract_generic_kos(
        self,
        ocr_result: OCRResult,
        workspace_id: str = "default"
    ) -> List[SemanticObject]:
        
        raw_text = ocr_result.normalized_text or ocr_result.full_text or ""
        kv_pairs = kv_extractor.extract_kv_pairs(raw_text)
        semantic_mem = self.load_semantic_memory(workspace_id)

        system_prompt = (
            "You are an expert Information Extraction & Knowledge Graph System. "
            "Extract business entities, properties, and relationships from document text. "
            "Use consistent entity type labels (e.g. Patient, Invoice, Vendor, Customer, Hospital, MedicalBill, Condition, Medication, Procedure). "
            f"Existing Workspace Semantic Memory Labels: {json.dumps(semantic_mem.get('labels', []))}. "
            "Return JSON format: {\"nodes\": [{\"label\": string, \"id\": string, \"properties\": dict}], \"relationships\": [{\"from_label\": string, \"from_id\": string, \"type\": string, \"to_label\": string, \"to_id\": string}]}"
        )

        user_prompt = f"DOCUMENT TEXT:\n{raw_text[:3500]}\n\nEXTRACTED KEY-VALUE HINTS:\n{json.dumps(dict(kv_pairs[:20]))}"

        try:
            res_json = llm_gateway.generate_json(system_prompt, user_prompt)
            nodes = res_json.get("nodes", [])
            rels = res_json.get("relationships", [])

            provenance = {
                "document_id": ocr_result.document_id,
                "source_path": ocr_result.source_path,
                "page_number": 1,
                "engine_used": ocr_result.engine_used,
                "template_domain": "generic",
                "extraction_method": "generic_llm_schema"
            }

            kos: List[SemanticObject] = []
            node_id_map: Dict[str, str] = {}

            for n in nodes:
                lbl = n.get("label", "Entity")
                raw_id = str(n.get("id", f"{lbl}_{len(kos)}"))
                props = n.get("properties", {})
                props["id"] = raw_id

                cid = f"{lbl.lower()}_{hash(raw_id) & 0xffffffff:08x}"
                node_id_map[raw_id] = cid

                kos.append(SemanticObject(
                    canonical_id=cid,
                    entity=raw_id,
                    entity_type=lbl,
                    properties=props,
                    relationships=[],
                    confidence=Confidence(overall=0.85),
                    provenance=provenance,
                    validation_status="approved"
                ))

            for r in rels:
                from_id = node_id_map.get(str(r.get("from_id")), str(r.get("from_id")))
                to_id = node_id_map.get(str(r.get("to_id")), str(r.get("to_id")))

                for ko in kos:
                    if ko.canonical_id == from_id or ko.entity == str(r.get("from_id")):
                        ko.relationships.append({
                            "from_label": r.get("from_label"),
                            "from_id": from_id,
                            "type": r.get("type", "RELATED_TO"),
                            "to_label": r.get("to_label"),
                            "to_id": to_id
                        })

            return kos

        except Exception as e:
            logger.warning(f"LLM generic schema extraction error: {e}. Generating fallback generic KOs.")
            return self._fallback_generic_kos(ocr_result, kv_pairs)

    def _fallback_generic_kos(self, ocr_result: OCRResult, kv_pairs: List[Tuple[str, str]]) -> List[SemanticObject]:
        props = dict(kv_pairs[:10])
        cid = f"document_{ocr_result.document_id[:10]}"
        props["document_id"] = ocr_result.document_id
        
        return [
            SemanticObject(
                canonical_id=cid,
                entity=os.path.basename(ocr_result.source_path),
                entity_type="Document",
                properties=props,
                relationships=[],
                confidence=Confidence(overall=0.7),
                provenance={
                    "document_id": ocr_result.document_id,
                    "source_path": ocr_result.source_path,
                    "page_number": 1,
                    "engine_used": ocr_result.engine_used,
                    "template_domain": "generic",
                    "extraction_method": "kv_fallback"
                },
                validation_status="approved"
            )
        ]

business_schema_extractor = BusinessSchemaExtractor()
