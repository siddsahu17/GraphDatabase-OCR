import os
import json
import hashlib
from typing import Dict, Any, Optional, List

class EntityRegistryStore:
    """
    Registry store for deterministic entity resolution (§9A).
    Maps (entity_type, business_key_str) to a stable canonical_id.
    Persisted under data/semi_structured/entity_registry.json.
    """
    def __init__(self, storage_path: str = "data/semi_structured/entity_registry.json"):
        self.storage_path = os.path.abspath(storage_path)
        self._registry: Dict[str, str] = {}
        self._load()

    def _load(self):
        if os.path.exists(self.storage_path):
            try:
                with open(self.storage_path, "r", encoding="utf-8") as f:
                    self._registry = json.load(f)
            except Exception:
                self._registry = {}
        else:
            os.makedirs(os.path.dirname(self.storage_path), exist_ok=True)
            self._registry = {}

    def _save(self):
        os.makedirs(os.path.dirname(self.storage_path), exist_ok=True)
        temp_path = f"{self.storage_path}.tmp"
        with open(temp_path, "w", encoding="utf-8") as f:
            json.dump(self._registry, f, indent=2)
        os.replace(temp_path, self.storage_path)

    def _make_key(self, entity_type: str, business_key_val: str) -> str:
        clean_type = entity_type.strip().lower()
        clean_val = str(business_key_val).strip().lower()
        return f"{clean_type}:{clean_val}"

    def get_or_create_canonical_id(self, entity_type: str, business_key_val: str) -> str:
        """
        Returns existing canonical_id for business key, or creates a new deterministic canonical_id.
        """
        if not business_key_val:
            # Fallback to random hash if key is missing
            return f"{entity_type.lower()}_{hash(os.urandom(8)) & 0xffffffff:08x}"

        key = self._make_key(entity_type, business_key_val)
        if key in self._registry:
            return self._registry[key]

        # Generate stable canonical ID from hash of key
        hash_suffix = hashlib.sha256(key.encode("utf-8")).hexdigest()[:10]
        canonical_id = f"{entity_type.lower()}_{hash_suffix}"
        
        self._registry[key] = canonical_id
        self._save()
        return canonical_id

entity_registry_store = EntityRegistryStore()
