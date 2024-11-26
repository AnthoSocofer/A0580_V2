# doc_assistant/frontend/components/document_viewer_tab.py

import streamlit as st
from typing import Dict, List, Optional, Union
from datetime import datetime
from backend.kb_management.manager import KnowledgeBaseManager

class DocumentViewerComponent:
    def __init__(self, kb_manager: KnowledgeBaseManager):
        self.kb_manager = kb_manager
        
        # Initialisation du cache de session pour les filtres
        if 'doc_viewer_kb_filter' not in st.session_state:
            st.session_state.doc_viewer_kb_filter = []
            
        # Styles CSS personnalisés pour l'affichage
        self._init_styles()

    def _init_styles(self):
        """Initialise les styles CSS pour l'affichage des documents"""
        st.markdown("""
            <style>
            .doc-container {
                border: 1px solid #e0e0e0;
                border-radius: 8px;
                padding: 12px;
                margin: 8px 0;
                background-color: white;
                transition: all 0.2s ease;
            }
            .doc-container:hover {
                box-shadow: 0 2px 4px rgba(0,0,0,0.1);
                transform: translateY(-1px);
            }
            .doc-header {
                display: flex;
                justify-content: space-between;
                align-items: center;
                margin-bottom: 8px;
            }
            .doc-title {
                font-weight: 600;
                color: #1e88e5;
            }
            .doc-meta {
                font-size: 0.9em;
                color: #757575;
            }
            .kb-badge {
                background-color: #e3f2fd;
                color: #1565c0;
                padding: 4px 8px;
                border-radius: 12px;
                font-size: 0.8em;
            }
            .doc-stats {
                display: flex;
                gap: 12px;
                font-size: 0.85em;
                color: #616161;
                margin-top: 8px;
            }
            </style>
        """, unsafe_allow_html=True)

    def _format_size(self, size: Union[int, str, None]) -> str:
        """Formate la taille du fichier en unité lisible"""
        try:
            size_bytes = int(size) if size is not None else 0
        except (ValueError, TypeError):
            return "N/A"
            
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size_bytes < 1024:
                return f"{size_bytes:.1f} {unit}"
            size_bytes /= 1024
        return f"{size_bytes:.1f} TB"

    def _format_date(self, timestamp: Union[int, str, None]) -> str:
        """Formate la date en format lisible"""
        try:
            if timestamp is None:
                return "N/A"
            # Si c'est une chaîne, essayer de la convertir en timestamp
            if isinstance(timestamp, str):
                try:
                    return datetime.fromisoformat(timestamp).strftime("%d/%m/%Y %H:%M")
                except ValueError:
                    timestamp = int(float(timestamp))
            return datetime.fromtimestamp(int(timestamp)).strftime("%d/%m/%Y %H:%M")
        except (ValueError, TypeError):
            return "N/A"

    def _get_filtered_documents(self) -> Dict[str, Dict]:
        """Récupère les documents filtrés par base"""
        kb_list = self.kb_manager.list_knowledge_bases()
        documents_by_kb = {}
        
        selected_kbs = st.session_state.doc_viewer_kb_filter
        
        for kb in kb_list:
            if not selected_kbs or kb["id"] in selected_kbs:
                documents = self.kb_manager.list_documents(kb["id"])
                if documents:  # Ne pas inclure les bases vides
                    documents_by_kb[kb["id"]] = {
                        "title": kb["title"],
                        "docs": documents
                    }
        
        return documents_by_kb

    def render(self):
        """Affiche l'interface de consultation des documents"""
        st.header("📚 Documents")
        
        # Filtres
        kb_list = self.kb_manager.list_knowledge_bases()
        if not kb_list:
            st.warning("Aucune base de connaissances disponible.")
            return
            
        kb_options = {kb["id"]: f"{kb['title']} ({kb['id']})" for kb in kb_list}
        
        st.multiselect(
            "Filtrer par base de connaissances",
            options=list(kb_options.keys()),
            format_func=lambda x: kb_options[x],
            key="doc_viewer_kb_filter",
            placeholder="Toutes les bases"
        )
        
        # Recherche
        search_query = st.text_input("🔍 Rechercher un document", placeholder="Titre, type, tags...")
        
        # Récupération et affichage des documents
        documents_by_kb = self._get_filtered_documents()
        
        if not documents_by_kb:
            if st.session_state.doc_viewer_kb_filter:
                st.info("Aucun document trouvé dans les bases sélectionnées.")
            else:
                st.info("Aucun document trouvé.")
            return
            
        total_docs = sum(len(kb_info["docs"]) for kb_info in documents_by_kb.values())
        st.write(f"### {total_docs} documents trouvés")
        
        for kb_id, kb_info in documents_by_kb.items():
            with st.expander(f"📁 {kb_info['title']} ({len(kb_info['docs'])} documents)", expanded=True):
                for doc in kb_info["docs"]:
                    # Filtrage par recherche
                    if search_query:
                        doc_metadata = doc.get('metadata', {})
                        search_text = f"{doc['title']} {doc_metadata.get('file_type', '')} {' '.join(doc_metadata.get('tags', []))}"
                        if search_query.lower() not in search_text.lower():
                            continue
                    
                    # Extraction sécurisée des métadonnées
                    metadata = doc.get('metadata', {})
                    file_type = metadata.get('file_type', 'N/A')
                    file_size = metadata.get('file_size')
                    created_on = doc.get('created_on')
                    tags = metadata.get('tags', [])
                    
                    # Affichage du document
                    st.markdown(f"""
                        <div class="doc-container">
                            <div class="doc-header">
                                <span class="doc-title">📄 {doc.get('title', doc.get('id', 'Sans titre'))}</span>
                                <span class="kb-badge">{kb_info['title']}</span>
                            </div>
                            <div class="doc-meta">
                                ID: {doc.get('id', 'N/A')}<br/>
                                Type: {file_type}
                            </div>
                            <div class="doc-stats">
                                <span>📅 {self._format_date(created_on)}</span>
                                <span>📦 {self._format_size(file_size)}</span>
                            </div>
                        </div>
                    """, unsafe_allow_html=True)
                    
                    # Affichage des tags si présents
                    if tags:
                        st.markdown(' '.join([f'`{tag}`' for tag in tags]))
                    
                    # Ligne de séparation entre les documents
                    #st.markdown("---")