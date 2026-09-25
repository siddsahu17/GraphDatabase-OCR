import json
import logging
from typing import Dict, Any, List, Optional
from openai import OpenAI
from config.settings import get_settings
from common.logger import get_logger
from common.exceptions import ExtractionException

logger = get_logger(__name__)

class LLMGateway:
    """
    LLM Gateway (§12A) for managing OpenAI LLM completions and embeddings.
    Strictly isolated from vendor hardcoding.
    """
    def __init__(self):
        self._client: Optional[OpenAI] = None

    def _get_client(self) -> Optional[OpenAI]:
        if self._client is None:
            settings = get_settings()
            if settings.OPENAI_API_KEY and settings.OPENAI_API_KEY != "your_openai_api_key_here":
                try:
                    self._client = OpenAI(api_key=settings.OPENAI_API_KEY)
                    logger.info("LLMGateway OpenAI client initialized successfully.")
                except Exception as e:
                    logger.warning(f"LLMGateway initialization warning: {e}")
        return self._client

    def generate_json(self, system_prompt: str, user_prompt: str) -> Dict[str, Any]:
        """
        Generates structured JSON object completion from LLM.
        """
        client = self._get_client()
        settings = get_settings()

        if client is None:
            raise ExtractionException("LLMGateway OpenAI client is not configured with a valid API key.")

        try:
            response = client.chat.completions.create(
                model=settings.OPENAI_MODEL,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.1,
                response_format={"type": "json_object"}
            )
            content = response.choices[0].message.content
            return json.loads(content)
        except Exception as e:
            logger.error(f"LLMGateway completion error: {e}")
            raise ExtractionException(f"LLMGateway completion failed: {e}")

    def generate_embedding(self, text: str) -> List[float]:
        """
        Generates text embedding vector using gateway embedding model.
        """
        client = self._get_client()
        settings = get_settings()

        if client is None or not text.strip():
            # Return dummy zero vector of EMBED_DIM size if offline
            return [0.0] * settings.EMBED_DIM

        try:
            response = client.embeddings.create(
                model=settings.LLM_GATEWAY_EMBED_MODEL,
                input=text.replace("\n", " ")
            )
            return response.data[0].embedding
        except Exception as e:
            logger.warning(f"Embedding generation error: {e}")
            return [0.0] * settings.EMBED_DIM

llm_gateway = LLMGateway()
