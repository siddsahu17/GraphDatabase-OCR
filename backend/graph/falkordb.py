import logging
from typing import Dict, Any, List, Optional
from config.settings import get_settings
from common.logger import get_logger
from common.exceptions import GraphDatabaseError
from models.domain import GraphNode, GraphEdge

logger = get_logger(__name__)

class FalkorGraphClient:
    """
    FalkorDB Client (§11) for executing idempotent Cypher MERGE queries across domain-isolated graphs.
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

    def resolve_graph_name(self, domain_or_name: Optional[str] = None) -> str:
        """
        Maps domain string to domain-isolated graph name:
        - Invoice domain -> invoice_graph
        - Medical domain (medical_bill, discharge_summary, medical) -> medical_graph
        """
        if not domain_or_name or domain_or_name == "all":
            return get_settings().FALKORDB_GRAPH_NAME

        d = str(domain_or_name).lower().strip()
        if d in ("invoice", "invoice_graph", "invoices"):
            return "invoice_graph"
        elif d in ("medical_bill", "discharge_summary", "medical", "medical_graph", "medical_bills", "discharge_summaries"):
            return "medical_graph"
        return d

    def get_graph(self, graph_name: Optional[str] = None):
        driver = self._get_driver()
        target_name = self.resolve_graph_name(graph_name)
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
        """
        Retrieves nodes and edges with relationship properties for a specific graph
        ('invoice_graph' or 'medical_graph') or aggregated across all graphs.
        """
        if graph_name and graph_name != "all":
            target_graphs = [self.resolve_graph_name(graph_name)]
        else:
            target_graphs = ["invoice_graph", "medical_graph", get_settings().FALKORDB_GRAPH_NAME]

        nodes = []
        edges = []
        seen_nodes = set()

        for gname in target_graphs:
            graph = self.get_graph(gname)
            if graph:
                try:
                    res_nodes = graph.query("MATCH (n) RETURN n LIMIT 200")
                    for row in getattr(res_nodes, "result_set", []):
                        node_obj = row[0]
                        nid = getattr(node_obj, "properties", {}).get("id", str(getattr(node_obj, "id", "")))
                        if nid not in seen_nodes:
                            seen_nodes.add(nid)
                            nodes.append({
                                "id": nid,
                                "label": getattr(node_obj, "labels", ["Entity"])[0] if getattr(node_obj, "labels", None) else "Entity",
                                "properties": getattr(node_obj, "properties", {}),
                                "graph": gname
                            })

                    res_edges = graph.query("MATCH (a)-[r]->(b) RETURN a.id, type(r), b.id, properties(r) LIMIT 300")
                    for row in getattr(res_edges, "result_set", []):
                        edge_props = row[3] if len(row) > 3 and isinstance(row[3], dict) else {}
                        edges.append({
                            "from": row[0],
                            "label": row[1],
                            "to": row[2],
                            "properties": edge_props,
                            "graph": gname
                        })
                except Exception as e:
                    logger.debug(f"Query notice for graph '{gname}': {e}")

        return {"nodes": nodes, "edges": edges, "database_connected": self._connected}

    def merge_nodes_and_edges(
        self,
        nodes: List[GraphNode],
        edges: List[GraphEdge],
        graph_name: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Executes idempotent MERGE operations for nodes and edges into the target domain graph.
        Merges edge properties directly onto relationships.
        """
        target_graph = self.resolve_graph_name(graph_name)
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
            
            self.execute_query(cypher, param_dict, target_graph)
            nodes_created += 1

        # 2. Merge Edges with Relationship Properties
        for e in edges:
            param_dict = {
                "from_id": e.from_id,
                "to_id": e.to_id,
                "workspace_id": e.workspace_id
            }
            set_clauses = ["r.workspace_id = $workspace_id"]
            for k, v in e.properties.items():
                clean_k = "".join(c for c in k if c.isalnum() or c == '_')
                param_name = f"ep_{clean_k}"
                param_dict[param_name] = str(v) if v is not None else ""
                set_clauses.append(f"r.{clean_k} = ${param_name}")

            set_str = ", ".join(set_clauses)
            cypher = (
                f"MATCH (a {{id: $from_id}}), (b {{id: $to_id}}) "
                f"MERGE (a)-[r:{e.type}]->(b) "
                f"ON CREATE SET {set_str} ON MATCH SET {set_str} "
                f"RETURN r"
            )
            self.execute_query(cypher, param_dict, target_graph)
            edges_created += 1

        return {
            "status": "success",
            "graph_name": target_graph,
            "nodes_merged": nodes_created,
            "edges_merged": edges_created
        }

    def delete_graph(self, graph_name: Optional[str] = None) -> bool:
        target_name = self.resolve_graph_name(graph_name)
        graph = self.get_graph(target_name)
        if graph:
            try:
                graph.delete()
                logger.info(f"FalkorDB graph '{target_name}' deleted successfully.")
                return True
            except Exception as e:
                logger.warning(f"FalkorDB delete notice for '{target_name}': {e}")
                try:
                    graph.query("MATCH (n) DETACH DELETE n")
                    return True
                except Exception as inner_e:
                    logger.error(f"Failed to clear graph '{target_name}': {inner_e}")
                    return False
        return False

falkor_client = FalkorGraphClient()
