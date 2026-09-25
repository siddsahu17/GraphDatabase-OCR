from typing import Dict, Any
from ingestion.unstructured.graph.indexes import graph_index_manager
from common.logger import get_logger

logger = get_logger(__name__)

def ensure_retrieval_substrate(workspace_id: str = "default"):
    """
    Ensures vector and full-text indexes exist for the workspace (§24.1 & §24.2).
    """
    try:
        graph_index_manager.ensure_indexes()
        logger.info(f"Retrieval substrate initialized for workspace '{workspace_id}'")
    except Exception as e:
        logger.warning(f"Could not initialize retrieval substrate: {e}")
