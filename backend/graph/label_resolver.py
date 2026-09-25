import re

class LabelResolver:
    """
    Resolves entity types and relationship names to sanitized Cypher labels (§10).
    """
    @staticmethod
    def sanitize_label(label: str) -> str:
        if not label:
            return "Entity"
        # Remove non-alphanumeric characters except underscores
        clean = re.sub(r'[^A-Za-z0-9_]', '', label)
        return clean if clean else "Entity"

    @staticmethod
    def sanitize_rel_type(rel_type: str) -> str:
        if not rel_type:
            return "RELATED_TO"
        clean = re.sub(r'[^A-Za-z0-9_]', '', rel_type).upper()
        return clean if clean else "RELATED_TO"

label_resolver = LabelResolver()
