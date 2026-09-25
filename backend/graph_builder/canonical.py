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
        doc_node = GraphNode(
            id=doc_id,
            label="Document",
            properties={
                "id": doc_id,
                "source_path": ocr_result.source_path,
                "mime_type": ocr_result.mime_type,
                "engine_used": ocr_result.engine_used,
                "page_count": ocr_result.page_count,
                "ingested_at": now_str
            },
            workspace_id=workspace_id
        )
        nodes.append(doc_node)

        # Build Page and Chunk nodes
        for page in ocr_result.pages:
            page_id = f"{doc_id}_p{page.page_number}"
            page_node = GraphNode(
                id=page_id,
                label="Page",
                properties={
                    "id": page_id,
                    "document_id": doc_id,
                    "page_number": page.page_number,
                    "mean_confidence": page.mean_confidence
                },
                workspace_id=workspace_id
            )
            nodes.append(page_node)
            edges.append(GraphEdge(
                from_id=doc_id,
                from_label="Document",
                type="HAS_PAGE",
                to_id=page_id,
                to_label="Page",
                workspace_id=workspace_id
            ))

            # Chunk node (300-500 token window)
            chunk_id = f"{page_id}_c1"
            chunk_node = GraphNode(
                id=chunk_id,
                label="Chunk",
                properties={
                    "id": chunk_id,
                    "document_id": doc_id,
                    "page_number": page.page_number,
                    "text": page.text[:1000]
                },
                workspace_id=workspace_id
            )
            nodes.append(chunk_node)
            edges.append(GraphEdge(
                from_id=page_id,
                from_label="Page",
                type="HAS_CHUNK",
                to_id=chunk_id,
                to_label="Chunk",
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
            node_props["name"] = ko.entity

            b_node = GraphNode(
                id=ko_id,
                label=clean_label,
                properties=node_props,
                workspace_id=workspace_id
            )
            nodes.append(b_node)

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

            # Link entity to Chunk provenance (MENTIONS)
            first_chunk_id = f"{doc_id}_p1_c1"
            edges.append(GraphEdge(
                from_id=ko_id,
                from_label=clean_label,
                type="MENTIONS",
                to_id=first_chunk_id,
                to_label="Chunk",
                workspace_id=workspace_id
            ))

            # Business relationships
            for rel in ko.relationships:
                from_lbl = label_resolver.sanitize_label(rel.get("from_label", clean_label))
                to_lbl = label_resolver.sanitize_label(rel.get("to_label", "Entity"))
                rel_type = label_resolver.sanitize_rel_type(rel.get("type", "RELATED_TO"))

                edges.append(GraphEdge(
                    from_id=str(rel.get("from_id", ko_id)),
                    from_label=from_lbl,
                    type=rel_type,
                    to_id=str(rel.get("to_id")),
                    to_label=to_lbl,
                    workspace_id=workspace_id
                ))

        return nodes, edges

canonical_graph_builder = CanonicalGraphBuilder()
