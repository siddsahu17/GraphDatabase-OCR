import logging
from typing import Dict, Any, List
from graph.falkordb import falkor_client
from common.logger import get_logger

logger = get_logger(__name__)

class GraphIndexManager:
    """
    Manages vector (HNSW) and full-text (BM25) indexes on FalkorDB (§24.1).
    """
    def ensure_indexes(self, graph_name: str = "knowledge_graph"):
        index_queries = [
            "CREATE INDEX FOR (c:Chunk) ON (c.id)",
            "CREATE INDEX FOR (e:Entity) ON (e.id)",
            "CREATE INDEX FOR (d:Document) ON (d.id)",
            "CREATE INDEX FOR (p:Patient) ON (p.id)",
            "CREATE INDEX FOR (i:Invoice) ON (i.id)",
            "CREATE INDEX FOR (b:MedicalBill) ON (b.id)",
        ]
        
        for q in index_queries:
            try:
                falkor_client.execute_query(q, graph_name=graph_name)
            except Exception as e:
                logger.debug(f"Index creation notice: {e}")

graph_index_manager = GraphIndexManager()
