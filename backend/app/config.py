import os
from dotenv import load_dotenv

# Disable HuggingFace symlinks requirement on Windows
os.environ["HF_HUB_DISABLE_SYMLINKS_WARNING"] = "1"
os.environ["HF_HUB_DISABLE_SYMLINKS"] = "1"

# Load environment variables from .env
load_dotenv()

class Settings:
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
    OPENAI_MODEL: str = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    
    FALKORDB_HOST: str = os.getenv("FALKORDB_HOST", "localhost")
    FALKORDB_PORT: int = int(os.getenv("FALKORDB_PORT", "6379"))
    FALKORDB_USERNAME: str = os.getenv("FALKORDB_USERNAME", "")
    FALKORDB_PASSWORD: str = os.getenv("FALKORDB_PASSWORD", "")
    FALKORDB_GRAPH_NAME: str = os.getenv("FALKORDB_GRAPH_NAME", "knowledge_graph")
    FALKORDB_URL: str = os.getenv("FALKORDB_URL", "redis://localhost:6379")

settings = Settings()
