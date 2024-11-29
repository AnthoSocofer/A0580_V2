from typing import List, Optional, Dict, Any
from dataclasses import dataclass
from enum import Enum
from backend.types.response_types import SearchContext, DocumentReference
from dsrag.database.vector.types import MetadataFilter
from dsrag.knowledge_base import KnowledgeBase
import streamlit as st
from nltk.tokenize import regexp_tokenize
from nltk.corpus import stopwords
import nltk
import re
from collections import defaultdict

# Initialisation correcte des ressources NLTK
def initialize_nltk():
    """Initialise les ressources NLTK nécessaires"""
    required_resources = {
        'punkt': 'tokenizers/punkt',
        'stopwords': 'corpora/stopwords'
    }
    
    for resource, path in required_resources.items():
        try:
            nltk.data.find(path)
        except LookupError:
            st.info(f"📥 Téléchargement de la ressource NLTK : {resource}")
            try:
                nltk.download(resource, quiet=True)
            except Exception as e:
                st.error(f"❌ Erreur lors du téléchargement de {resource}: {str(e)}")
                # Utiliser une alternative sans NLTK pour le tokenization
                return False
    return True

class SearchMode(Enum):
    PRECISE = "precise"       
    BALANCED = "balanced"     
    THOROUGH = "thorough"    
    EXHAUSTIVE = "exhaustive" 

@dataclass
class SearchConfig:
    mode: SearchMode = SearchMode.BALANCED
    min_relevance: float = 0.6
    max_segments_per_doc: int = 3
    adaptive_recall: bool = True
    enable_fallback: bool = True      # Active la recherche de fallback combinée
    fallback_min_relevance: float = 0.3  # Seuil de pertinence pour les résultats de fallback
    fallback_search_limit: int = 200  # Limite pour la recherche de fallback

