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
        Parses an image or document using Docling.
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
                
                return {
                    "status": "success",
                    "parser": "docling",
                    "markdown": markdown_output,
                    "raw_text": raw_output
                }
            except Exception as e:
                logger.error(f"Docling conversion failed for {file_path}: {e}")

        # Fallback 1: EasyOCR / RapidOCR
        try:
            import easyocr
            reader = easyocr.Reader(['en'], gpu=False)
            ocr_results = reader.readtext(file_path, detail=0)
            extracted_text = "\n".join(ocr_results)
            return {
                "status": "success",
                "parser": "easyocr_fallback",
                "markdown": extracted_text,
                "raw_text": extracted_text
            }
        except Exception as e:
            logger.warning(f"EasyOCR fallback failed: {e}")

        # Fallback 2: Basic image info placeholder
        return {
            "status": "warning",
            "parser": "basic_info",
            "markdown": f"Document: {os.path.basename(file_path)}",
            "raw_text": f"Document: {os.path.basename(file_path)}"
        }

doc_parser = DocumentParser()
