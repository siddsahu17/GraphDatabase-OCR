import os
from typing import Optional

class InputClassifier:
    """
    InputClassifier (§5.3 & §6.4).
    Routes input files to the appropriate engine.
    Routes PDFs and images to 'semi_structured' when templates exist.
    """
    def route(self, file_path: str, engine_hint: Optional[str] = None) -> str:
        if engine_hint:
            return engine_hint

        ext = os.path.splitext(file_path)[1].lower()
        if ext in [".pdf", ".jpg", ".jpeg", ".png", ".webp", ".tiff", ".bmp"]:
            return "semi_structured"

        return "semi_structured"

input_classifier = InputClassifier()
