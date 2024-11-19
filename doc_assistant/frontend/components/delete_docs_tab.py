#frontend/components/delete_docs_tab.py
from typing import List, Optional
import streamlit as st
import os
from datetime import datetime
from backend.kb_management.manager import KnowledgeBaseManager
from pathlib import Path

class DeleteDocsComponent:
    def __init__(self, kb_manager: KnowledgeBaseManager):
        self.kb_manager = kb_manager
        
    def render(self):
        """Interface principale pour la suppression de documents"""
        st.header("Supprimer des Documents")
        
        # Liste des bases disponibles
        kb_list = self.kb_manager.list_knowledge_bases()
        if not kb_list:
            st.warning("Aucune base de connaissances disponible.")
            return

        # Sélection de la base
        selected_kb = st.selectbox(
            "Base de connaissances",
            options=[kb["id"] for kb in kb_list],
            format_func=lambda x: f"{x} - {next((kb['title'] for kb in kb_list if kb['id'] == x), '')}",
            key="delete_kb_select"
        )
        
        if not selected_kb:
            return

        # Chargement de la base sélectionnée
        kb = self.kb_manager.load_knowledge_base(selected_kb)
        if not kb:
            st.error(f"Impossible de charger la base {selected_kb}")
            return
            
        # Affichage des documents
        self._render_document_list(kb)

    def _render_document_list(self, kb):
        """Affiche la liste des documents avec options de suppression"""
        # Récupération de la liste des documents
        documents = kb.chunk_db.get_all_doc_ids()
        
        if not documents:
            st.info("Cette base ne contient aucun document.")
            return
            
        st.subheader("Documents disponibles")
        
        # Filtre de recherche
        search = st.text_input("🔍 Rechercher un document")
        filtered_docs = [doc for doc in documents 
                        if search.lower() in doc.lower()] if search else documents

        # Affichage de chaque document
        for doc_id in filtered_docs:
            col1, col2 = st.columns([4, 1])
            
            with col1:
                # Récupération et affichage des métadonnées
                doc_info = kb.chunk_db.get_document(doc_id)
                if doc_info:
                    st.markdown(f"📄 **{doc_info['title'] or doc_id}**")
                    if doc_info.get('created_on'):
                        st.caption(f"Ajouté le: {datetime.fromtimestamp(int(doc_info['created_on'])).strftime('%d/%m/%Y')}")
            
            with col2:
                # Bouton de suppression
                if st.button("🗑️", key=f"delete_{doc_id}", help=f"Supprimer {doc_id}"):
                    if st.session_state.get(f"confirm_{doc_id}", False):
                        try:
                            kb.delete_document(doc_id)
                            st.success(f"Document '{doc_id}' supprimé avec succès")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Erreur lors de la suppression: {str(e)}")
                    else:
                        st.session_state[f"confirm_{doc_id}"] = True
                        st.warning("Confirmer la suppression ?")
            
            st.divider()