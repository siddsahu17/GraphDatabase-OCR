from abc import ABC, abstractmethod
from models.domain import PipelineContext

class PipelineStage(ABC):
    @property
    @abstractmethod
    def name(self) -> str:
        pass

    @abstractmethod
    def execute(self, ctx: PipelineContext) -> PipelineContext:
        pass
