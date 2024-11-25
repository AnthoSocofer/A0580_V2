# frontend/components/document_ingestion_tab.py
from pathlib import Path
import tempfile
import streamlit as st
from typing import Dict, Any
from datetime import datetime
from backend.kb_management.manager import KnowledgeBaseManager
import os 

class DocumentIngestionComponent:
    def __init__(self, kb_manager: KnowledgeBaseManager):
        self.kb_manager = kb_manager

    def _render_ingestion_config(self) -> Dict[str, Any]:
        """Affiche et retourne la configuration d'ingestion"""
        with st.expander("Options d'ingestion", expanded=False):
            col1, col2 = st.columns(2)
            
            with col1:
                auto_context = st.checkbox("Génération auto du contexte", value=True)
                semantic_sectioning = st.checkbox("Sectionnement sémantique", value=True)
                
            with col2:
                chunk_size = st.slider("Taille des chunks", 400, 2000, 800)
                min_length = st.slider("Longueur min pour chunking", 800, 3000, 1600)
            
            # Configuration des métadonnées personnalisées
            st.markdown("### Métadonnées personnalisées")
            add_metadata = st.checkbox("Ajouter des métadonnées", value=False)
            
            metadata = {}
            if add_metadata:
                metadata["date_added"] = datetime.now().isoformat()
                metadata["added_by"] = st.text_input("Ajouté par", "")
                metadata["document_type"] = st.selectbox(
                    "Type de document",
                    ["specification", "procedure", "rapport", "autre"]
                )
                metadata["tags"] = st.text_input(
                    "Tags (séparés par des virgules)",
                    help="Ex: technique, maintenance, sécurité"
                )
                if metadata["tags"]:
                    metadata["tags"] = [tag.strip() for tag in metadata["tags"].split(",")]
            
        return {
            "auto_context_config": {
                "use_generated_title": auto_context,
                "get_document_summary": auto_context,
                "get_section_summaries": auto_context and semantic_sectioning
            },
            "semantic_sectioning_config": {
                "use_semantic_sectioning": semantic_sectioning
            },
            "chunk_size": chunk_size,
            "min_length_for_chunking": min_length,
            "metadata": metadata if add_metadata else {}
        }

    def _process_uploaded_file(
        self, 
        file, 
        kb_id: str, 
        config: Dict[str, Any]
    ) -> tuple[bool, str]:
        """Traite un fichier uploadé"""
        with tempfile.NamedTemporaryFile(delete=False, suffix=Path(file.name).suffix) as tmp_file:
            tmp_file.write(file.getvalue())
            tmp_file.flush()
            
            try:
                metadata = config.pop("metadata", {})
                metadata.update({
                    "original_filename": file.name,
                    "file_size": len(file.getvalue()),
                    "file_type": Path(file.name).suffix.lower()[1:]
                })
                
                # Set title in auto_context_config
                auto_context_config = config.get("auto_context_config", {}) 
                auto_context_config["use_generated_title"] = False
                auto_context_config["document_title"] = os.path.splitext(os.path.basename(file.name))[0]
                config["auto_context_config"] = auto_context_config
                
                success = self.kb_manager.add_document(
                    kb_id=kb_id,
                    file_path=tmp_file.name,
                    doc_id=file.name,
                    metadata=metadata,
                    **config
                )
                
                return (True, "") if success else (False, "Failed to add document")
                
            except Exception as e:
                return False, str(e)
            finally:
                Path(tmp_file.name).unlink(missing_ok=True)

    def render(self):
        """Interface principale d'ajout de documents"""
        st.header("Ajouter des Documents")

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
            key="add_kb_select"
        )

        # Mode d'ajout
        ingestion_type = st.radio(
            "Mode d'ajout",
            ["Fichiers", "Dossier"],
            help="Choisissez entre l'upload de fichiers individuels ou l'import d'un dossier"
        )

        # Configuration d'ingestion
        config = self._render_ingestion_config()

        # Gestion des fichiers
        if ingestion_type == "Fichiers":
            uploaded_files = st.file_uploader(
                "Sélectionner les fichiers",
                accept_multiple_files=True,
                type=["pdf", "docx", "txt", "md"],
                help="Formats supportés: PDF, DOCX, TXT, MD"
            )

            if st.button("Ajouter les fichiers", type="primary") and uploaded_files:
                progress_bar = st.progress(0)
                status_container = st.empty()
                total_files = len(uploaded_files)
                success_count = 0
                
                for idx, file in enumerate(uploaded_files):
                    status_container.text(f"Traitement de {file.name}...")
                    success, error_message = self._process_uploaded_file(
                        file, 
                        selected_kb, 
                        config.copy()  # Important: on copie la config pour éviter les modifications
                    )
                    
                    if success:
                        success_count += 1
                        st.success(f"✅ {file.name} ajouté avec succès")
                    else:
                        st.error(f"❌ Erreur lors de l'ajout de {file.name}: {error_message}")
                    
                    progress_bar.progress((idx + 1) / total_files)

                status_container.empty()
                
                if success_count == total_files:
                    st.success(f"✅ Tous les documents ({success_count}) ont été ajoutés avec succès!")
                else:
                    st.warning(f"⚠️ {success_count}/{total_files} documents ajoutés avec succès")

        else:  # Mode Dossier
            folder_path = st.text_input(
                "Chemin du dossier",
                help="Chemin absolu vers le dossier contenant les documents"
            )
            
            if st.button("Ajouter le dossier", type="primary") and folder_path:
                folder = Path(folder_path)
                if not folder.exists():
                    st.error("❌ Chemin de dossier invalide")
                    return

                success_count = 0
                error_count = 0
                files_found = 0
                
                with st.spinner("Analyse du dossier en cours..."):
                    total_files = len(list(folder.rglob("*.[pPtTdDmM]*")))
                    if total_files == 0:
                        st.warning("Aucun document compatible trouvé dans le dossier")
                        return
                    
                    progress_bar = st.progress(0)
                    
                    for idx, file in enumerate(folder.rglob("*")):
                        if file.suffix.lower() in [".pdf", ".docx", ".txt", ".md"]:
                            files_found += 1
                            st.text(f"Traitement de {file.name}...")
                            
                            try:
                                # Préparation des métadonnées spécifiques au fichier
                                local_config = config.copy()
                                local_config["metadata"] = local_config.get("metadata", {}).copy()
                                local_config["metadata"].update({
                                    "original_path": str(file.relative_to(folder)),
                                    "file_size": file.stat().st_size,
                                    "file_type": file.suffix.lower()[1:]
                                })
                                
                                success = self.kb_manager.add_document(
                                    kb_id=selected_kb,
                                    file_path=str(file),
                                    doc_id=file.name,
                                    **local_config
                                )
                                
                                if success:
                                    success_count += 1
                                    st.success(f"✅ {file.name} ajouté avec succès")
                                else:
                                    error_count += 1
                                    st.error(f"❌ Échec de l'ajout de {file.name}")
                                    
                            except Exception as e:
                                error_count += 1
                                st.error(f"❌ Erreur lors de l'ajout de {file.name}: {str(e)}")
                                
                            progress_bar.progress((idx + 1) / total_files)

                if files_found == 0:
                    st.warning("Aucun document compatible trouvé dans le dossier")
                else:
                    if success_count > 0:
                        st.success(f"✅ {success_count} documents ajoutés avec succès!")
                    if error_count > 0:
                        st.warning(f"⚠️ {error_count} documents n'ont pas pu être ajoutés")
