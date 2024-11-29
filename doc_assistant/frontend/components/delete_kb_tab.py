#frontend/components/delete_kb_tab.py

import streamlit as st
from typing import Optional
from pathlib import Path
import shutil
import os
import time
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

    def _verify_permissions(self, paths: list[Path]) -> tuple[bool, str]:
        """Vérifie les permissions pour la suppression"""
        for path in paths:
            if path.exists():
                try:
                    if path.is_file():
                        # Tester l'accès en écriture au fichier
                        os.access(path, os.W_OK)
                    elif path.is_dir():
                        # Tester l'accès en écriture au dossier
                        os.access(path, os.W_OK)
                        # Tester l'accès aux fichiers dans le dossier
                        for file in path.rglob('*'):
                            if not os.access(file, os.W_OK):
                                return False, f"Permission refusée pour: {file}"
                except Exception as e:
                    return False, f"Erreur de vérification des permissions: {str(e)}"
        return True, ""

    def _force_close_connections(self, kb_id: str):
        """Force la fermeture des connexions à la base"""
        try:
            # Forcer la libération des ressources de la base
            kb = self.kb_manager.load_knowledge_base(kb_id)
            if kb:
                # Fermer explicitement les connexions
                if hasattr(kb.chunk_db, 'close'):
                    kb.chunk_db.close()
                if hasattr(kb.vector_db, 'close'):
                    kb.vector_db.close()
                
                # Attendre un court instant pour la libération des ressources
                time.sleep(0.5)
        except Exception as e:
            st.warning(f"Avertissement lors de la fermeture des connexions: {str(e)}")

    def _delete_kb_files(self, kb_id: str) -> tuple[bool, str]:
        """Supprime les fichiers de la base avec gestion d'erreurs détaillée"""
        try:
            # Chemins des fichiers à supprimer
            paths = [
                Path(self.kb_manager.metadata_dir) / f"{kb_id}.json",
                Path(self.kb_manager.storage_directory) / "chunk_storage" / f"{kb_id}.db",
                Path(self.kb_manager.vector_storage_path) / kb_id
            ]

            # Vérifier les permissions
            has_permissions, error_msg = self._verify_permissions(paths)
            if not has_permissions:
                return False, error_msg

            # Forcer la fermeture des connexions
            self._force_close_connections(kb_id)

            # Supprimer les fichiers avec gestion d'erreurs détaillée
            for path in paths:
                if path.exists():
                    try:
                        if path.is_file():
                            path.unlink()
                        elif path.is_dir():
                            shutil.rmtree(path)
                    except PermissionError:
                        return False, f"Permission refusée pour: {path}"
                    except FileNotFoundError:
                        st.warning(f"Fichier déjà supprimé: {path}")
                    except Exception as e:
                        return False, f"Erreur lors de la suppression de {path}: {str(e)}"

            return True, "Suppression réussie"

        except Exception as e:
            return False, f"Erreur inattendue: {str(e)}"

    def _show_kb_details(self, kb_id: str) -> Optional[dict]:
        """Affiche les détails de la base avant suppression"""
        try:
            # Obtenir les informations détaillées de la base
            kb = self.kb_manager.load_knowledge_base(kb_id)
            if not kb:
                return None

            # Collecter les statistiques
            stats = {
                "num_docs": len(kb.chunk_db.get_all_doc_ids()),
                "total_chars": kb.chunk_db.get_total_num_characters() if hasattr(kb.chunk_db, 'get_total_num_characters') else None
            }

            # Calculer l'espace disque
            storage_paths = {
                "metadata": Path(self.kb_manager.metadata_dir) / f"{kb_id}.json",
                "chunk_storage": Path(self.kb_manager.storage_directory) / "chunk_storage" / f"{kb_id}.db",
                "vector_storage": Path(self.kb_manager.vector_storage_path) / kb_id
            }

            total_size = 0
            for path in storage_paths.values():
                if path.exists():
                    if path.is_file():
                        total_size += path.stat().st_size
                    elif path.is_dir():
                        total_size += sum(f.stat().st_size for f in path.rglob('*') if f.is_file())

            stats["disk_size"] = total_size

            # Afficher les informations
            st.markdown("### 📊 Statistiques")
            col1, col2 = st.columns(2)
            
            with col1:
                st.write(f"📚 Documents: {stats['num_docs']}")
                if stats['total_chars']:
                    st.write(f"📝 Volume: {stats['total_chars']:,} caractères")
            
            with col2:
                size_mb = round(total_size / (1024 * 1024), 2)
                st.write(f"💾 Espace disque: {size_mb} MB")

            # Afficher les fichiers à supprimer
            # with st.expander("🗃️ Fichiers à supprimer", expanded=False):
            #     for storage_type, path in storage_paths.items():
            #         if path.exists():
            #             st.code(f"{storage_type}: {path}")

            return stats

        except Exception as e:
            st.error(f"Erreur lors de la récupération des détails: {str(e)}")
            return None

    def render(self):
        """Interface principale"""
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
                # Afficher les informations de la base
                st.info(
                    f"""
                    **Base**: {kb_info['title']}
                    
                    **Description**: {kb_info['description']}
                    
                    **Langue**: {kb_info['language']}
                    """
                )
                
                # Afficher les détails et statistiques
                stats = self._show_kb_details(selected_kb)
                
                if stats:  # Vérifier que les statistiques ont été récupérées avec succès
                    # Zone de suppression
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
                    
                    # Demande de confirmation
                    if st.session_state.kb_to_delete == selected_kb:
                        st.warning(
                            f"""⚠️ Êtes-vous sûr de vouloir supprimer définitivement la base "{kb_info['title']}" ?
                            
                            Cette action :
                            - Supprimera {stats['num_docs']} documents
                            - Libérera {round(stats['disk_size'] / (1024 * 1024), 2)} MB d'espace disque
                            - Ne pourra pas être annulée
                            """
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
                                try:
                                    with st.spinner("Suppression en cours..."):
                                        # Tentative de suppression directe des fichiers
                                        success, error_msg = self._delete_kb_files(selected_kb)
                                        
                                        if success:
                                            st.success(f"✅ Base '{kb_info['title']}' supprimée avec succès!")
                                            # Forcer un rechargement pour actualiser la liste des bases
                                            st.session_state.kb_cache_timestamp = time.time()
                                            self._reset_state()
                                            st.rerun()
                                        else:
                                            st.error(f"❌ Erreur lors de la suppression: {error_msg}")
                                            
                                except Exception as e:
                                    st.error(f"❌ Erreur inattendue: {str(e)}")
                        
                        with col2:
                            if st.button("❌ Non, annuler", type="secondary"):
                                self._reset_state()
                                st.rerun()