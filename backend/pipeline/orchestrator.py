from typing import List, Optional
from models.domain import PipelineContext
from pipeline.dispatcher import input_classifier
from pipeline.registry import engine_registry
from pipeline.stages.base import PipelineStage
from pipeline.stages.canonical_stages import (
    IngestionStage,
    KnowledgeObjectStage,
    ReviewStage,
    EntityResolutionStage,
    KnowledgeAlignmentStage,
    GraphBuilderStage,
    PersistenceStage,
    ValidationStage,
    IndexingStage,
    RetrievalReadyStage,
)
from common.logger import get_logger

logger = get_logger(__name__)

DEFAULT_STAGES: List[PipelineStage] = [
    IngestionStage(),
    KnowledgeObjectStage(),
    ReviewStage(),
    EntityResolutionStage(),
    KnowledgeAlignmentStage(),
    GraphBuilderStage(),
    PersistenceStage(),
    ValidationStage(),
    IndexingStage(),
    RetrievalReadyStage(),
]

class PipelineOrchestrator:
    """
    PipelineOrchestrator (§5.3 & Ground Rule 3).
    Single canonical execution path for all ingestion graph writes through DEFAULT_STAGES.
    """
    def __init__(self, stages: Optional[List[PipelineStage]] = None):
        self.stages = stages or DEFAULT_STAGES

    def process_document(
        self,
        file_path: str,
        domain: Optional[str] = None,
        workspace_id: str = "default",
        engine_hint: Optional[str] = None
    ) -> PipelineContext:

        engine_name = input_classifier.route(file_path, engine_hint)
        engine = engine_registry.get(engine_name)

        if not engine:
            raise ValueError(f"No registered engine found for name '{engine_name}'")

        logger.info(f"PipelineOrchestrator starting run for '{file_path}' via engine '{engine_name}'")
        
        # 1. Run engine parse & extraction
        ctx = engine.run(file_path, explicit_domain=domain, workspace_id=workspace_id)

        # 2. Run canonical DEFAULT_STAGES
        for stage in self.stages:
            logger.info(f"Executing stage: {stage.name}")
            ctx = stage.execute(ctx)

        return ctx

pipeline_orchestrator = PipelineOrchestrator()
