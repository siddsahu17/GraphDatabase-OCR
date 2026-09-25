from typing import Dict, Any, Optional
from pipeline.engines.semi_structured_engine import semi_structured_engine

class EngineRegistry:
    def __init__(self):
        self._engines: Dict[str, Any] = {
            "semi_structured": semi_structured_engine
        }

    def register(self, name: str, engine_instance: Any):
        self._engines[name] = engine_instance

    def get(self, name: str) -> Optional[Any]:
        return self._engines.get(name)

engine_registry = EngineRegistry()
