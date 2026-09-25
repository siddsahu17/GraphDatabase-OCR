import logging
from typing import Dict, Any, List, Optional
from config.settings import get_settings
from common.logger import get_logger
from common.exceptions import GraphDatabaseError
from models.domain import GraphNode, GraphEdge

logger = get_logger(__name__)

class FalkorGraphClient:
    """
    FalkorDB Client (§11) for executing idempotent Cypher MERGE queries.
    """
    def __init__(self):
        self._driver = None
        self._connected = False

    def _get_driver(self):
        if self._driver is None:
            settings = get_settings()
            try:
                from falkordb import FalkorDB
                kwargs = {"host": settings.FALKORDB_HOST, "port": settings.FALKORDB_PORT}
                if settings.FALKORDB_USERNAME:
                    kwargs["username"] = settings.FALKORDB_USERNAME
                if settings.FALKORDB_PASSWORD:
                    kwargs["password"] = settings.FALKORDB_PASSWORD
                self._driver = FalkorDB(**kwargs)
                self._connected = True
                logger.info(f"FalkorDB connected at {settings.FALKORDB_HOST}:{settings.FALKORDB_PORT}")
            except Exception as e:
                logger.warning(f"FalkorDB connection warning: {e}. Running in mock/fallback mode.")
                self._connected = False
        return self._driver

    def get_graph(self, graph_name: Optional[str] = None):
        driver = self._get_driver()
        settings = get_settings()
        target_name = graph_name or settings.FALKORDB_GRAPH_NAME
        if driver and self._connected:
            return driver.select_graph(target_name)
        return None

    def execute_query(
        self,
        query: str,
        params: Optional[Dict[str, Any]] = None,
        graph_name: Optional[str] = None,
        ignore_errors: bool = False
    ) -> Any:
        graph = self.get_graph(graph_name)
        params = params or {}
        if graph:
            try:
                return graph.query(query, params)
            except Exception as e:
                if ignore_errors or "already indexed" in str(e).lower():
                    logger.debug(f"FalkorDB query notice: {e} | Query: {query}")
                    return None
                logger.error(f"FalkorDB query error: {e} | Query: {query}")
                raise GraphDatabaseError(f"Cypher execution failed: {e}")
        else:
            logger.info(f"[Mock Cypher]: {query} | params: {params}")
            return {"status": "mock", "query": query, "params": params}

    def get_all_nodes_and_edges(self, graph_name: Optional[str] = None) -> Dict[str, Any]:
        graph = self.get_graph(graph_name)
        nodes = []
        edges = []
        if graph:
            try:
                res_nodes = graph.query("MATCH (n) RETURN n LIMIT 100")
                for row in getattr(res_nodes, "result_set", []):
                    node_obj = row[0]
                    nodes.append({
                        "id": getattr(node_obj, "properties", {}).get("id", str(getattr(node_obj, "id", ""))),
                        "label": getattr(node_obj, "labels", ["Entity"])[0] if getattr(node_obj, "labels", None) else "Entity",
                        "properties": getattr(node_obj, "properties", {})
                    })

                res_edges = graph.query("MATCH (a)-[r]->(b) RETURN a.id, type(r), b.id LIMIT 100")
                for row in getattr(res_edges, "result_set", []):
                    edges.append({
                        "from": row[0],
                        "label": row[1],
                        "to": row[2]
                    })
            except Exception as e:
                logger.warning(f"Error querying FalkorDB nodes and edges: {e}")
        return {"nodes": nodes, "edges": edges}

    def merge_nodes_and_edges(self, nodes: List[GraphNode], edges: List[GraphEdge], graph_name: Optional[str] = None) -> Dict[str, Any]:
        """
        Executes idempotent MERGE operations for nodes and edges.
        """
        nodes_created = 0
        edges_created = 0

        # 1. Merge Nodes
        for n in nodes:
            param_dict = {}
            set_clauses = []
            for k, v in n.properties.items():
                clean_k = "".join(c for c in k if c.isalnum() or c == '_')
                param_name = f"p_{clean_k}"
                param_dict[param_name] = str(v) if v is not None else ""
                set_clauses.append(f"n.{clean_k} = ${param_name}")

            param_dict["node_id"] = n.id
            param_dict["workspace_id"] = n.workspace_id
            set_clauses.append("n.workspace_id = $workspace_id")

            set_str = ", ".join(set_clauses)
            cypher = f"MERGE (n:{n.label} {{id: $node_id}}) ON CREATE SET {set_str} ON MATCH SET {set_str} RETURN n"
            
            self.execute_query(cypher, param_dict, graph_name)
            nodes_created += 1

        # 2. Merge Edges
        for e in edges:
            param_dict = {
                "from_id": e.from_id,
                "to_id": e.to_id,
                "workspace_id": e.workspace_id
            }
            cypher = (
                f"MATCH (a:{e.from_label} {{id: $from_id}}), (b:{e.to_label} {{id: $to_id}}) "
                f"MERGE (a)-[r:{e.type}]->(b) "
                f"ON CREATE SET r.workspace_id = $workspace_id "
                f"RETURN r"
            )
            self.execute_query(cypher, param_dict, graph_name)
            edges_created += 1

        return {
            "status": "success",
            "nodes_merged": nodes_created,
            "edges_merged": edges_created
        }

falkor_client = FalkorGraphClient()
