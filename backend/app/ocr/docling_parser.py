import os
import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)

class DocumentParser:
    def __init__(self):
        self._docling_converter = None
        self._initialized = False

    def _get_docling(self):
        if not self._initialized:
            try:
                from docling.document_converter import DocumentConverter
                self._docling_converter = DocumentConverter()
                logger.info("Docling DocumentConverter lazy-loaded successfully.")
            except Exception as e:
                logger.warning(f"Docling initialization notice: {e}. Fallback parser will be used if needed.")
            finally:
                self._initialized = True
        return self._docling_converter

    def parse_document(self, file_path: str) -> Dict[str, Any]:
        """
        Parses an image or document using Docling + Tesseract fallback.
        Returns a dict containing extracted raw_text, markdown_text, and parser metadata.
        """
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File not found: {file_path}")

        converter = self._get_docling()

        # Primary: Docling Parser
        if converter is not None:
            try:
                result = converter.convert(file_path)
                doc = result.document
                markdown_output = doc.export_to_markdown() if hasattr(doc, "export_to_markdown") else str(doc)
                raw_output = doc.export_to_text() if hasattr(doc, "export_to_text") else markdown_output
                
                if raw_output and raw_output.strip():
                    return {
                        "status": "success",
                        "parser": "docling",
                        "markdown": markdown_output,
                        "raw_text": raw_output
                    }
            except Exception as e:
                logger.warning(f"Docling conversion notice for {file_path}: {e}")

        # Fallback 1: Tesseract OCR
        try:
            import pytesseract
            from PIL import Image
            img = Image.open(file_path)
            tess_text = pytesseract.image_to_string(img) or ""
            if tess_text.strip():
                return {
                    "status": "success",
                    "parser": "tesseract_fallback",
                    "markdown": tess_text,
                    "raw_text": tess_text
                }
        except Exception as e:
            logger.debug(f"Tesseract fallback notice: {e}")

        # Fallback 2: Basic filename info
        base_name = os.path.basename(file_path)
        return {
            "status": "warning",
            "parser": "filename_fallback",
            "markdown": f"Document File: {base_name}",
            "raw_text": f"Document File: {base_name}"
        }

doc_parser = DocumentParser()
