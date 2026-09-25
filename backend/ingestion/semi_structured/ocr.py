import os
import re
import math
import time
import hashlib
import mimetypes
from typing import List, Dict, Any, Tuple, Optional
import numpy as np
from PIL import Image
import cv2

from config.settings import get_settings
from common.logger import get_logger
from common.exceptions import OCRError
from models.domain import OCRResult, OCRPage, OCRTextElement

logger = get_logger(__name__)

# --- IMAGE PREPROCESSING (§6A.5) ---

def preprocess_image(image_input: Any) -> np.ndarray:
    """
    Preprocesses input image for optimal Tesseract/OCR recognition:
    Upscale -> Grayscale -> Denoise -> Adaptive Threshold -> Deskew.
    Can be tested independently.
    """
    settings = get_settings()

    if isinstance(image_input, Image.Image):
        img_np = np.array(image_input)
        if len(img_np.shape) == 3 and img_np.shape[2] == 3:
            img = cv2.cvtColor(img_np, cv2.COLOR_RGB2BGR)
        else:
            img = img_np
    else:
        img = image_input

    if img is None or img.size == 0:
        raise ValueError("Invalid image input for preprocessing")

    # 1. Upscale if configured
    if settings.OCR_UPSCALE > 1.0:
        h, w = img.shape[:2]
        new_w = int(w * settings.OCR_UPSCALE)
        new_h = int(h * settings.OCR_UPSCALE)
        img = cv2.resize(img, (new_w, new_h), interpolation=cv2.INTER_CUBIC)

    # 2. Convert to Grayscale
    if len(img.shape) == 3:
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    else:
        gray = img

    # 3. Denoise with Gaussian Blur
    blurred = cv2.GaussianBlur(gray, (3, 3), 0)

    # 4. Adaptive Thresholding (Otsu)
    _, thresh = cv2.threshold(blurred, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

    # 5. Deskew / Angle Correction
    try:
        coords = np.column_stack(np.where(thresh == 0))
        if len(coords) > 0:
            angle = cv2.minAreaRect(coords)[-1]
            if angle < -45:
                angle = -(90 + angle)
            else:
                angle = -angle
            if abs(angle) > 0.5 and abs(angle) < 45:
                (h, w) = thresh.shape[:2]
                center = (w // 2, h // 2)
                M = cv2.getRotationMatrix2D(center, angle, 1.0)
                thresh = cv2.warpAffine(thresh, M, (w, h), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE)
    except Exception as e:
        logger.debug(f"Deskew skipped: {e}")

    return thresh


# --- TEXT NORMALIZATION HELPER (§6A.5) ---

def normalize_ocr_text(raw_text: str) -> str:
    """
    Normalizes common OCR artifacts:
    - Fixes O/0 and l/1/I errors in numeric and ID code contexts.
    - Joins hyphenated line breaks.
    - Formats currency and date tokens consistently.
    """
    if not raw_text:
        return ""

    text = raw_text

    # 1. Join hyphenated line breaks (e.g., "invo-\n-ice" -> "invoice")
    text = re.sub(r'(\w+)-\s*\n\s*(\w+)', r'\1\2', text)

    # Helper function to fix numeric / ID tokens
    def fix_numeric_token(match):
        prefix = match.group(1) or ""
        token = match.group(2)
        token = re.sub(r'(?<=\d)[Oo]|[Oo](?=\d)', '0', token)
        token = re.sub(r'^[Oo](?=\d)', '0', token)
        token = re.sub(r'(?<=\d)[lI]|[lI](?=\d)', '1', token)
        token = re.sub(r'^[lI](?=\d)', '1', token)
        return f"{prefix}{token}"

    # 2. Fix O/0 and l/1 inside numeric and code tokens
    text = re.sub(r'([A-Za-z]+[\-\:\#]?)?([OoIl\d][OoIl\d\.\,\-]+)', fix_numeric_token, text)

    # 3. Currency symbol normalization spacing ($ 250.00 -> $250.00)
    text = re.sub(r'([\$\u20b9\u20ac])\s+(\d)', r'\1\2', text)

    # 4. Collapse extra whitespace while preserving line structure
    lines = [re.sub(r'[ \t]+', ' ', line.strip()) for line in text.split('\n')]
    return '\n'.join(lines)


# --- OCR CASCADE ENGINE (§6A.5) ---

class OCREngineCascade:
    def __init__(self):
        self._docling_converter = None
        self._easyocr_reader = None

    def _get_docling(self):
        if self._docling_converter is None:
            try:
                from docling.document_converter import DocumentConverter
                self._docling_converter = DocumentConverter()
                logger.info("Docling converter loaded lazily for OCR cascade.")
            except Exception as e:
                logger.warning(f"Docling lazy import warning: {e}")
        return self._docling_converter

    def _get_easyocr(self):
        if self._easyocr_reader is None:
            try:
                import easyocr
                self._easyocr_reader = easyocr.Reader(['en'], gpu=False)
                logger.info("EasyOCR reader loaded lazily for fallback OCR.")
            except Exception as e:
                logger.warning(f"EasyOCR lazy import warning: {e}")
        return self._easyocr_reader

    def compute_file_hash(self, file_path: str) -> str:
        """Computes a stable SHA-256 hash of file bytes as document_id."""
        hasher = hashlib.sha256()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(65536), b""):
                hasher.update(chunk)
        return hasher.hexdigest()

    def process(self, file_path: str) -> OCRResult:
        """
        Runs full OCR Cascade:
        Text File Direct Reader -> PDF Fast Path (pypdf) -> Docling -> Tesseract + Preprocessing -> EasyOCR Fallback.
        """
        if not os.path.exists(file_path):
            raise OCRError(f"File not found: {file_path}")

        start_time = time.time()
        settings = get_settings()
        doc_id = self.compute_file_hash(file_path)
        mime_type, _ = mimetypes.guess_type(file_path)
        mime_type = mime_type or "application/octet-stream"

        engines_attempted = []
        warnings = []

        # BRANCH 0: DIRECT TEXT READ FOR PLAIN TEXT / MD / CSV FILES
        if file_path.lower().endswith((".txt", ".md", ".csv", ".json")):
            engines_attempted.append("text_reader")
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                raw_txt = f.read()
            duration = (time.time() - start_time) * 1000.0
            return OCRResult(
                document_id=doc_id,
                source_path=file_path,
                mime_type="text/plain",
                page_count=1,
                pages=[OCRPage(page_number=1, text=raw_txt, mean_confidence=1.0)],
                full_text=raw_txt,
                normalized_text=normalize_ocr_text(raw_txt),
                engine_used="text_reader",
                engines_attempted=engines_attempted,
                duration_ms=duration,
                warnings=warnings
            )

        # BRANCH 1: PDF FAST PATH
        if file_path.lower().endswith(".pdf"):
            engines_attempted.append("pypdf")
            try:
                import pypdf
                reader = pypdf.PdfReader(file_path)
                page_count = len(reader.pages)
                pdf_pages = []
                total_chars = 0

                for idx, page in enumerate(reader.pages):
                    p_text = page.extract_text() or ""
                    total_chars += len(p_text.strip())
                    pdf_pages.append(OCRPage(
                        page_number=idx + 1,
                        text=p_text,
                        mean_confidence=1.0 if p_text.strip() else 0.0
                    ))

                if total_chars >= settings.SEMI_PDF_FAST_MIN_CHARS:
                    full_txt = "\n\n".join(p.text for p in pdf_pages)
                    duration = (time.time() - start_time) * 1000.0
                    return OCRResult(
                        document_id=doc_id,
                        source_path=file_path,
                        mime_type="application/pdf",
                        page_count=page_count,
                        pages=pdf_pages,
                        full_text=full_txt,
                        normalized_text=normalize_ocr_text(full_txt),
                        engine_used="pypdf",
                        engines_attempted=engines_attempted,
                        duration_ms=duration,
                        warnings=warnings
                    )
                else:
                    warnings.append(f"pypdf text count ({total_chars}) below threshold ({settings.SEMI_PDF_FAST_MIN_CHARS}). Falling back to Docling/OCR.")
            except Exception as e:
                warnings.append(f"pypdf extraction error: {e}")

            # BRANCH 2: PDF FALLBACK VIA DOCLING
            engines_attempted.append("docling")
            docling_conv = self._get_docling()
            if docling_conv is not None:
                try:
                    res = docling_conv.convert(file_path)
                    doc = res.document
                    doc_md = doc.export_to_markdown() if hasattr(doc, "export_to_markdown") else str(doc)
                    duration = (time.time() - start_time) * 1000.0
                    return OCRResult(
                        document_id=doc_id,
                        source_path=file_path,
                        mime_type="application/pdf",
                        page_count=len(res.document.pages) if hasattr(res.document, "pages") else 1,
                        pages=[OCRPage(page_number=1, text=doc_md, mean_confidence=0.95)],
                        full_text=doc_md,
                        normalized_text=normalize_ocr_text(doc_md),
                        engine_used="docling",
                        engines_attempted=engines_attempted,
                        duration_ms=duration,
                        warnings=warnings
                    )
                except Exception as e:
                    warnings.append(f"Docling PDF conversion failed: {e}")

        # BRANCH 3: IMAGE OCR (Tesseract via pytesseract with Preprocessing)
        engines_attempted.append("tesseract")
        tess_conf = 0.0
        tess_text = ""
        tess_elements = []

        try:
            import pytesseract
            if settings.TESSERACT_CMD:
                pytesseract.pytesseract.tesseract_cmd = settings.TESSERACT_CMD

            pil_img = Image.open(file_path)
            preprocessed_np = preprocess_image(pil_img)

            tess_text = pytesseract.image_to_string(preprocessed_np) or ""
            
            try:
                data = pytesseract.image_to_data(preprocessed_np, output_type=pytesseract.Output.DICT)
                confidences = []
                for i in range(len(data['text'])):
                    w_text = data['text'][i].strip()
                    conf = float(data['conf'][i])
                    if w_text and conf >= 0:
                        confidences.append(conf)
                        bbox = (float(data['left'][i]), float(data['top'][i]), float(data['width'][i]), float(data['height'][i]))
                        tess_elements.append(OCRTextElement(text=w_text, bbox=bbox, confidence=conf / 100.0))
                
                if confidences:
                    tess_conf = sum(confidences) / len(confidences)
            except Exception as e:
                warnings.append(f"Tesseract data confidence parsing error: {e}")
                tess_conf = 70.0 if tess_text.strip() else 0.0
        except Exception as e:
            warnings.append(f"Tesseract OCR failed: {e}")

        # BRANCH 4: SECONDARY FALLBACK (EasyOCR) IF CONFIDENCE LOW
        if settings.OCR_FALLBACK and (tess_conf < settings.OCR_CONFIDENCE_THRESHOLD or not tess_text.strip()):
            fallback_reason = f"Tesseract confidence ({tess_conf:.1f}%) below threshold ({settings.OCR_CONFIDENCE_THRESHOLD}%)"
            engines_attempted.append("easyocr")
            easy_reader = self._get_easyocr()
            
            if easy_reader is not None:
                try:
                    ocr_results = easy_reader.readtext(file_path, detail=1)
                    easy_texts = []
                    easy_confs = []
                    easy_elements = []

                    for bbox, text, conf in ocr_results:
                        if text.strip():
                            easy_texts.append(text)
                            easy_confs.append(float(conf) * 100.0)
                            xs = [pt[0] for pt in bbox]
                            ys = [pt[1] for pt in bbox]
                            b_tuple = (float(min(xs)), float(min(ys)), float(max(xs) - min(xs)), float(max(ys) - min(ys)))
                            easy_elements.append(OCRTextElement(text=text, bbox=b_tuple, confidence=float(conf)))

                    easy_text = "\n".join(easy_texts)
                    easy_mean_conf = (sum(easy_confs) / len(easy_confs)) if easy_confs else 0.0

                    if easy_mean_conf >= tess_conf:
                        duration = (time.time() - start_time) * 1000.0
                        return OCRResult(
                            document_id=doc_id,
                            source_path=file_path,
                            mime_type=mime_type,
                            page_count=1,
                            pages=[OCRPage(page_number=1, text=easy_text, words=easy_elements, mean_confidence=easy_mean_conf / 100.0)],
                            full_text=easy_text,
                            normalized_text=normalize_ocr_text(easy_text),
                            engine_used="easyocr",
                            engines_attempted=engines_attempted,
                            fallback_reason=fallback_reason,
                            duration_ms=duration,
                            warnings=warnings
                        )
                except Exception as e:
                    warnings.append(f"EasyOCR secondary fallback error: {e}")

        duration = (time.time() - start_time) * 1000.0
        return OCRResult(
            document_id=doc_id,
            source_path=file_path,
            mime_type=mime_type,
            page_count=1,
            pages=[OCRPage(page_number=1, text=tess_text, words=tess_elements, mean_confidence=tess_conf / 100.0)],
            full_text=tess_text,
            normalized_text=normalize_ocr_text(tess_text),
            engine_used="tesseract" if tess_text.strip() else "fallback_raw",
            engines_attempted=engines_attempted,
            duration_ms=duration,
            warnings=warnings
        )

ocr_cascade = OCREngineCascade()
