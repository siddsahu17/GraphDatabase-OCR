import json
import os
from typing import Dict, Any

SCHEMA_FILE_PATH = os.path.join(os.path.dirname(__file__), "default_schemas.json")

class SchemaRegistry:
    def __init__(self, file_path: str = SCHEMA_FILE_PATH):
        self.file_path = file_path
        self._schemas: Dict[str, Any] = {}
        self.load_schemas()

    def load_schemas(self):
        if os.path.exists(self.file_path):
            with open(self.file_path, "r", encoding="utf-8") as f:
                self._schemas = json.load(f)
        else:
            self._schemas = {}

    def get_all_schemas(self) -> Dict[str, Any]:
        return self._schemas

    def get_schema(self, schema_key: str) -> Dict[str, Any]:
        return self._schemas.get(schema_key, {})

    def save_schemas(self):
        with open(self.file_path, "w", encoding="utf-8") as f:
            json.dump(self._schemas, f, indent=2)

    def register_schema(self, schema_key: str, schema_data: Dict[str, Any]):
        self._schemas[schema_key] = schema_data
        self.save_schemas()

schema_registry = SchemaRegistry()
