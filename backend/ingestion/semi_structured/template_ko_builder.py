from typing import Dict, Any, List
from models.domain import SemanticObject, Confidence, OCRResult
from storage.entity_registry_store import entity_registry_store
from common.logger import get_logger

logger = get_logger(__name__)

class TemplateKOBuilder:
    """
    Constructs Knowledge Objects (SemanticObject) from template-extracted fields (§8 & §9A).
    Enforces deterministic identity resolution using registered business keys.
    """
    
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
        entity_canonical_map: Dict[str, str] = {}  # entity_type -> canonical_id

        provenance_base = {
            "document_id": ocr_result.document_id,
            "source_path": ocr_result.source_path,
            "page_number": 1,
            "engine_used": ocr_result.engine_used,
            "template_domain": domain,
            "extraction_method": "template_regex"
        }

        # 1. Build Entity SemanticObjects
        for espec in entities_spec:
            etype = espec.get("type", "Entity")
            bkeys = espec.get("business_key", [])
            prop_names = espec.get("properties", [])

            # Construct business key string
            bkey_parts = []
            for bk in bkeys:
                v = extracted_fields.get(bk)
                if v:
                    bkey_parts.append(str(v))
            
            bkey_val = "-".join(bkey_parts) if bkey_parts else extracted_fields.get("document_id", ocr_result.document_id)

            # Deterministic Identity Resolution (§9A)
            canonical_id = entity_registry_store.get_or_create_canonical_id(etype, bkey_val)
            entity_canonical_map[etype] = canonical_id

            # Gather entity properties
            props = {}
            for pname in prop_names:
                if pname in extracted_fields and extracted_fields[pname] is not None:
                    props[pname] = extracted_fields[pname]
            props["id"] = canonical_id

            kos.append(SemanticObject(
                canonical_id=canonical_id,
                entity=bkey_val or canonical_id,
                entity_type=etype,
                properties=props,
                relationships=[],
                confidence=Confidence(overall=1.0 if validation_status == "approved" else 0.7),
                provenance=provenance_base,
                validation_status=validation_status
            ))

        # 2. Build Relationships
        for rel_spec in relationships_spec:
            from_type = rel_spec.get("from")
            to_type = rel_spec.get("to")
            rel_type = rel_spec.get("type", "RELATED_TO")

            from_cid = entity_canonical_map.get(from_type)
            to_cid = entity_canonical_map.get(to_type)

            if from_cid and to_cid:
                # Find source SemanticObject and attach relationship
                for ko in kos:
                    if ko.canonical_id == from_cid:
                        ko.relationships.append({
                            "from_label": from_type,
                            "from_id": from_cid,
                            "type": rel_type,
                            "to_label": to_type,
                            "to_id": to_cid
                        })

        return kos

template_ko_builder = TemplateKOBuilder()
