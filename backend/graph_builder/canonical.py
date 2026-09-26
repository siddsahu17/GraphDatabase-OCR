import os
import time
from typing import List, Dict, Any, Tuple
from models.domain import SemanticObject, GraphNode, GraphEdge, OCRResult
from graph.label_resolver import label_resolver
from common.logger import get_logger

logger = get_logger(__name__)

class CanonicalGraphBuilder:
    """
    CanonicalGraphBuilder (§10) converts approved SemanticObjects and OCRResult
    into GraphNode and GraphEdge instances with full provenance graph support:
    (:Document) -> [:HAS_PAGE] -> (:Page) -> [:HAS_CHUNK] -> (:Chunk) <- [:MENTIONS] - (:Entity)
    """

    def build_graph(
        self,
        knowledge_objects: List[SemanticObject],
        ocr_result: OCRResult,
        workspace_id: str = "default"
    ) -> Tuple[List[GraphNode], List[GraphEdge]]:

        nodes: List[GraphNode] = []
        edges: List[GraphEdge] = []
        now_str = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

        # 1. BUILD PROVENANCE LAYER NODES & EDGES (§10)
        doc_id = ocr_result.document_id
        
        # Determine domain root hub for domain connectivity
        domain_name = "medical"
        if knowledge_objects:
            domain_name = knowledge_objects[0].provenance.get("template_domain", "medical")
        
        domain_clean = "invoice" if "invoice" in str(domain_name).lower() else "medical"
        domain_hub_id = f"domain_{domain_clean}_graph"
        domain_hub_name = "Invoice Knowledge Network" if domain_clean == "invoice" else "Medical Knowledge Network"
        
        domain_node = GraphNode(
            id=domain_hub_id,
            label="DomainGraph",
            properties={
                "id": domain_hub_id,
                "name": domain_hub_name,
                "domain": domain_clean
            },
            workspace_id=workspace_id
        )
        nodes.append(domain_node)

        doc_filename = os.path.basename(ocr_result.source_path) if ocr_result.source_path else doc_id[:8]
        doc_node = GraphNode(
            id=doc_id,
            label="Document",
            properties={
                "id": doc_id,
                "name": f"Document ({doc_filename})",
                "source_path": ocr_result.source_path,
                "mime_type": ocr_result.mime_type,
                "engine_used": ocr_result.engine_used,
                "page_count": ocr_result.page_count,
                "ingested_at": now_str
            },
            workspace_id=workspace_id
        )
        nodes.append(doc_node)

        # Connect Document to central DomainGraph hub
        edges.append(GraphEdge(
            from_id=doc_id,
            from_label="Document",
            type="IN_DOMAIN",
            to_id=domain_hub_id,
            to_label="DomainGraph",
            workspace_id=workspace_id
        ))

        # 2. BUILD BUSINESS ENTITIES & RELATIONSHIPS FROM NON-REJECTED KOs
        for ko in knowledge_objects:
            if ko.validation_status == "rejected":
                continue

            clean_label = label_resolver.sanitize_label(ko.entity_type)
            ko_id = ko.canonical_id

            node_props = dict(ko.properties)
            node_props["id"] = ko_id
            
            # Ensure name is human-readable and filter out raw document hashes
            raw_name = node_props.get("name") or ko.entity
            if len(str(raw_name)) >= 64 and str(raw_name) == doc_id:
                raw_name = f"{clean_label} Record"
            node_props["name"] = str(raw_name)

            b_node = GraphNode(
                id=ko_id,
                label=clean_label,
                properties=node_props,
                workspace_id=workspace_id
            )
            nodes.append(b_node)

            # Link major entities to DomainGraph hub to unify subgraphs
            if clean_label in ("Patient", "Vendor", "Hospital", "Customer"):
                edges.append(GraphEdge(
                    from_id=ko_id,
                    from_label=clean_label,
                    type="IN_DOMAIN",
                    to_id=domain_hub_id,
                    to_label="DomainGraph",
                    workspace_id=workspace_id
                ))

            # Link entity to Document provenance
            edges.append(GraphEdge(
                from_id=ko_id,
                from_label=clean_label,
                type="EXTRACTED_FROM",
                to_id=doc_id,
                to_label="Document",
                properties={
                    "confidence": ko.confidence.overall,
                    "method": ko.provenance.get("extraction_method", "unknown")
                },
                workspace_id=workspace_id
            ))

            # Business relationships with edge properties
            for rel in ko.relationships:
                from_lbl = label_resolver.sanitize_label(rel.get("from_label", clean_label))
                to_lbl = label_resolver.sanitize_label(rel.get("to_label", "Entity"))
                rel_type = label_resolver.sanitize_rel_type(rel.get("type", "RELATED_TO"))
                rel_props = rel.get("properties", {})

                edges.append(GraphEdge(
                    from_id=str(rel.get("from_id", ko_id)),
                    from_label=from_lbl,
                    type=rel_type,
                    to_id=str(rel.get("to_id")),
                    to_label=to_lbl,
                    properties=rel_props,
                    workspace_id=workspace_id
                ))

        return nodes, edges

canonical_graph_builder = CanonicalGraphBuilder()
