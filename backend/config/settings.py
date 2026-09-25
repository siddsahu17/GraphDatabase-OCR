import os
from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict

# Disable HuggingFace symlinks warning on Windows
os.environ["HF_HUB_DISABLE_SYMLINKS_WARNING"] = "1"
os.environ["HF_HUB_DISABLE_SYMLINKS"] = "1"

class Settings(BaseSettings):
    # App Settings
    APP_NAME: str = "BodhiECG"
    APP_ENV: str = "development"
    LOG_LEVEL: str = "INFO"
    
    # Storage & Data Paths
    DATA_DIR: str = "data"
    
    # OCR Pipeline Settings (§6A.5)
    SEMI_PDF_FAST_MIN_CHARS: int = 50
    OCR_UPSCALE: float = 1.5
    OCR_FALLBACK: bool = True
    OCR_CONFIDENCE_THRESHOLD: float = 60.0
    TESSERACT_CMD: str = ""
    AUTO_APPROVE_THRESHOLD: float = 0.8
    
    # LLM Gateway Settings
    OPENAI_API_KEY: str = "your_openai_api_key_here"
    OPENAI_MODEL: str = "gpt-4o-mini"
    LLM_GATEWAY_EMBED_MODEL: str = "text-embedding-3-small"
    EMBED_DIM: int = 1536
    EMBED_ON_INGEST: bool = True

    # FalkorDB Database Settings
    FALKORDB_HOST: str = "localhost"
    FALKORDB_PORT: int = 6379
    FALKORDB_USERNAME: str = ""
    FALKORDB_PASSWORD: str = ""
    FALKORDB_GRAPH_NAME: str = "knowledge_graph"
    FALKORDB_URL: str = "redis://localhost:6379"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

@lru_cache()
def get_settings() -> Settings:
    """Returns cached singleton Settings instance."""
    return Settings()
