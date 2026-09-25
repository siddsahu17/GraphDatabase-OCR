import re
from datetime import datetime
from typing import Dict, Any, List, Tuple, Optional
from common.logger import get_logger

logger = get_logger(__name__)

class TemplateExtractor:
    """
    Deterministic template extractor for semi-structured documents.
    Extracts regex fields, coerces types, parses line items, and runs validation checks.
    """
    
    def coerce_value(self, val_str: str, ftype: str) -> Any:
        if not val_str:
            return None
            
        clean_str = val_str.strip()

        if ftype == "money":
            # Remove currency symbols and commas
            num_str = re.sub(r'[^\d\.]', '', clean_str)
            try:
                return float(num_str) if num_str else 0.0
            except ValueError:
                return 0.0

        elif ftype == "date":
            # Normalize common date formats to ISO YYYY-MM-DD
            for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%d/%m/%Y", "%m-%d-%Y", "%d-%m-%Y"):
                try:
                    return datetime.strptime(clean_str, fmt).strftime("%Y-%m-%d")
                except ValueError:
                    continue
            return clean_str

        elif ftype == "integer":
            num_str = re.sub(r'[^\d]', '', clean_str)
            try:
                return int(num_str) if num_str else 0
            except ValueError:
                return 0

        return clean_str

    def extract(self, text: str, template: Dict[str, Any]) -> Tuple[Dict[str, Any], List[str]]:
        """
        Extracts fields and line items from text using template specification.
        Returns tuple of (extracted_fields_dict, validation_errors_list).
        """
        extracted = {}
        errors = []

        fields_def = template.get("fields", [])
        for field in fields_def:
            fname = field.get("name")
            fregex = field.get("regex")
            ftype = field.get("type", "string")
            is_req = field.get("required", False)

            val = None
            if fregex:
                match = re.search(fregex, text)
                if match:
                    val_str = match.group(1) if match.groups() else match.group(0)
                    val = self.coerce_value(val_str, ftype)

            if is_req and (val is None or val == ""):
                errors.append(f"Required field '{fname}' missing or could not be extracted.")

            extracted[fname] = val

        # Extract line items table if specified
        line_items_spec = template.get("line_items", {})
        row_regex = line_items_spec.get("row_regex")
        cols = line_items_spec.get("columns", [])

        line_items = []
        if row_regex:
            for match in re.finditer(row_regex, text):
                groups = match.groups()
                if len(groups) >= len(cols):
                    item = {}
                    for i, col_name in enumerate(cols):
                        raw_col_val = groups[i].strip()
                        if "amount" in col_name or "rate" in col_name or "price" in col_name:
                            item[col_name] = self.coerce_value(raw_col_val, "money")
                        elif "qty" in col_name or "quantity" in col_name:
                            item[col_name] = self.coerce_value(raw_col_val, "integer")
                        else:
                            item[col_name] = raw_col_val
                    line_items.append(item)

        extracted["line_items"] = line_items

        # Run template arithmetic validation checks if configured
        val_spec = template.get("validation", {})
        if "checks" in val_spec:
            total_amt = extracted.get("total_amount")
            if total_amt is not None and line_items:
                items_sum = sum(item.get("amount", 0.0) for item in line_items if isinstance(item.get("amount"), (int, float)))
                if items_sum > 0 and abs(items_sum - total_amt) > 1.0:
                    errors.append(f"Line items sum ({items_sum:.2f}) does not match total amount ({total_amt:.2f}).")

        return extracted, errors

template_extractor = TemplateExtractor()
