from pipeline.stages.base import PipelineStage
from models.domain import PipelineContext
from config.settings import get_settings
from common.logger import get_logger
from graph_builder.canonical import canonical_graph_builder
from graph.falkordb import falkor_client
from pipeline.alignment.knowledge_alignment import knowledge_alignment_stage

logger = get_logger(__name__)

class IngestionStage(PipelineStage):
    @property
    def name(self) -> str:
        return "IngestionStage"

    def execute(self, ctx: PipelineContext) -> PipelineContext:
        logger.info(f"[{self.name}] Ingesting document '{ctx.document_id}'")
        return ctx

class KnowledgeObjectStage(PipelineStage):
    @property
    def name(self) -> str:
        return "KnowledgeObjectStage"

    def execute(self, ctx: PipelineContext) -> PipelineContext:
        logger.info(f"[{self.name}] Built {len(ctx.knowledge_objects)} KOs for '{ctx.document_id}'")
        return ctx

class ReviewStage(PipelineStage):
    @property
    def name(self) -> str:
        return "ReviewStage"

    def execute(self, ctx: PipelineContext) -> PipelineContext:
        settings = get_settings()
        for ko in ctx.knowledge_objects:
            if ko.confidence.overall >= settings.AUTO_APPROVE_THRESHOLD:
                ko.validation_status = "approved"
            else:
                ko.validation_status = "needs_review"
                ctx.status = "needs_review"
                ctx.add_warning(f"KO '{ko.canonical_id}' marked for review (confidence {ko.confidence.overall:.2f} < {settings.AUTO_APPROVE_THRESHOLD})")
        return ctx

class EntityResolutionStage(PipelineStage):
    @property
    def name(self) -> str:
        return "EntityResolutionStage"

    def execute(self, ctx: PipelineContext) -> PipelineContext:
        # Passthrough for template deterministic identities
        return ctx

class KnowledgeAlignmentStage(PipelineStage):
    @property
    def name(self) -> str:
        return "KnowledgeAlignmentStage"

    def execute(self, ctx: PipelineContext) -> PipelineContext:
        if ctx.template_name is None or ctx.template_name == "generic":
            aligned, _ = knowledge_alignment_stage.align_knowledge_objects(ctx.knowledge_objects, [], ctx.workspace_id)
            ctx.knowledge_objects = aligned
        return ctx

class GraphBuilderStage(PipelineStage):
    @property
    def name(self) -> str:
        return "GraphBuilderStage"

    def execute(self, ctx: PipelineContext) -> PipelineContext:
        if ctx.ocr_result:
            nodes, edges = canonical_graph_builder.build_graph(ctx.knowledge_objects, ctx.ocr_result, ctx.workspace_id)
            ctx.graph_nodes = nodes
            ctx.graph_edges = edges
            logger.info(f"[{self.name}] Built {len(nodes)} GraphNodes & {len(edges)} GraphEdges")
        return ctx

class PersistenceStage(PipelineStage):
    @property
    def name(self) -> str:
        return "PersistenceStage"

    def execute(self, ctx: PipelineContext) -> PipelineContext:
        if ctx.graph_nodes or ctx.graph_edges:
            target_graph = falkor_client.resolve_graph_name(ctx.domain)
            res = falkor_client.merge_nodes_and_edges(ctx.graph_nodes, ctx.graph_edges, graph_name=target_graph)
            logger.info(f"[{self.name}] Ingested {res.get('nodes_merged')} nodes and {res.get('edges_merged')} edges into FalkorDB graph '{target_graph}'")
        return ctx

class ValidationStage(PipelineStage):
    @property
    def name(self) -> str:
        return "ValidationStage"

    def execute(self, ctx: PipelineContext) -> PipelineContext:
        return ctx

class IndexingStage(PipelineStage):
    @property
    def name(self) -> str:
        return "IndexingStage"

    def execute(self, ctx: PipelineContext) -> PipelineContext:
        # Embeddings & substrate indexing
        try:
            from ingestion.unstructured.graph.retrieval_substrate import ensure_retrieval_substrate
            ensure_retrieval_substrate(ctx.workspace_id)
        except Exception as e:
            logger.warning(f"IndexingStage substrate notice: {e}")
        return ctx

class RetrievalReadyStage(PipelineStage):
    @property
    def name(self) -> str:
        return "RetrievalReadyStage"

    def execute(self, ctx: PipelineContext) -> PipelineContext:
        if ctx.status != "needs_review":
            ctx.status = "ingested"
        logger.info(f"[{self.name}] Pipeline execution ready for document '{ctx.document_id}' | Status: {ctx.status}")
        return ctx
