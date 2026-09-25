import logging
from typing import Dict, Any, List, Tuple
from app.graph.falkor_client import falkor_client

logger = logging.getLogger(__name__)

class CypherBuilder:
    @staticmethod
    def sanitize_label(label: str) -> str:
        return "".join(c for c in label if c.isalnum() or c == '_')

    @staticmethod
    def sanitize_property_key(key: str) -> str:
        return "".join(c for c in key if c.isalnum() or c == '_')

    def build_node_merge_query(self, node: Dict[str, Any]) -> Tuple[str, Dict[str, Any]]:
        """
        Builds Cypher MERGE query for a single node.
        """
        label = self.sanitize_label(node.get("label", "Entity"))
        node_id = str(node.get("id", "default_id"))
        properties = node.get("properties", {})
        
        # Ensure 'id' is in properties for primary lookup
        properties["id"] = node_id

        # Escape parameter keys
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
        """
        Builds Cypher MERGE query for a relationship between two nodes.
        """
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

    def ingest_graph_data(self, graph_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Ingests all nodes and relationships into FalkorDB graph.
        Returns execution statistics.
        """
        nodes = graph_data.get("nodes", [])
        relationships = graph_data.get("relationships", [])

        nodes_created = 0
        rels_created = 0
        queries_executed = []

        # 1. Ingest Nodes
        for node in nodes:
            try:
                cypher, params = self.build_node_merge_query(node)
                queries_executed.append(cypher)
                falkor_client.query(cypher, params)
                nodes_created += 1
            except Exception as e:
                logger.error(f"Error ingesting node {node}: {e}")

        # 2. Ingest Relationships
        for rel in relationships:
            try:
                cypher, params = self.build_relationship_merge_query(rel)
                queries_executed.append(cypher)
                falkor_client.query(cypher, params)
                rels_created += 1
            except Exception as e:
                logger.error(f"Error ingesting relationship {rel}: {e}")

        return {
            "status": "success",
            "nodes_ingested": nodes_created,
            "relationships_ingested": rels_created,
            "total_queries": len(queries_executed),
            "sample_queries": queries_executed[:5]
        }

cypher_builder = CypherBuilder()
