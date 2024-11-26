import streamlit as st
from pathlib import Path
from typing import Dict, Any
from datetime import datetime
import tempfile
from backend.kb_management.manager import KnowledgeBaseManager
from dsrag.dsparse.file_parsing.element_types import default_element_types

class DocumentIngestionComponent:
    def __init__(self, kb_manager: KnowledgeBaseManager):
        self.kb_manager = kb_manager

    def _render_ingestion_config(self) -> Dict[str, Any]:
        """Affiche et retourne la configuration d'ingestion avec support VLM"""
        with st.expander("⚙️ Configuration avancée", expanded=False):
            col1, col2 = st.columns(2)
            
            with col1:
                auto_context = st.checkbox("Génération auto du contexte", value=True)
                semantic_sectioning = st.checkbox("Sectionnement sémantique", value=True)
                
            with col2:
                chunk_size = st.slider("Taille des chunks", 400, 2000, 800)
                min_length = st.slider("Longueur min pour chunking", 800, 3000, 1600)

            # Section VLM
            st.markdown("### 🔍 Configuration VLM")
            use_vlm = st.checkbox("Utiliser le VLM pour le parsing", value=False,
                                help="Active l'analyse des documents PDF via un modèle de vision-langage")
            
            if use_vlm:
                vlm_col1, vlm_col2 = st.columns(2)
                with vlm_col1:
                    vlm_provider = st.selectbox(
                        "Fournisseur VLM",
                        options=["gemini", "vertex_ai"],
                        help="Service fournissant le modèle vision-langage"
                    )

                with vlm_col2:
                    if vlm_provider == "gemini":
                        vlm_model = st.selectbox(
                            "Modèle VLM", 
                            options=["gemini-1.5-flash-002"]
                        )
                    else:
                        vlm_model = st.selectbox(
                            "Modèle VLM",
                            options=["vertex-ai-vision-model"]  # Remplacer par les modèles réels
                        )

                # Configuration supplémentaire pour Vertex AI
                if vlm_provider == "vertex_ai":
                    project_id = st.text_input("Project ID GCP", help="Identifiant du projet Google Cloud")
                    location = st.text_input("Location GCP", value="us-central1")
                else:
                    project_id = None
                    location = None

                # Exclusion d'éléments
                exclude_elements = st.multiselect(
                    "Éléments à exclure",
                    options=["Header", "Footer"],
                    default=["Header", "Footer"],
                    help="Éléments à ne pas inclure dans le texte final"
                )

                # Types d'éléments personnalisés
                custom_elements = st.checkbox("Personnaliser les types d'éléments", value=False)
                if custom_elements:
                    st.info("Utilisation des types d'éléments par défaut de dsRAG")
                    element_types = default_element_types
                else:
                    element_types = []

            # Configuration des métadonnées
            st.markdown("### 📋 Métadonnées personnalisées")
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

        # Construction de la configuration
        config = {
            "auto_context_config": {
                "use_generated_title": False,
                "get_document_summary": auto_context,
                "get_section_summaries": auto_context
            },
            "semantic_sectioning_config": {
                "use_semantic_sectioning": semantic_sectioning
            },
            "chunk_size": chunk_size,
            "min_length_for_chunking": min_length,
            "metadata": metadata if add_metadata else {}
        }

        # Ajout de la configuration VLM si activée
        if use_vlm:
            vlm_config = {
                "provider": vlm_provider,
                "model": vlm_model,
                "exclude_elements": exclude_elements,
                "element_types": element_types
            }
            
            if vlm_provider == "vertex_ai":
                vlm_config.update({
                    "project_id": project_id,
                    "location": location
                })

            config["file_parsing_config"] = {
                "use_vlm": True,
                "vlm_config": vlm_config
            }
        
        return config

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

                # Vérifier si VLM est activé et si le fichier est un PDF
                if config.get("file_parsing_config", {}).get("use_vlm", False):
                    if not file.name.lower().endswith('.pdf'):
                        return False, "Le traitement VLM n'est disponible que pour les fichiers PDF"
                
                success = self.kb_manager.add_document(
                    kb_id=kb_id,
                    file_path=tmp_file.name,
                    doc_id=file.name,
                    metadata=metadata,
                    **config
                )
                
                if success:
                    return True, ""
                return False, "Échec de l'ajout du document"
                
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
        use_vlm = config.get("file_parsing_config", {}).get("use_vlm", False)

        # Gestion des fichiers
        accepted_types = ["pdf"] if use_vlm else ["pdf", "docx", "txt", "md"]
        help_text = "Format supporté: PDF uniquement (VLM activé)" if use_vlm else "Formats supportés: PDF, DOCX, TXT, MD"

        if ingestion_type == "Fichiers":
            uploaded_files = st.file_uploader(
                "Sélectionner les fichiers",
                accept_multiple_files=True,
                type=accepted_types,
                help=help_text
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
                        config.copy()
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
                    extensions = [".pdf"] if use_vlm else [".pdf", ".docx", ".txt", ".md"]
                    files = [f for f in folder.rglob("*") if f.suffix.lower() in extensions]
                    total_files = len(files)
                    
                    if total_files == 0:
                        st.warning("Aucun document compatible trouvé dans le dossier")
                        return
                    
                    progress_bar = st.progress(0)
                    
                    for idx, file in enumerate(files):
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