class SearchAgent:
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
        self.use_nltk = initialize_nltk()
        
        # Charger les stop words ou utiliser une liste basique si NLTK échoue
        try:
            self.stop_words = set(stopwords.words('english') + stopwords.words('french'))
        except:
            # Liste basique de stop words en cas d'échec de NLTK
            self.stop_words = set([
                'le', 'la', 'les', 'de', 'du', 'des', 'un', 'une', 'et', 'ou', 'mais',
                'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for'
            ])
    

    def _get_rse_params(self, mode: SearchMode) -> dict:
        return self.RSE_CONFIGS[mode].copy()

    def _adjust_params_for_recall(self, params: dict) -> dict:
        adjusted = params.copy()
        adjusted['minimum_value'] = max(0.1, params['minimum_value'] - 0.2)
        adjusted['overall_max_length'] = int(params['overall_max_length'] * 1.5)
        adjusted['irrelevant_chunk_penalty'] *= 0.8
        return adjusted

    def _tokenize_text(self, text: str) -> List[str]:
        """Tokenize le texte avec fallback si NLTK n'est pas disponible"""
        text = self._preprocess_text(text)
        if self.use_nltk:
            try:
                return regexp_tokenize(text, pattern=r'\w+')
            except:
                pass
        # Fallback simple si NLTK n'est pas disponible
        return text.split()

    def _preprocess_text(self, text: str) -> str:
        """Prétraite le texte pour la recherche"""
        text = text.lower()
        text = re.sub(r'[^\w\s]', ' ', text)
        text = re.sub(r'\s+', ' ', text)
        return text.strip()

    def _get_keywords(self, text: str) -> List[str]:
        """Extrait les mots-clés significatifs avec gestion d'erreur robuste"""
        text = self._preprocess_text(text)
        tokens = self._tokenize_text(text)
        keywords = [word for word in tokens 
                   if word not in self.stop_words 
                   and len(word) > 2]
        return list(set(keywords))

    def _keyword_search_score(self, text: str, keywords: List[str]) -> float:
        """Calcule un score de pertinence basé sur les mots-clés"""
        if not keywords:
            return 0.0
            
        text = self._preprocess_text(text)
        text_words = set(word for word in text.split() if word not in self.stop_words)
        
        matches = sum(1 for keyword in keywords if keyword in text_words)
        score = matches / len(keywords)
        
        for i in range(len(keywords) - 1):
            if ' '.join(keywords[i:i+2]) in text:
                score += 0.1
                
        return min(1.0, score)

    async def _combined_fallback_search(
        self,
        query: str,
        kb: KnowledgeBase,
        metadata_filter: Optional[MetadataFilter],
        config: SearchConfig
    ) -> List[DocumentReference]:
        """
        Effectue une recherche combinée utilisant kb.search() et la recherche par mots-clés
        """
        st.info("🔍 Activation de la recherche combinée (kb.search + mots-clés)")
        
        # Extraction des mots-clés
        keywords = self._get_keywords(query)
        if not keywords:
            st.warning("Aucun mot-clé significatif trouvé dans la requête")
            return []

        st.info(f"Mots-clés identifiés: {', '.join(keywords)}")
        
        # 1. Recherche avec kb.search()
        kb_results = []
        try:
            # Correction: passer query directement sans le mettre dans une liste
            kb_search_results = kb.search(query, config.fallback_search_limit, metadata_filter)
            for result in kb_search_results:
                doc_id = result["metadata"]["doc_id"]
                chunk_index = result["metadata"]["chunk_index"]
                similarity = result["similarity"]
                
                if similarity >= config.fallback_min_relevance:
                    chunk_text = kb.chunk_db.get_chunk_text(doc_id, chunk_index)
                    doc_title = kb.chunk_db.get_document_title(doc_id, chunk_index) or ""
                    doc_info = kb.chunk_db.get_document(doc_id)
                    page_numbers = kb.chunk_db.get_chunk_page_numbers(doc_id, chunk_index)
                    
                    kb_results.append(DocumentReference(
                        doc_id=doc_id,
                        doc_title=doc_title,
                        text=chunk_text,
                        relevance_score=similarity,
                        page_numbers=page_numbers,
                        metadata=doc_info.get('metadata', {}) if doc_info else {}
                    ))
        except Exception as e:
            st.warning(f"Erreur lors de la recherche kb.search(): {str(e)}")
            st.info("🔄 Continuation avec la recherche par mots-clés uniquement")
        
        # 2. Recherche par mots-clés
        keyword_results = []
        doc_ids = kb.chunk_db.get_all_doc_ids()
        
        for doc_id in doc_ids:
            if metadata_filter:
                doc_info = kb.chunk_db.get_document(doc_id)
                if not self._check_metadata_filter(doc_info, metadata_filter):
                    continue
            
            chunk_index = 0
            while True:
                chunk_text = kb.chunk_db.get_chunk_text(doc_id, chunk_index)
                if not chunk_text:
                    break
                
                score = self._keyword_search_score(chunk_text, keywords)
                
                if score >= config.fallback_min_relevance:
                    doc_title = kb.chunk_db.get_document_title(doc_id, chunk_index) or ""
                    doc_info = kb.chunk_db.get_document(doc_id)
                    page_numbers = kb.chunk_db.get_chunk_page_numbers(doc_id, chunk_index)
                    
                    keyword_results.append(DocumentReference(
                        doc_id=doc_id,
                        doc_title=doc_title,
                        text=chunk_text,
                        relevance_score=score,
                        page_numbers=page_numbers,
                        metadata=doc_info.get('metadata', {}) if doc_info else {}
                    ))
                
                chunk_index += 1

        # Fusionner et déduplicater les résultats
        all_results = []
        seen_chunks = set()
        
        # Fonction helper pour créer une clé unique pour chaque chunk
        def get_chunk_key(result):
            return f"{result.doc_id}_{result.text[:100]}"
        
        # Ajouter d'abord les résultats de kb.search()
        for result in kb_results:
            chunk_key = get_chunk_key(result)
            if chunk_key not in seen_chunks:
                seen_chunks.add(chunk_key)
                all_results.append(result)

        # Ajouter ensuite les résultats de la recherche par mots-clés
        for result in keyword_results:
            chunk_key = get_chunk_key(result)
            if chunk_key not in seen_chunks:
                seen_chunks.add(chunk_key)
                # Ajuster le score pour donner une légère préférence aux résultats de kb.search()
                result.relevance_score *= 0.9
                all_results.append(result)

        # Trier par pertinence
        all_results.sort(key=lambda x: x.relevance_score, reverse=True)
        
        # Limiter le nombre de segments par document
        if config.max_segments_per_doc > 0:
            filtered_results = []
            doc_count = defaultdict(int)
            
            for result in all_results:
                if doc_count[result.doc_id] < config.max_segments_per_doc:
                    filtered_results.append(result)
                    doc_count[result.doc_id] += 1
            
            all_results = filtered_results

        return all_results

    def _check_metadata_filter(self, doc_info: Optional[Dict], metadata_filter: MetadataFilter) -> bool:
        """Vérifie si un document correspond au filtre de métadonnées"""
        if not doc_info or not metadata_filter:
            return True
            
        field = metadata_filter["field"]
        operator = metadata_filter["operator"]
        value = metadata_filter["value"]
        
        if field == "doc_id":
            doc_id = doc_info["id"]
            if operator == "equals":
                return doc_id == value
            elif operator == "in":
                return doc_id in value
        
        return True

    async def search(self, query: str, kb: KnowledgeBase, filters: Optional[Dict] = None) -> List[DocumentReference]:
        """
        Effectue une recherche dans une base de connaissances
        """
        try:
            # Si la base n'est pas accessible, retourner une liste vide plutôt que None
            if not kb:
                print(f"Base de connaissances non accessible")
                return []

            metadata_filter = None
            if filters:
                metadata_filter = MetadataFilter(
                    field=filters.get("field", ""),
                    operator=filters.get("operator", "equals"),
                    value=filters.get("value", "")
                )

            results = kb.query(
                search_queries=[query],
                metadata_filter=metadata_filter,
                rse_params="balanced"  # Utiliser les paramètres par défaut
            )

            # S'assurer qu'on retourne toujours une liste, même vide
            if not results:
                return []

            # Transformer les résultats en DocumentReference
            doc_references = []
            for r in results:
                doc_title = kb.chunk_db.get_document_title(r["doc_id"], r["chunk_start"]) or ""
                doc_info = kb.chunk_db.get_document(r["doc_id"])
                
                # Protection contre les None
                if r.get("doc_id") and "chunk_start" in r:
                    doc_references.append(
                        DocumentReference(
                            doc_id=r["doc_id"],
                            doc_title=doc_title,
                            text=r.get("text", ""),
                            relevance_score=r.get("score", 0.0),
                            page_numbers=(r.get("chunk_page_start"), r.get("chunk_page_end")),
                            metadata=doc_info.get('metadata', {}) if doc_info else {}
                        )
                    )

            return doc_references

        except Exception as e:
            print(f"Erreur lors de la recherche: {str(e)}")
            return []  # Retourner une liste vide en cas d'erreur au lieu de None
    
    async def multi_kb_search(
        self,
        query: str,
        kb_mappings: List[Any],
        config: Optional[SearchConfig] = None
    ) -> List[SearchContext]:
        """
        Effectue une recherche sur plusieurs bases de connaissances
        """
        search_contexts = []
        total_kbs = len(kb_mappings)
        
        st.info(f"🔍 Recherche dans {total_kbs} bases de connaissances")
        
        for idx, mapping in enumerate(kb_mappings, 1):
            # Charger les informations de la base
            kb = self.kb_manager.load_knowledge_base(mapping.kb_id)
            if not kb:
                st.warning(f"⚠️ Base {mapping.kb_id} non trouvée ou inaccessible")
                continue
                
            # Récupérer le titre de la base pour les messages
            kb_info = next((kb for kb in self.kb_manager.list_knowledge_bases() 
                        if kb["id"] == mapping.kb_id), None)
            kb_title = kb_info["title"] if kb_info else mapping.kb_id
            
            st.info(f"📚 [{idx}/{total_kbs}] Recherche dans la base: {kb_title} (score de mapping: {mapping.relevance_score:.2f})")

            # Ajuster la configuration en fonction du score de mapping
            if config:
                adjusted_config = SearchConfig(
                    mode=config.mode,
                    min_relevance=config.min_relevance * mapping.relevance_score,
                    max_segments_per_doc=config.max_segments_per_doc,
                    adaptive_recall=config.adaptive_recall,
                    enable_fallback=config.enable_fallback,
                    fallback_min_relevance=config.fallback_min_relevance,
                    fallback_search_limit=config.fallback_search_limit
                )
            else:
                adjusted_config = None

            # Effectuer la recherche
            results = await self.search(
                query=query,
                kb=kb,
                config=adjusted_config
            )

            if results:
                st.success(f"✅ {len(results)} résultats trouvés dans {kb_title}")
                search_contexts.append(SearchContext(
                    kb_id=mapping.kb_id,
                    results=results,
                    mapping_score=mapping.relevance_score,
                    kb_title=kb_title
                ))
            else:
                st.warning(f"❌ Aucun résultat trouvé dans {kb_title}")

        # Résumé final
        total_results = sum(len(ctx.results) for ctx in search_contexts)
        if search_contexts:
            st.success(f"🎯 Total: {total_results} résultats trouvés dans {len(search_contexts)} bases")
        else:
            st.error("❌ Aucun résultat trouvé dans l'ensemble des bases")

        return search_contexts