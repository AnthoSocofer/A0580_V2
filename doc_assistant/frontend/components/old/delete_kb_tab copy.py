#frontend/components/delete_kb_tab.py

import streamlit as st
from typing import Optional
from backend.kb_management.manager import KnowledgeBaseManager

class DeleteKBComponent:
    def __init__(self, kb_manager: KnowledgeBaseManager):
        self.kb_manager = kb_manager
        if 'kb_to_delete' not in st.session_state:
            st.session_state.kb_to_delete = None
        if 'delete_confirmed' not in st.session_state:
            st.session_state.delete_confirmed = False
            
    def _reset_state(self):
        """Réinitialise l'état de suppression"""
        st.session_state.kb_to_delete = None
        st.session_state.delete_confirmed = False
        
    def _show_kb_stats(self, kb_id: str) -> Optional[dict]:
        """Affiche les statistiques de la base sélectionnée"""
        kb = self.kb_manager.load_knowledge_base(kb_id)
        if not kb:
            return None
            
        stats = {
            "num_docs": len(kb.chunk_db.get_all_doc_ids()),
            "total_chars": kb.chunk_db.get_total_num_characters() if hasattr(kb.chunk_db, 'get_total_num_characters') else None
        }
        
        st.markdown("### Statistiques de la base")
        st.write(f"📚 Nombre de documents : {stats['num_docs']}")
        if stats['total_chars']:
            st.write(f"📝 Volume total : {stats['total_chars']:,} caractères")
            
        return stats

    def render(self):
        """Interface principale pour la suppression de bases"""
        st.header("🗑️ Supprimer une Base de Connaissances")
        
        # Liste des bases disponibles
        kb_list = self.kb_manager.list_knowledge_bases()
        if not kb_list:
            st.warning("Aucune base de connaissances disponible.")
            return
            
        # Sélection de la base
        selected_kb = st.selectbox(
            "Sélectionner une base à supprimer",
            options=[kb["id"] for kb in kb_list],
            format_func=lambda x: f"{x} - {next((kb['title'] for kb in kb_list if kb['id'] == x), x)}"
        )
        
        if selected_kb:
            kb_info = next((kb for kb in kb_list if kb["id"] == selected_kb), None)
            if kb_info:
                st.markdown(f"**Description**: {kb_info['description']}")
                stats = self._show_kb_stats(selected_kb)
                
                # Zone de bouton avec style personnalisé pour indiquer le danger
                if st.session_state.kb_to_delete != selected_kb:
                    st.markdown("---")
                    st.markdown("""
                        <style>
                        div[data-testid="stButton"] button {
                            background-color: #ff4b4b;
                            color: white;
                        }
                        </style>
                    """, unsafe_allow_html=True)
                    if st.button("🗑️ Supprimer cette base"):
                        st.session_state.kb_to_delete = selected_kb
                        st.rerun()
                
                # Confirmation de suppression
                if st.session_state.kb_to_delete == selected_kb:
                    st.warning(
                        f"⚠️ Êtes-vous sûr de vouloir supprimer définitivement la base "
                        f"'{kb_info['title']}' et tous ses documents ?"
                    )
                    
                    col1, col2 = st.columns(2)
                    with col1:
                        st.markdown("""
                            <style>
                            div[data-testid="stButton"] button {
                                background-color: #ff4b4b;
                                color: white;
                            }
                            </style>
                        """, unsafe_allow_html=True)
                        if st.button("✅ Oui, supprimer", key="confirm_delete"):
                            with st.spinner("Suppression en cours..."):
                                if self.kb_manager.delete_knowledge_base(selected_kb):
                                    st.success("Base supprimée avec succès!")
                                    self._reset_state()
                                    st.rerun()
                                else:
                                    st.error("Erreur lors de la suppression de la base")
                    
                    with col2:
                        if st.button("❌ Non, annuler", type="secondary"):
                            self._reset_state()
                            st.rerun()