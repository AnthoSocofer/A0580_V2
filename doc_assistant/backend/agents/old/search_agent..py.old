from typing import List, Optional, Dict, Any
from dataclasses import dataclass
from enum import Enum
from backend.types.response_types import SearchContext, DocumentReference
from dsrag.database.vector.types import MetadataFilter
from dsrag.knowledge_base import KnowledgeBase
import streamlit as st

class SearchMode(Enum):
    PRECISE = "precise"       # Haute précision, peu de résultats
    BALANCED = "balanced"     # Équilibre précision/rappel
    THOROUGH = "thorough"    # Plus de résultats, moins stricts sur la pertinence
    EXHAUSTIVE = "exhaustive" # Tous les résultats possiblement pertinents

@dataclass
class SearchConfig:
    mode: SearchMode = SearchMode.BALANCED
    min_relevance: float = 0.6
    max_segments_per_doc: int = 3
    adaptive_recall: bool = True  # Ajuste automatiquement les paramètres si pas assez de résultats

class SearchAgent:
    # Paramètres RSE optimisés pour différents modes de recherche
    RSE_CONFIGS = {
        SearchMode.PRECISE: {
            'max_length': 10,
            'overall_max_length': 20,
            'minimum_value': 0.7,
            'irrelevant_chunk_penalty': 0.2,
            'overall_max_length_extension': 3,
            'decay_rate': 20,
            'top_k_for_document_selection': 5,
            'chunk_length_adjustment': True,
        },
        SearchMode.BALANCED: {
            'max_length': 15,
            'overall_max_length': 30,
            'minimum_value': 0.5,
            'irrelevant_chunk_penalty': 0.18,
            'overall_max_length_extension': 5,
            'decay_rate': 30,
            'top_k_for_document_selection': 10,
            'chunk_length_adjustment': True,
        },
        SearchMode.THOROUGH: {
            'max_length': 20,
            'overall_max_length': 50,
            'minimum_value': 0.3,
            'irrelevant_chunk_penalty': 0.15,
            'overall_max_length_extension': 8,
            'decay_rate': 40,
            'top_k_for_document_selection': 15,
            'chunk_length_adjustment': True,
        },
        SearchMode.EXHAUSTIVE: {
            'max_length': 25,
            'overall_max_length': 100,
            'minimum_value': 0.1,
            'irrelevant_chunk_penalty': 0.1,
            'overall_max_length_extension': 10,
            'decay_rate': 50,
            'top_k_for_document_selection': 20,
            'chunk_length_adjustment': True,
        }
    }

    def __init__(self, kb_manager):
        self.kb_manager = kb_manager

    def _get_rse_params(self, mode: SearchMode) -> dict:
        """Récupère les paramètres RSE pour un mode donné"""
        return self.RSE_CONFIGS[mode].copy()

    def _adjust_params_for_recall(self, params: dict) -> dict:
        """Ajuste les paramètres pour augmenter le rappel"""
        adjusted = params.copy()
        adjusted['minimum_value'] = max(0.1, params['minimum_value'] - 0.2)
        adjusted['overall_max_length'] = int(params['overall_max_length'] * 1.5)
        adjusted['irrelevant_chunk_penalty'] *= 0.8
        return adjusted

    async def search(
        self,
        query: str,
        kb: KnowledgeBase,
        filters: Optional[Dict[str, Any]] = None,
        config: Optional[SearchConfig] = None
    ) -> List[DocumentReference]:
        """
        Effectue une recherche avec gestion adaptative de la qualité des résultats
        
        Args:
            query: La requête de recherche
            kb: La base de connaissances
            filters: Filtres de métadonnées optionnels
            config: Configuration de la recherche
        """
        if config is None:
            config = SearchConfig()

        metadata_filter = None
        if filters:
            metadata_filter = MetadataFilter(
                field=filters.get("field", ""),
                operator=filters.get("operator", "equals"),
                value=filters.get("value", "")
            )

        # Tentative initiale avec les paramètres du mode choisi
        rse_params = self._get_rse_params(config.mode)
        results = kb.query(
            search_queries=[query],
            metadata_filter=metadata_filter,
            rse_params=rse_params
        )

        # Si pas assez de résultats et adaptive_recall activé, essayer avec des paramètres plus souples
        if not results and config.adaptive_recall:
            st.info("Adaptation des paramètres pour une recherche plus approfondie...")
            for mode in [SearchMode.BALANCED, SearchMode.THOROUGH, SearchMode.EXHAUSTIVE]:
                if mode.value <= config.mode.value:
                    continue
                    
                rse_params = self._get_rse_params(mode)
                if config.mode != SearchMode.EXHAUSTIVE:
                    rse_params = self._adjust_params_for_recall(rse_params)
                    
                results = kb.query(
                    search_queries=[query],
                    metadata_filter=metadata_filter,
                    rse_params=rse_params
                )
                if results:
                    break

        if not results:
            return []

        # Conversion des résultats en DocumentReference
        doc_references = []
        for r in results:
            # Récupération du titre et des métadonnées du document
            doc_title = kb.chunk_db.get_document_title(r["doc_id"], r["chunk_start"]) or ""
            doc_metadata = kb.chunk_db.get_document(r["doc_id"]).get("metadata", {})
            
            doc_references.append(
                DocumentReference(
                    doc_id=r["doc_id"],
                    doc_title=doc_title,
                    text=r["text"],
                    relevance_score=r["score"],
                    page_numbers=(r.get("chunk_page_start"), r.get("chunk_page_end")),
                    metadata=doc_metadata
                )
            )

        # Filtrage des résultats selon les critères de qualité
        filtered_refs = [
            ref for ref in doc_references 
            if ref.relevance_score >= config.min_relevance
        ]

        # Limitation du nombre de segments par document si nécessaire
        if config.max_segments_per_doc > 0:
            doc_segments = {}
            for ref in filtered_refs:
                if ref.doc_id not in doc_segments:
                    doc_segments[ref.doc_id] = []
                if len(doc_segments[ref.doc_id]) < config.max_segments_per_doc:
                    doc_segments[ref.doc_id].append(ref)
            
            filtered_refs = [
                ref for segments in doc_segments.values() 
                for ref in segments
            ]

        return sorted(filtered_refs, key=lambda x: x.relevance_score, reverse=True)

    async def multi_kb_search(
        self,
        query: str,
        kb_mappings: List[Any],
        config: Optional[SearchConfig] = None
    ) -> List[SearchContext]:
        """
        Effectue une recherche sur plusieurs bases de connaissances
        
        Args:
            query: La requête de recherche
            kb_mappings: Liste des mappings de bases de connaissances
            config: Configuration de la recherche
        """
        search_contexts = []
        
        for mapping in kb_mappings:
            kb = self.kb_manager.load_knowledge_base(mapping.kb_id)
            if not kb:
                continue

            # Ajuster la configuration en fonction du score de mapping
            if config:
                adjusted_config = SearchConfig(
                    mode=config.mode,
                    min_relevance=config.min_relevance * mapping.relevance_score,
                    max_segments_per_doc=config.max_segments_per_doc,
                    adaptive_recall=config.adaptive_recall
                )
            else:
                adjusted_config = None

            results = await self.search(
                query=query,
                kb=kb,
                config=adjusted_config
            )

            if results:
                search_contexts.append(SearchContext(
                    kb_id=mapping.kb_id,
                    results=results,
                    mapping_score=mapping.relevance_score
                ))

        return search_contexts