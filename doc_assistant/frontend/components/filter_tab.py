#frontend/components/filter_tab.py
import streamlit as st
from typing import Optional
from backend.kb_management.manager import KnowledgeBaseManager
from backend.utils.filter_utils import SearchFilter

class FilterTab:
    def __init__(self, kb_manager: KnowledgeBaseManager):
        self.kb_manager = kb_manager
        if 'selected_filters' not in st.session_state:
            st.session_state.selected_filters = SearchFilter()
        if 'force_rerun' not in st.session_state:
            st.session_state.force_rerun = False

    def _display_active_filters(self, search_filter: SearchFilter):
        """Affiche un résumé des filtres actifs"""
        st.markdown("---")
        st.subheader("📋 Filtres actifs")

        if not search_filter.has_filters():
            st.info("Aucun filtre actif - tous les documents seront inclus dans la recherche")
            return

        # Affichage des bases sélectionnées sans documents spécifiques
        kb_only = [kb_id for kb_id in search_filter.get_kb_ids() 
                  if not search_filter.doc_ids or kb_id not in search_filter.doc_ids]
        
        if kb_only:
            st.write("🗄️ **Bases complètes sélectionnées:**")
            for kb_id in kb_only:
                kb_info = next((kb for kb in self.kb_manager.list_knowledge_bases() 
                              if kb["id"] == kb_id), None)
                if kb_info:
                    st.markdown(f"- {kb_info['title']} (`{kb_id}`)")

        # Affichage des bases avec documents spécifiques
        if search_filter.doc_ids:
            st.write("📑 **Documents sélectionnés par base:**")
            for kb_id, doc_ids in search_filter.doc_ids.items():
                kb_info = next((kb for kb in self.kb_manager.list_knowledge_bases() 
                              if kb["id"] == kb_id), None)
                if kb_info:
                    with st.expander(f"📚 {kb_info['title']} ({len(doc_ids)} documents)"):
                        for doc_id in doc_ids:
                            doc_info = self.kb_manager.get_document(kb_id, doc_id)
                            if doc_info:
                                st.markdown(f"- {doc_info['title'] or doc_id}")
                            else:
                                st.markdown(f"- {doc_id}")

    def render(self) -> Optional[SearchFilter]:
        """Affiche l'interface de filtrage et retourne les filtres sélectionnés"""
        st.subheader("🔍 Filtrer les documents")
        
        # Liste des bases de connaissances
        kb_list = self.kb_manager.list_knowledge_bases()
        kb_ids = [kb["id"] for kb in kb_list]
        
        selected_kb = st.multiselect(
            "Sélectionner des bases de connaissances", 
            kb_ids,
            key="filter_kb_select",
            format_func=lambda x: f"{x} - {next((kb['title'] for kb in kb_list if kb['id'] == x), x)}"
        )
        
        # Dictionnaire pour stocker la sélection {kb_id: [doc_ids]}
        selected_docs = {}
        
        if selected_kb:
            for idx, kb_id in enumerate(selected_kb):
                documents = self.kb_manager.list_documents(kb_id)
                doc_options = {doc["id"]: doc["title"] or doc["id"] 
                             for doc in documents}
                
                selected = st.multiselect(
                    f"Documents dans {kb_id}",
                    list(doc_options.keys()),
                    format_func=lambda x: doc_options[x],
                    key=f"filter_docs_select_{kb_id}_{idx}"
                )
                
                if selected:
                    selected_docs[kb_id] = selected

        # Boutons d'action
        col1, col2 = st.columns(2)
        with col1:
            if st.button("✅ Appliquer les filtres", key="filter_apply_btn", type="primary"):
                if selected_kb or selected_docs:
                    new_filter = SearchFilter(
                        kb_ids=selected_kb if selected_kb else None,
                        doc_ids=selected_docs if selected_docs else None
                    )
                    st.session_state.selected_filters = new_filter
                    st.session_state.force_rerun = True
                    st.rerun()
                return None
            
        with col2:
            if st.button("🔄 Réinitialiser", key="filter_reset_btn"):
                st.session_state.selected_filters = SearchFilter()
                st.session_state.force_rerun = True
                st.rerun()
                return None

        # Affichage des filtres actifs
        if st.session_state.selected_filters.has_filters() or st.session_state.force_rerun:
            self._display_active_filters(st.session_state.selected_filters)
            st.session_state.force_rerun = False
            return st.session_state.selected_filters
            
        return None