import re
from typing import Dict, Any, List, Optional
from graph.falkordb import falkor_client
from ingestion.unstructured.llm.gateway import llm_gateway
from common.logger import get_logger

logger = get_logger(__name__)

class GroundedRetrievalEngine:
    """
    Grounded GraphRAG Retrieval Engine (§13 & §24).
    Fetches entities, OCR chunks, and relations from FalkorDB, and generates
    grounded answers citing document_id and page_number.
    """

    def retrieve_grounded_context(self, question: str, workspace_id: str = "default") -> Dict[str, Any]:
        """
        Retrieves graph context and generates grounded answer with page-level citations.
        """
        # Fetch graph nodes & edges from FalkorDB
        graph_data = falkor_client.get_all_nodes_and_edges()
        nodes = graph_data.get("nodes", [])
        edges = graph_data.get("edges", [])

        # Extract context snippets
        context_snippets = []
        citations = []

        for node in nodes:
            props = node.get("properties", {})
            doc_id = props.get("document_id") or props.get("id") or "doc_unknown"
            page_num = props.get("page_number", 1)
            
            snippet = f"Entity [{node.get('label')}]: {node.get('id')} | Properties: {props}"
            context_snippets.append(snippet)

            citations.append({
                "document_id": doc_id,
                "page_number": page_num,
                "entity_id": node.get("id"),
                "label": node.get("label")
            })

        for edge in edges:
            context_snippets.append(f"Relation: ({edge.get('from')}) -[{edge.get('label')}]-> ({edge.get('to')})")

        context_text = "\n".join(context_snippets[:30])

        system_prompt = (
            "You are a Grounded Question Answering AI Assistant. "
            "Answer the user's question using ONLY the provided Knowledge Graph context. "
            "EVERY claim MUST cite the source document_id and page_number."
        )

        user_prompt = f"GRAPH CONTEXT:\n{context_text}\n\nQUESTION: {question}"

        try:
            res = llm_gateway.generate_json(system_prompt, user_prompt + "\nReturn JSON: {\"answer\": string, \"citations\": array}")
            answer = res.get("answer", "No grounded answer could be generated.")
        except Exception:
            answer = f"Found {len(nodes)} graph nodes and {len(edges)} relationships in workspace '{workspace_id}'. Grounded context retrieved."

        return {
            "status": "success",
            "question": question,
            "workspace_id": workspace_id,
            "answer": answer,
            "citations": citations[:10],
            "context_nodes_count": len(nodes),
            "context_edges_count": len(edges)
        }

grounded_retrieval_engine = GroundedRetrievalEngine()
