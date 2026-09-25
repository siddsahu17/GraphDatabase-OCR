import logging
from typing import List, Dict, Any, Optional
from app.config import settings

logger = logging.getLogger(__name__)

class FalkorDBClient:
    def __init__(self):
        self._driver = None
        self._graph = None
        self._connected = False

    def connect(self) -> bool:
        """
        Connects to FalkorDB graph instance using falkordb driver.
        """
        try:
            from falkordb import FalkorDB
            
            # Connect via FalkorDB SDK
            kwargs = {
                "host": settings.FALKORDB_HOST,
                "port": settings.FALKORDB_PORT
            }
            if settings.FALKORDB_USERNAME:
                kwargs["username"] = settings.FALKORDB_USERNAME
            if settings.FALKORDB_PASSWORD:
                kwargs["password"] = settings.FALKORDB_PASSWORD

            self._driver = FalkorDB(**kwargs)
            self._graph = self._driver.select_graph(settings.FALKORDB_GRAPH_NAME)
            self._connected = True
            logger.info(f"Connected to FalkorDB graph '{settings.FALKORDB_GRAPH_NAME}' at {settings.FALKORDB_HOST}:{settings.FALKORDB_PORT}")
            return True
        except Exception as e:
            logger.warning(f"FalkorDB connection warning: {e}. Graph operations will run in mock/preview mode if database is offline.")
            self._connected = False
            return False

    @property
    def is_connected(self) -> bool:
        return self._connected

    def query(self, cypher_query: str, params: Optional[Dict[str, Any]] = None) -> Any:
        """
        Executes Cypher query on FalkorDB.
        """
        if not self._connected or self._graph is None:
            if not self.connect():
                logger.info(f"[Mock Cypher Executed]: {cypher_query} | params: {params}")
                return {"status": "mock_executed", "query": cypher_query, "result": []}

        try:
            result = self._graph.query(cypher_query, params or {})
            return result
        except Exception as e:
            logger.error(f"FalkorDB query error: {e} | Query: {cypher_query}")
            raise e

    def get_all_nodes_and_edges(self) -> Dict[str, Any]:
        """
        Fetches all nodes and relationships for visual representation in frontend.
        """
        if not self._connected or self._graph is None:
            self.connect()

        if not self._connected or self._graph is None:
            # Return sample graph data for frontend demo if FalkorDB service is not currently running
            return {
                "nodes": [
                    {"id": "Vendor:Acme Corp", "label": "Vendor", "properties": {"name": "Acme Corp", "phone": "555-0199"}},
                    {"id": "Invoice:INV-1001", "label": "Invoice", "properties": {"invoice_number": "INV-1001", "total_amount": "250.00"}},
                    {"id": "Customer:John Smith", "label": "Customer", "properties": {"name": "John Smith"}}
                ],
                "edges": [
                    {"from": "Vendor:Acme Corp", "to": "Invoice:INV-1001", "label": "ISSUED"},
                    {"from": "Invoice:INV-1001", "to": "Customer:John Smith", "label": "BILLED_TO"}
                ],
                "database_connected": False
            }

        try:
            # Fetch nodes
            nodes_query = "MATCH (n) RETURN id(n) AS node_id, labels(n)[0] AS label, properties(n) AS props LIMIT 200"
            nodes_result = self._graph.query(nodes_query)
            
            nodes = []
            for row in nodes_result.result_set:
                node_id, label, props = row[0], row[1], row[2]
                custom_id = f"{label}:{props.get('id', props.get('name', props.get('invoice_number', props.get('bill_id', node_id))))}"
                nodes.append({
                    "id": custom_id,
                    "label": label or "Node",
                    "properties": props or {}
                })

            # Fetch edges
            edges_query = "MATCH (a)-[r]->(b) RETURN labels(a)[0] AS a_label, properties(a) AS a_props, type(r) AS rel_type, labels(b)[0] AS b_label, properties(b) AS b_props LIMIT 200"
            edges_result = self._graph.query(edges_query)
            
            edges = []
            for row in edges_result.result_set:
                a_label, a_props, rel_type, b_label, b_props = row[0], row[1], row[2], row[3], row[4]
                source_id = f"{a_label}:{a_props.get('id', a_props.get('name', a_props.get('invoice_number', a_props.get('bill_id', ''))))}"
                target_id = f"{b_label}:{b_props.get('id', b_props.get('name', b_props.get('invoice_number', b_props.get('bill_id', ''))))}"
                edges.append({
                    "from": source_id,
                    "to": target_id,
                    "label": rel_type
                })

            return {
                "nodes": nodes,
                "edges": edges,
                "database_connected": True
            }
        except Exception as e:
            logger.error(f"Failed to fetch graph data: {e}")
            return {"nodes": [], "edges": [], "error": str(e), "database_connected": True}

falkor_client = FalkorDBClient()
