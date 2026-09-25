import os
import glob
import json
import re
from typing import Dict, Any, List, Optional, Tuple
from common.logger import get_logger
from models.domain import OCRResult

logger = get_logger(__name__)

class TemplateManager:
    def __init__(self, templates_dir: str = "templates"):
        self.templates_dir = os.path.abspath(templates_dir)
        self._templates: Dict[str, Dict[str, Any]] = {}
        self.reload_templates()

    def reload_templates(self):
        self._templates.clear()
        if not os.path.exists(self.templates_dir):
            os.makedirs(self.templates_dir, exist_ok=True)
            return

        pattern = os.path.join(self.templates_dir, "*.json")
        for fpath in glob.glob(pattern):
            try:
                with open(fpath, "r", encoding="utf-8") as f:
                    tmpl = json.load(f)
                    domain = tmpl.get("domain")
                    if domain:
                        self._templates[domain] = tmpl
            except Exception as e:
                logger.error(f"Failed to load template file '{fpath}': {e}")
                
        logger.info(f"Loaded {len(self._templates)} templates from '{self.templates_dir}': {list(self._templates.keys())}")

    def get_template(self, domain: str) -> Optional[Dict[str, Any]]:
        return self._templates.get(domain)

    def list_templates(self) -> List[Dict[str, Any]]:
        return list(self._templates.values())

    def classify_document(self, ocr_result: OCRResult, explicit_domain: Optional[str] = None) -> Tuple[Optional[str], Optional[Dict[str, Any]], float]:
        """
        Classifies OCRResult against loaded template signatures.
        Returns tuple of (domain_name, template_dict, score).
        If explicit_domain is provided, skips signature matching.
        """
        if explicit_domain and explicit_domain in self._templates:
            return explicit_domain, self._templates[explicit_domain], 1.0

        text = ocr_result.normalized_text or ocr_result.full_text or ""
        best_domain = None
        best_tmpl = None
        best_score = 0.0

        for domain, tmpl in self._templates.items():
            sig = tmpl.get("signature", {})
            all_of = sig.get("all_of", [])
            any_of = sig.get("any_of", [])
            min_score = sig.get("min_score", 0.6)

            # Check required all_of signatures
            all_matched = True
            for pat in all_of:
                if not re.search(pat, text):
                    all_matched = False
                    break

            if not all_matched:
                continue

            # Base score for passing all_of
            score = 0.5
            if any_of:
                any_matches = sum(1 for pat in any_of if re.search(pat, text))
                score += (any_matches / len(any_of)) * 0.5
            else:
                score = 1.0

            if score >= min_score and score > best_score:
                best_score = score
                best_domain = domain
                best_tmpl = tmpl

        return best_domain, best_tmpl, best_score

template_manager = TemplateManager()
