from typing import Dict, Any, Optional
from ingestion.unstructured.graph.context import grounded_retrieval_engine
from ingestion.unstructured.llm.gateway import llm_gateway
from graph.falkordb import falkor_client
from common.logger import get_logger

logger = get_logger(__name__)

class RetrievalService:
    """
    Service layer (§3.2 & §13 & §24) for grounded QA, vector/graph search, and NL2Cypher translation.
    Strictly isolated from HTTP routers.
    """

    def grounded_qa(self, question: str, workspace_id: str = "default") -> Dict[str, Any]:
        return grounded_retrieval_engine.retrieve_grounded_context(
            question=question,
            workspace_id=workspace_id
        )

    def nl2cypher(self, query: str, workspace_id: str = "default") -> Dict[str, Any]:
        system_prompt = (
            "You are a Cypher query generator for FalkorDB. "
            "Translate the user's natural language request into a valid Cypher READ query. "
            "Use labels: Patient, Invoice, MedicalBill, Document, Entity. "
            "Return JSON format: {\"cypher\": string, \"explanation\": string}"
        )
        try:
            res = llm_gateway.generate_json(system_prompt, f"Translate to Cypher: {query}")
            cypher_raw = res.get("cypher", "MATCH (n) RETURN n LIMIT 10")
            cypher_str = str(cypher_raw) if not isinstance(cypher_raw, (dict, list)) else "MATCH (n) RETURN n LIMIT 10"
            explanation = str(res.get("explanation", "Default fallback query"))
        except Exception:
            cypher_str = f"MATCH (n) WHERE n.name CONTAINS '{query}' OR n.id CONTAINS '{query}' RETURN n LIMIT 25"
            explanation = "Rule-based Cypher lookup"

        # Execute query on FalkorDB if available and convert response to JSON-serializable structure
        try:
            raw_res = falkor_client.execute_query(cypher_str)
            if isinstance(raw_res, (dict, str, list, int, float, bool)) or raw_res is None:
                exec_res = raw_res
            else:
                exec_res = {"status": "executed", "result": str(raw_res)}
        except Exception as e:
            exec_res = {"error": str(e)}

        return {
            "status": "success",
            "query": query,
            "generated_cypher": cypher_str,
            "explanation": explanation,
            "execution_result": exec_res
        }

    def execute_query(self, query: str, workspace_id: str = "default") -> Dict[str, Any]:
        return self.grounded_qa(question=query, workspace_id=workspace_id)

retrieval_service = RetrievalService()
