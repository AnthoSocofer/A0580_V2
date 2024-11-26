from typing import Optional, Dict, List, Tuple
import streamlit as st
from backend.kb_management.manager import KnowledgeBaseManager 
from backend.utils.filter_utils import SearchFilter
from functools import lru_cache
import time

class FilterTab:
    def __init__(self, kb_manager: KnowledgeBaseManager):
        self.kb_manager = kb_manager
        
        # Initialisation des états de session
        if 'selected_filters' not in st.session_state:
            st.session_state.selected_filters = SearchFilter()
        if 'kb_cache_timestamp' not in st.session_state:
            st.session_state.kb_cache_timestamp = time.time()
        if 'doc_cache' not in st.session_state:
            st.session_state.doc_cache = {}
        if 'reset_triggered' not in st.session_state:
            st.session_state.reset_triggered = False

    @lru_cache(maxsize=32)
    def _get_cached_kb_list(self, cache_timestamp: float) -> List[Dict]:
        """
        Récupère la liste des bases avec mise en cache.
        Le timestamp permet d'invalider le cache quand nécessaire.
        """
        return self.kb_manager.list_knowledge_bases()

    def _get_cached_documents(self, kb_id: str) -> List[Dict]:
        """
        Récupère les documents d'une base avec mise en cache locale
        """
        if kb_id not in st.session_state.doc_cache:
            st.session_state.doc_cache[kb_id] = {
                'timestamp': time.time(),
                'docs': self.kb_manager.list_documents(kb_id)
            }
        return st.session_state.doc_cache[kb_id]['docs']

    def _invalidate_caches(self):
        """Force le rafraîchissement des caches"""
        st.session_state.kb_cache_timestamp = time.time()
        st.session_state.doc_cache.clear()
        self._get_cached_kb_list.cache_clear()

    def _format_kb_options(self, kb_list: List[Dict]) -> Dict[str, str]:
        """
        Prépare le format d'affichage des bases
        """
        return {
            kb["id"]: f"{kb['id']} - {kb['title']}"
            for kb in kb_list
        }

    def _lazy_load_documents(self, kb_id: str) -> Dict[str, str]:
        """
        Charge les documents d'une base de manière optimisée
        """
        documents = self._get_cached_documents(kb_id)
        return {
            doc["id"]: doc["title"] or doc["id"]
            for doc in documents
        }

    def _on_change_callback(self):
        """Callback appelé lorsque une sélection change"""
        selected_kb = st.session_state.get('filter_kb_select', [])
        selected_docs = {}
        
        if selected_kb:
            # Récupérer les documents sélectionnés pour chaque base
            for idx, kb_id in enumerate(selected_kb):
                key = f"filter_docs_select_{kb_id}_{idx}"
                if key in st.session_state and st.session_state[key]:
                    selected_docs[kb_id] = st.session_state[key]
        
        # Mettre à jour les filtres
        st.session_state.selected_filters = SearchFilter(
            kb_ids=selected_kb if selected_kb else None,
            doc_ids=selected_docs if selected_docs else None
        )

    def _trigger_reset(self):
        """Déclenche la réinitialisation"""
        st.session_state.reset_triggered = True
        st.session_state.selected_filters = SearchFilter()
        self._invalidate_caches()

    def _display_active_filters(self, search_filter: SearchFilter):
        """Affiche un résumé des filtres actifs avec mise en cache"""
        st.markdown("---")
        st.subheader("📋 Filtres actifs")

        if not search_filter.has_filters():
            st.info("Aucun filtre actif - tous les documents seront inclus dans la recherche")
            return

        kb_list = self._get_cached_kb_list(st.session_state.kb_cache_timestamp)
        kb_dict = {kb["id"]: kb for kb in kb_list}

        # Affichage des bases sélectionnées sans documents spécifiques
        kb_only = [kb_id for kb_id in search_filter.get_kb_ids() 
                  if not search_filter.doc_ids or kb_id not in search_filter.doc_ids]
        
        if kb_only:
            st.write("🗄️ **Bases complètes sélectionnées:**")
            for kb_id in kb_only:
                if kb_id in kb_dict:
                    st.markdown(f"- {kb_dict[kb_id]['title']} (`{kb_id}`)")

        # Affichage des bases avec documents spécifiques
        if search_filter.doc_ids:
            st.write("📑 **Documents sélectionnés par base:**")
            for kb_id, doc_ids in search_filter.doc_ids.items():
                if kb_id in kb_dict:
                    with st.expander(f"📚 {kb_dict[kb_id]['title']} ({len(doc_ids)} documents)"):
                        doc_options = self._lazy_load_documents(kb_id)
                        for doc_id in doc_ids:
                            st.markdown(f"- {doc_options.get(doc_id, doc_id)}")

    def render(self) -> Optional[SearchFilter]:
        """Interface de filtrage optimisée"""
        st.subheader("🔍 Filtrer les documents")
        
        # Récupération des bases avec cache
        kb_list = self._get_cached_kb_list(st.session_state.kb_cache_timestamp)
        kb_options = self._format_kb_options(kb_list)
        
        # Sélection des bases avec callback de changement
        default_value = [] if st.session_state.reset_triggered else None
        selected_kb = st.multiselect(
            "Sélectionner des bases de connaissances", 
            options=list(kb_options.keys()),
            format_func=lambda x: kb_options[x],
            key="filter_kb_select",
            on_change=self._on_change_callback,
            default=default_value
        )

        # Réinitialiser le flag de reset après la création du multiselect
        if st.session_state.reset_triggered:
            st.session_state.reset_triggered = False
        
        # Container pour les sélections de documents
        doc_container = st.container()
        
        # Chargement progressif des documents par base
        if selected_kb:
            with doc_container:
                for idx, kb_id in enumerate(selected_kb):
                    doc_options = self._lazy_load_documents(kb_id)
                    
                    st.multiselect(
                        f"Documents dans {kb_id}",
                        options=list(doc_options.keys()),
                        format_func=lambda x: doc_options[x],
                        key=f"filter_docs_select_{kb_id}_{idx}",
                        on_change=self._on_change_callback
                    )

        # Bouton de réinitialisation
        if st.button("🔄 Réinitialiser", use_container_width=True):
            self._trigger_reset()
            st.rerun()

        # Affichage des filtres actifs
        if st.session_state.selected_filters.has_filters():
            self._display_active_filters(st.session_state.selected_filters)
        
        return st.session_state.selected_filters