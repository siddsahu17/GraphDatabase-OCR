import os
import json
import time
import threading
from typing import Dict, Any, List, Optional
from common.logger import get_logger
from common.exceptions import ValidationException

logger = get_logger(__name__)

STATUS_PENDING = "pending"
STATUS_NEEDS_REVIEW = "needs_review"
STATUS_INGESTED = "ingested"

VALID_TRANSITIONS = {
    "new": [STATUS_PENDING, STATUS_NEEDS_REVIEW],
    STATUS_NEEDS_REVIEW: [STATUS_PENDING],
    STATUS_PENDING: [STATUS_INGESTED, STATUS_NEEDS_REVIEW],
    STATUS_INGESTED: [STATUS_PENDING]  # For reprocess
}

class DocumentCache:
    """
    JSON-backed cache under data/semi_structured/cache/ (pending.json, needs_review.json, ingested.json).
    Ensures atomic writes and thread safety.
    """
    def __init__(self, cache_dir: str = "data/semi_structured/cache", upload_dir: str = "data/semi_structured/uploads"):
        self.cache_dir = os.path.abspath(cache_dir)
        self.upload_dir = os.path.abspath(upload_dir)
        self._lock = threading.Lock()
        
        os.makedirs(self.cache_dir, exist_ok=True)
        os.makedirs(self.upload_dir, exist_ok=True)

    def _get_file_path(self, status: str) -> str:
        return os.path.join(self.cache_dir, f"{status}.json")

    def _read_records(self, status: str) -> Dict[str, Dict[str, Any]]:
        path = self._get_file_path(status)
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Error reading cache file {path}: {e}")
                return {}
        return {}

    def _write_records(self, status: str, records: Dict[str, Dict[str, Any]]):
        path = self._get_file_path(status)
        temp_path = f"{path}.tmp"
        with open(temp_path, "w", encoding="utf-8") as f:
            json.dump(records, f, indent=2)
        os.replace(temp_path, path)

    def get_document(self, document_id: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            for status in [STATUS_PENDING, STATUS_NEEDS_REVIEW, STATUS_INGESTED]:
                records = self._read_records(status)
                if document_id in records:
                    return records[document_id]
        return None

    def list_documents(self, status: Optional[str] = None) -> List[Dict[str, Any]]:
        with self._lock:
            if status:
                return list(self._read_records(status).values())
            
            all_docs = []
            for s in [STATUS_PENDING, STATUS_NEEDS_REVIEW, STATUS_INGESTED]:
                all_docs.extend(list(self._read_records(s).values()))
            return all_docs

    def save_document(
        self,
        document_id: str,
        source_path: str,
        target_status: str,
        ocr_result_ref: Optional[Dict[str, Any]] = None,
        domain: Optional[str] = None,
        extracted_fields: Optional[Dict[str, Any]] = None,
        validation_errors: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Creates or updates a document record, enforcing legal status transitions.
        """
        with self._lock:
            existing = None
            old_status = "new"

            for s in [STATUS_PENDING, STATUS_NEEDS_REVIEW, STATUS_INGESTED]:
                recs = self._read_records(s)
                if document_id in recs:
                    existing = recs[document_id]
                    old_status = s
                    break

            # Enforce valid transition rules
            if target_status not in VALID_TRANSITIONS.get(old_status, []):
                raise ValidationException(
                    f"Illegal cache transition for doc '{document_id}' from '{old_status}' to '{target_status}'. "
                    f"Allowed transitions from '{old_status}': {VALID_TRANSITIONS.get(old_status, [])}"
                )

            now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
            record = existing or {
                "document_id": document_id,
                "source_path": source_path,
                "created_at": now
            }

            record.update({
                "source_path": source_path,
                "status": target_status,
                "updated_at": now,
                "domain": domain or record.get("domain"),
                "ocr_result_ref": ocr_result_ref or record.get("ocr_result_ref"),
                "extracted_fields": extracted_fields if extracted_fields is not None else record.get("extracted_fields", {}),
                "validation_errors": validation_errors if validation_errors is not None else record.get("validation_errors", [])
            })

            # If moving to new status file, remove from old file
            if old_status != "new" and old_status != target_status:
                old_recs = self._read_records(old_status)
                if document_id in old_recs:
                    del old_recs[document_id]
                    self._write_records(old_status, old_recs)

            # Write to new status file
            target_recs = self._read_records(target_status)
            target_recs[document_id] = record
            self._write_records(target_status, target_recs)

            logger.info(f"Document '{document_id}' status transitioned: '{old_status}' -> '{target_status}'")
            return record

document_cache = DocumentCache()
