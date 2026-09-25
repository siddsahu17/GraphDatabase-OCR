from typing import List, Dict, Any, Optional, Tuple
from pydantic import BaseModel, Field, ConfigDict

class Confidence(BaseModel):
    overall: float = 1.0
    fields: Dict[str, float] = Field(default_factory=dict)

class OCRTextElement(BaseModel):
    text: str
    bbox: Optional[Tuple[float, float, float, float]] = None
    confidence: float = 1.0

class OCRPage(BaseModel):
    page_number: int
    text: str
    lines: List[OCRTextElement] = Field(default_factory=list)
    words: List[OCRTextElement] = Field(default_factory=list)
    mean_confidence: float = 1.0

class OCRResult(BaseModel):
    document_id: str
    source_path: str
    mime_type: str = "image/jpeg"
    page_count: int = 1
    pages: List[OCRPage] = Field(default_factory=list)
    full_text: str = ""
    normalized_text: str = ""
    engine_used: str = "pypdf"  # pypdf | docling | tesseract | easyocr
    engines_attempted: List[str] = Field(default_factory=list)
    fallback_reason: Optional[str] = None
    duration_ms: float = 0.0
    warnings: List[str] = Field(default_factory=list)

class SemanticObject(BaseModel):
    canonical_id: str
    entity: str
    entity_type: str
    properties: Dict[str, Any] = Field(default_factory=dict)
    relationships: List[Dict[str, Any]] = Field(default_factory=list)
    confidence: Confidence = Field(default_factory=Confidence)
    provenance: Dict[str, Any] = Field(default_factory=dict)
    ontology_mapping: Dict[str, Any] = Field(default_factory=dict)
    validation_status: str = "approved"  # approved | needs_review | rejected

class GraphNode(BaseModel):
    id: str
    label: str
    properties: Dict[str, Any] = Field(default_factory=dict)
    workspace_id: str = "default"

class GraphEdge(BaseModel):
    from_id: str
    from_label: str
    type: str
    to_id: str
    to_label: str
    properties: Dict[str, Any] = Field(default_factory=dict)
    workspace_id: str = "default"

class PipelineContext(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)
    
    document_id: str
    source_path: str
    workspace_id: str = "default"
    ocr_result: Optional[OCRResult] = None
    domain: Optional[str] = None
    template_name: Optional[str] = None
    extracted_fields: Dict[str, Any] = Field(default_factory=dict)
    knowledge_objects: List[SemanticObject] = Field(default_factory=list)
    graph_nodes: List[GraphNode] = Field(default_factory=list)
    graph_edges: List[GraphEdge] = Field(default_factory=list)
    status: str = "pending"  # pending | needs_review | ingested | failed
    warnings: List[str] = Field(default_factory=list)
    errors: List[str] = Field(default_factory=list)

    def add_warning(self, warning_msg: str):
        self.warnings.append(warning_msg)
