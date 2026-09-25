import re
from typing import Dict, Any, List, Tuple
from common.logger import get_logger

logger = get_logger(__name__)

class KeyValueExtractor:
    """
    Layout Key-Value Extractor for generic semi-structured documents (§6A.4).
    Extracts candidate (key, value) text pairs using colon delimiters and tab alignment.
    """
    
    def extract_kv_pairs(self, text: str) -> List[Tuple[str, str]]:
        kv_pairs = []
        if not text:
            return kv_pairs

        lines = [line.strip() for line in text.split('\n') if line.strip()]

        for line in lines:
            # Match Colon Delimited Key-Value Pairs (e.g., "Patient Name: John Doe", "MRN: 103948")
            match = re.match(r'^([A-Za-z0-9\s_\-\.\#]{2,40})[:\=]\s*(.+)$', line)
            if match:
                key = match.group(1).strip()
                val = match.group(2).strip()
                if key and val and len(key) < 40 and not key.lower().startswith(('http', 'www')):
                    kv_pairs.append((key, val))

        return kv_pairs

kv_extractor = KeyValueExtractor()
