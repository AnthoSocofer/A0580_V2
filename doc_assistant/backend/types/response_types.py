from dataclasses import dataclass
from typing import List, Dict, Any, Optional, Tuple
from enum import Enum

class RelevanceLevel(Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"

@dataclass
class DocumentReference:
    doc_id: str
    doc_title: str
    text: str
    relevance_score: float
    page_numbers: Optional[Tuple[Optional[int], Optional[int]]] = None
    metadata: Optional[Dict[str, Any]] = None
    kb_title: Optional[str] = None
    
    @property
    def title(self) -> str:
        return self.doc_title

@dataclass 
class SearchContext:
    kb_id: str
    results: List[DocumentReference]
    mapping_score: float
    kb_title: Optional[str] = None