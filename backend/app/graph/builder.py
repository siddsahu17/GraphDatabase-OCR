import logging
from typing import Dict, Any, List, Tuple, Optional
from graph.falkordb import falkor_client
from models.domain import GraphNode, GraphEdge

logger = logging.getLogger(__name__)

class CypherBuilder:
    @staticmethod
    def sanitize_label(label: str) -> str:
        return "".join(c for c in label if c.isalnum() or c == '_')

    @staticmethod
    def sanitize_property_key(key: str) -> str:
        return "".join(c for c in key if c.isalnum() or c == '_')

    def build_node_merge_query(self, node: Dict[str, Any]) -> Tuple[str, Dict[str, Any]]:
        label = self.sanitize_label(node.get("label", "Entity"))
        node_id = str(node.get("id", "default_id"))
        properties = node.get("properties", {})
        properties["id"] = node_id

        params = {}
        set_clauses = []
        for k, v in properties.items():
            clean_k = self.sanitize_property_key(k)
            param_name = f"prop_{clean_k}"
            params[param_name] = str(v) if v is not None else ""
            set_clauses.append(f"n.{clean_k} = ${param_name}")

        set_str = ", ".join(set_clauses)
        params["primary_id"] = node_id

        cypher = f"MERGE (n:{label} {{id: $primary_id}}) ON CREATE SET {set_str} ON MATCH SET {set_str} RETURN n"
        return cypher, params

    def build_relationship_merge_query(self, rel: Dict[str, Any]) -> Tuple[str, Dict[str, Any]]:
        from_label = self.sanitize_label(rel.get("from_label", "Entity"))
        from_id = str(rel.get("from_id", ""))
        rel_type = self.sanitize_label(rel.get("type", "RELATED_TO")).upper()
        to_label = self.sanitize_label(rel.get("to_label", "Entity"))
        to_id = str(rel.get("to_id", ""))

        params = {
            "from_id": from_id,
            "to_id": to_id
        }

        cypher = (
            f"MATCH (a:{from_label} {{id: $from_id}}), (b:{to_label} {{id: $to_id}}) "
            f"MERGE (a)-[r:{rel_type}]->(b) "
            f"RETURN r"
        )
        return cypher, params

    def ingest_graph_data(self, graph_data: Dict[str, Any], domain: Optional[str] = None) -> Dict[str, Any]:
        nodes = graph_data.get("nodes", [])
        relationships = graph_data.get("relationships", [])
        target_domain = domain or graph_data.get("domain")

        g_nodes = [
            GraphNode(
                id=str(n.get("id")),
                label=str(n.get("label", "Entity")),
                properties=n.get("properties", {})
            )
            for n in nodes
        ]
        g_edges = [
            GraphEdge(
                from_id=str(r.get("from_id")),
                from_label=str(r.get("from_label", "Entity")),
                type=str(r.get("type", "RELATED_TO")),
                to_id=str(r.get("to_id")),
                to_label=str(r.get("to_label", "Entity"))
            )
            for r in relationships
        ]

        res = falkor_client.merge_nodes_and_edges(g_nodes, g_edges, graph_name=target_domain)
        return {
            "status": "success",
            "graph_name": res.get("graph_name"),
            "nodes_ingested": res.get("nodes_merged"),
            "relationships_ingested": res.get("edges_merged"),
            "total_queries": len(g_nodes) + len(g_edges)
        }

cypher_builder = CypherBuilder()
