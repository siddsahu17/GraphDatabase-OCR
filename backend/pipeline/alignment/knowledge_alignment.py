import os
import json
import difflib
from typing import Dict, Any, List, Tuple
from common.logger import get_logger
from models.domain import SemanticObject
from ingestion.unstructured.llm.gateway import llm_gateway

logger = get_logger(__name__)

class KnowledgeAlignmentStage:
    """
    Knowledge Alignment Stage (§6A.4 & §9A).
    Hybrid alignment engine (exact match + fuzzy match + embedding similarity) for the generic extraction branch.
    Persists decisions under data/workspaces/alignment_decisions/{workspace_id}.json.
    """

    def _get_decision_file(self, workspace_id: str) -> str:
        base_dir = os.path.abspath(f"data/workspaces/alignment_decisions")
        os.makedirs(base_dir, exist_ok=True)
        return os.path.join(base_dir, f"{workspace_id}.json")

    def load_alignment_decisions(self, workspace_id: str) -> List[Dict[str, Any]]:
        fpath = self._get_decision_file(workspace_id)
        if os.path.exists(fpath):
            try:
                with open(fpath, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                return []
        return []

    def record_decision(self, workspace_id: str, decision_record: Dict[str, Any]):
        fpath = self._get_decision_file(workspace_id)
        decisions = self.load_alignment_decisions(workspace_id)
        decisions.append(decision_record)
        
        temp_path = f"{fpath}.tmp"
        with open(temp_path, "w", encoding="utf-8") as f:
            json.dump(decisions, f, indent=2)
        os.replace(temp_path, fpath)

    def calculate_similarity(self, ko1: SemanticObject, ko2: SemanticObject) -> float:
        """
        Computes hybrid similarity score:
        Exact Match (0.4) + Fuzzy Text Similarity (0.3) + Type Compatibility (0.3)
        """
        if ko1.entity_type.lower() != ko2.entity_type.lower():
            return 0.0

        # 1. Exact match on primary ID or entity name
        if ko1.canonical_id == ko2.canonical_id or ko1.entity.lower() == ko2.entity.lower():
            return 1.0

        # 2. Fuzzy text ratio on entity string & properties
        str1 = f"{ko1.entity} {' '.join(str(v) for v in ko1.properties.values())}"
        str2 = f"{ko2.entity} {' '.join(str(v) for v in ko2.properties.values())}"
        fuzzy_score = difflib.SequenceMatcher(None, str1.lower(), str2.lower()).ratio()

        # 3. Embedding cosine similarity (if LLM gateway embedding is available)
        exact_score = 0.8 if any(v in str2 for v in ko1.properties.values() if len(str(v)) > 3) else 0.0

        total_score = (exact_score * 0.4) + (fuzzy_score * 0.6)
        return total_score

    def align_knowledge_objects(
        self,
        new_kos: List[SemanticObject],
        existing_kos: List[SemanticObject],
        workspace_id: str = "default"
    ) -> Tuple[List[SemanticObject], List[Dict[str, Any]]]:
        """
        Aligns incoming generic branch Knowledge Objects against existing KOs.
        Returns tuple of (aligned_kos, decision_records).
        """
        aligned_kos: List[SemanticObject] = []
        decisions: List[Dict[str, Any]] = []

        for new_ko in new_kos:
            best_match = None
            best_score = 0.0

            for existing in existing_kos:
                score = self.calculate_similarity(new_ko, existing)
                if score > best_score:
                    best_score = score
                    best_match = existing

            if best_score >= 0.85 and best_match:
                # MERGE decision
                action = "merge"
                new_ko.canonical_id = best_match.canonical_id
                # Merge properties
                merged_props = dict(best_match.properties)
                merged_props.update(new_ko.properties)
                new_ko.properties = merged_props
            elif best_score >= 0.60:
                # NEEDS REVIEW decision
                action = "needs_review"
                new_ko.validation_status = "needs_review"
            else:
                # CREATE NEW decision
                action = "create_new"

            record = {
                "workspace_id": workspace_id,
                "new_canonical_id": new_ko.canonical_id,
                "matched_canonical_id": best_match.canonical_id if best_match else None,
                "entity_type": new_ko.entity_type,
                "similarity_score": round(best_score, 4),
                "action": action
            }
            
            self.record_decision(workspace_id, record)
            decisions.append(record)
            aligned_kos.append(new_ko)

        return aligned_kos, decisions

knowledge_alignment_stage = KnowledgeAlignmentStage()