# import streamlit as st
# from pathlib import Path
# import tempfile
# from backend.kb_management.manager import KnowledgeBaseManager

# class DocumentIngestionComponent:
#     def __init__(self, kb_manager: KnowledgeBaseManager):
#         self.kb_manager = kb_manager

#     def _render_ingestion_config(self):
#         with st.expander("Options d'ingestion", expanded=False):
#             auto_context = st.checkbox("Générer le contexte automatiquement", value=True)
#             semantic_sectioning = st.checkbox("Utiliser le sectionnement sémantique", value=True)
#             chunk_size = st.slider("Taille des chunks", 400, 2000, 800)
#             min_length = st.slider("Longueur minimale pour chunking", 800, 3000, 1600)
            
#         return {
#             "auto_context_config": {"use_generated_title": auto_context},
#             "semantic_sectioning_config": {"use_semantic_sectioning": semantic_sectioning},
#             "chunk_size": chunk_size,
#             "min_length_for_chunking": min_length
#         }

#     def _process_uploaded_file(self, file, kb_id: str, config: dict):
#         with tempfile.NamedTemporaryFile(delete=False, suffix=Path(file.name).suffix) as tmp_file:
#             tmp_file.write(file.getvalue())
#             tmp_file.flush()
#             try:
#                 self.kb_manager.add_document(
#                     kb_id=kb_id,
#                     file_path=tmp_file.name,
#                     doc_id=file.name,
#                     **config
#                 )
#                 return True
#             except Exception as e:
#                 st.error(f"Erreur lors de l'ajout de {file.name}: {str(e)}")
#                 return False
#             finally:
#                 Path(tmp_file.name).unlink(missing_ok=True)

#     def render(self):
#         st.header("Ajouter des Documents")

#         kb_list = self.kb_manager.list_knowledge_bases()
#         if not kb_list:
#             st.warning("Aucune base de connaissances disponible.")
#             return

#         selected_kb = st.selectbox(
#             "Base de connaissances",
#             options=[kb["id"] for kb in kb_list],
#             format_func=lambda x: f"{x} - {next((kb['title'] for kb in kb_list if kb['id'] == x), '')}",
#             key="add_kb_select"
#         )

#         ingestion_type = st.radio(
#             "Mode d'ajout",
#             ["Fichiers", "Dossier"]
#         )

#         config = self._render_ingestion_config()

#         if ingestion_type == "Fichiers":
#             files = st.file_uploader(
#                 "Sélectionner les fichiers",
#                 accept_multiple_files=True,
#                 type=["pdf", "docx", "txt", "md"]
#             )

#             if st.button("Ajouter les fichiers") and files:
#                 with st.spinner("Ajout des documents en cours..."):
#                     success = True
#                     for file in files:
#                         if not self._process_uploaded_file(file, selected_kb, config):
#                             success = False
                    
#                     if success:
#                         st.success("Documents ajoutés avec succès!")

#         else:  # Dossier
#             folder_path = st.text_input("Chemin du dossier")
            
#             if st.button("Ajouter le dossier") and folder_path:
#                 folder = Path(folder_path)
#                 if not folder.exists():
#                     st.error("Dossier invalide")
#                     return

#                 with st.spinner("Ajout des documents en cours..."):
#                     success = True
#                     for file in folder.rglob("*"):
#                         if file.suffix.lower() in [".pdf", ".docx", ".txt", ".md"]:
#                             try:
#                                 self.kb_manager.add_document(
#                                     kb_id=selected_kb,
#                                     file_path=str(file),
#                                     doc_id=file.name,
#                                     **config
#                                 )
#                             except Exception as e:
#                                 st.error(f"Erreur lors de l'ajout de {file.name}: {str(e)}")
#                                 success = False
                    
#                     if success:
#                         st.success(f"Documents du dossier {folder.name} ajoutés avec succès!")