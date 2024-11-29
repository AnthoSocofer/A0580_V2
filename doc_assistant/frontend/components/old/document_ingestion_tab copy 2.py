#doc_assistant/frontend/components/document_ingestion_tab.py
import streamlit as st
from pathlib import Path
from typing import Dict, Any, List, Tuple, Optional
from datetime import datetime
import tempfile
import asyncio
from functools import lru_cache
import time
from backend.kb_management.manager import KnowledgeBaseManager
from dsrag.dsparse.file_parsing.element_types import default_element_types
import os
from dsrag.embedding import Embedding

class DocumentIngestionComponent:
    """Composant optimisé pour l'ingestion de documents"""
    
    def __init__(self, kb_manager: KnowledgeBaseManager):
        self.kb_manager = kb_manager
        self._init_session_state()
        self._init_styles()
        
    def _init_styles(self):
        """Initialise les styles CSS pour une meilleure UX"""
        st.markdown("""
            <style>
            .upload-status {
                margin: 10px 0;
                padding: 10px;
                border-radius: 5px;
            }
            .status-processing {
                background-color: #f0f2f6;
                border-left: 5px solid #3498db;
            }
            .status-success {
                background-color: #eafaf1;
                border-left: 5px solid #2ecc71;
            }
            .status-error {
                background-color: #fdedec;
                border-left: 5px solid #e74c3c;
            }
            .config-section {
                background-color: #f8f9fa;
                padding: 15px;
                border-radius: 8px;
                margin: 10px 0;
            }
            .file-info {
                font-size: 0.9em;
                color: #666;
            }
            .progress-bar {
                height: 5px;
                margin: 5px 0;
            }
            </style>
        """, unsafe_allow_html=True)
    
    def _init_session_state(self):
        """Initialise ou récupère les états de session avec des valeurs par défaut optimisées"""
        default_config = {
            'auto_context': True,
            'semantic_sectioning': True,
            'chunk_size': 800,
            'min_length': 1600,
            'use_vlm': False,
            'vlm_provider': 'gemini',
            'vlm_model': 'gemini-1.5-flash-002',
            'exclude_elements': ['Header', 'Footer'],
            'custom_elements': False,
            'last_update': time.time()
        }
        
        if 'ingestion_config' not in st.session_state:
            st.session_state.ingestion_config = default_config
        elif 'last_update' not in st.session_state.ingestion_config:
            st.session_state.ingestion_config.update(default_config)
            
        # État pour le cache et la progression
        if 'kb_cache_timestamp' not in st.session_state:
            st.session_state.kb_cache_timestamp = time.time()
        if 'upload_progress' not in st.session_state:
            st.session_state.upload_progress = {}
        if 'upload_stats' not in st.session_state:
            st.session_state.upload_stats = {'success': 0, 'error': 0, 'total': 0}

    @lru_cache(maxsize=32)
    def _get_cached_kb_list(self, cache_timestamp: float) -> List[Dict]:
        """Récupère et met en cache la liste des bases de connaissances"""
        return self.kb_manager.list_knowledge_bases()

    def _validate_file(self, file_name: str, file_size: int, use_vlm: bool) -> Tuple[bool, str]:
        """Validation optimisée des fichiers avec vérifications rapides"""
        # Vérification rapide de l'extension
        ext = Path(file_name).suffix.lower()
        if use_vlm:
            if ext != '.pdf':
                return False, "Le traitement VLM n'est disponible que pour les fichiers PDF"
        elif ext not in ['.pdf', '.docx', '.txt', '.md']:
            return False, f"Extension non supportée: {ext}"
        
        # Vérification de la taille avec limite configurable
        max_size = 100 * 1024 * 1024  # 100MB
        if file_size > max_size:
            return False, f"Fichier trop volumineux (max: {max_size // (1024*1024)}MB)"
            
        return True, ""

    def _update_progress(self, key: str, status: str, message: str, progress: float = 0):
        """Met à jour la progression de manière atomique"""
        st.session_state.upload_progress[key] = {
            'status': status,
            'message': message,
            'progress': progress,
            'timestamp': time.time()
        }

    def _get_kb_embedding_config(self, kb_id: str) -> Optional[Dict[str, Any]]:
        """Récupère la configuration d'embedding d'une base de connaissances"""
        try:
            metadata_path = os.path.join(self.kb_manager.metadata_dir, f"{kb_id}.json")
            with open(metadata_path, 'r') as f:
                metadata = json.load(f)
            return metadata.get('embedding_config')
        except Exception:
            return None

    def _create_embedding_model(self, config: Dict[str, Any]) -> Embedding:
        """Crée un modèle d'embedding à partir de la configuration"""
        provider = config['provider']
        model = config['model']
        dimension = config['dimension']

        if provider not in self.kb_manager.SUPPORTED_EMBEDDING_MODELS:
            raise ValueError(f"Provider d'embedding non supporté: {provider}")
            
        if model not in self.kb_manager.SUPPORTED_EMBEDDING_MODELS[provider]["models"]:
            raise ValueError(f"Modèle d'embedding non supporté pour {provider}: {model}")

        model_class = self.kb_manager.SUPPORTED_EMBEDDING_MODELS[provider]["class"]
        return model_class(model=model, dimension=dimension)

    async def _process_file(
        self, 
        file,
        kb_id: str,
        config: Dict[str, Any],
        progress_key: str
    ) -> Tuple[bool, str]:
        """Traitement asynchrone optimisé des fichiers avec vérification d'embedding"""
        try:
            # Récupérer la configuration d'embedding de la base
            embedding_config = self._get_kb_embedding_config(kb_id)
            if not embedding_config:
                return False, "Configuration d'embedding non trouvée pour cette base"

            # Créer le modèle d'embedding correspondant
            try:
                embedding_model = self._create_embedding_model(embedding_config)
                # Mettre à jour la configuration avec le bon modèle d'embedding
                config['embedding_model'] = embedding_model
            except Exception as e:
                return False, f"Erreur lors de la création du modèle d'embedding: {str(e)}"


            self._update_progress(progress_key, 'processing', 'Validation du fichier...', 0.1)
            
            # Validation rapide
            is_valid, error = self._validate_file(
                file.name,
                len(file.getvalue()),
                config.get('file_parsing_config', {}).get('use_vlm', False)
            )
            if not is_valid:
                self._update_progress(progress_key, 'error', error)
                return False, error

            # Création du fichier temporaire avec contexte
            with tempfile.NamedTemporaryFile(delete=False, suffix=Path(file.name).suffix) as tmp_file:
                self._update_progress(progress_key, 'processing', 'Préparation du fichier...', 0.2)
                tmp_file.write(file.getvalue())
                tmp_file.flush()
                
                try:
                    # Enrichissement des métadonnées avec la configuration d'embedding
                    metadata = config.pop('metadata', {})
                    metadata.update({
                        'original_filename': file.name,
                        'file_size': len(file.getvalue()),
                        'file_type': Path(file.name).suffix.lower()[1:],
                        'upload_timestamp': datetime.now().isoformat(),
                        'embedding_info': {
                            'provider': embedding_config['provider'],
                            'model': embedding_config['model'],
                            'dimension': embedding_config['dimension']
                        }
                    })
                    self._update_progress(progress_key, 'processing', 'Ingestion en cours...', 0.4)
                    
                    success = await asyncio.get_event_loop().run_in_executor(
                        None,
                        lambda: self.kb_manager.add_document(
                            kb_id=kb_id,
                            file_path=tmp_file.name,
                            doc_id=file.name,
                            metadata=metadata,
                            embedding_model=embedding_model,  # Utiliser le même modèle d'embedding
                            **config
                        )
                    )
                    
                    if success:
                        self._update_progress(progress_key, 'success', 'Document ajouté avec succès', 1.0)
                        return True, ""
                    else:
                        self._update_progress(progress_key, 'error', "Échec de l'ingestion")
                        return False, "Échec de l'ingestion"
                        
                finally:
                    await asyncio.get_event_loop().run_in_executor(
                        None,
                        lambda: Path(tmp_file.name).unlink(missing_ok=True)
                    )
                    
        except Exception as e:
            error_msg = f"Erreur inattendue: {str(e)}"
            self._update_progress(progress_key, 'error', error_msg)
            return False, error_msg
        
    def _render_progress(self):
        """Affiche la progression avec une interface améliorée"""
        if not st.session_state.upload_progress:
            return
            
        st.markdown("### 📊 Progression des uploads")
        
        for key, progress in dict(sorted(
            st.session_state.upload_progress.items(),
            key=lambda x: x[1].get('timestamp', 0),
            reverse=True
        )).items():
            file_name = key.split('_')[0]
            status = progress['status']
            message = progress.get('message', '')
            
            # Utilisation de classes CSS personnalisées
            status_class = f"status-{status}"
            with st.container():
                st.markdown(
                    f"""<div class="upload-status {status_class}">
                        <div class="file-info">{file_name}</div>
                        {message}
                    </div>""",
                    unsafe_allow_html=True
                )
                
                if status == 'processing':
                    st.progress(progress.get('progress', 0), text=None)

    def _render_config_section(self) -> Dict[str, Any]:
        """Affiche la section de configuration avec une interface optimisée"""
        config = st.session_state.ingestion_config
        
        # Section de configuration de base
        with st.expander("⚙️ Configuration d'ingestion", expanded=False):
            st.markdown("### 📝 Paramètres de base")
            col1, col2 = st.columns(2)
            
            with col1:
                config['auto_context'] = st.toggle(
                    "👁️ Auto-contexte",
                    value=config['auto_context'],
                    help="Génération automatique du contexte et des résumés"
                )
                config['semantic_sectioning'] = st.toggle(
                    "🔍 Sectionnement sémantique",
                    value=config['semantic_sectioning'],
                    help="Découpage intelligent du document en sections"
                )
                
            with col2:
                config['chunk_size'] = st.slider(
                    "📏 Taille des chunks",
                    400, 2000, config['chunk_size'],
                    help="Taille des segments de texte"
                )
                config['min_length'] = st.slider(
                    "📐 Longueur minimale",
                    800, 3000, config['min_length'],
                    help="Longueur minimale avant découpage"
                )

            # Configuration VLM
            st.markdown("### 🔬 Configuration VLM")
            config['use_vlm'] = st.toggle(
                "Utiliser l'analyse visuelle (VLM)",
                value=config['use_vlm'],
                help="Active l'analyse des PDF via vision-langage"
            )
            
            if config['use_vlm']:
                vlm_col1, vlm_col2 = st.columns(2)
                with vlm_col1:
                    config['vlm_provider'] = st.selectbox(
                        "Provider VLM",
                        options=["gemini", "vertex_ai"],
                        index=0 if config['vlm_provider'] == "gemini" else 1
                    )

                with vlm_col2:
                    models = {
                        "gemini": ["gemini-1.5-flash-002"],
                        "vertex_ai": ["vertex-ai-vision-model"]
                    }
                    config['vlm_model'] = st.selectbox(
                        "Modèle VLM",
                        options=models[config['vlm_provider']]
                    )

                if config['vlm_provider'] == "vertex_ai":
                    config['project_id'] = st.text_input("Project ID GCP", value=config.get('project_id', ''))
                    config['location'] = st.text_input("Location GCP", value=config.get('location', 'us-central1'))

                # Configuration des éléments
                st.markdown("#### 🎯 Configuration des éléments")
                config['exclude_elements'] = st.multiselect(
                    "Éléments à exclure",
                    options=["Header", "Footer", "Equation", "Table"],
                    default=config['exclude_elements']
                )

                config['custom_elements'] = st.toggle(
                    "Elements personnalisés",
                    value=config['custom_elements']
                )
                
                if config['custom_elements']:
                    config['element_types'] = default_element_types
                else:
                    config['element_types'] = []

        # Métadonnées
        with st.expander("📋 Métadonnées", expanded=False):
            metadata = {}
            metadata["document_type"] = st.selectbox(
                "Type de document",
                ["rapport", "specification", "procedure", "documentation", "autre"]
            )
            
            metadata["tags"] = st.text_input(
                "Tags (séparés par des virgules)",
                help="Ex: technique, maintenance, sécurité"
            )
            
            if metadata["tags"]:
                metadata["tags"] = [tag.strip() for tag in metadata["tags"].split(",")]
                
            metadata["description"] = st.text_area(
                "Description",
                help="Description courte du document"
            )
            
            metadata["added_by"] = st.text_input("Ajouté par")

        # Construction de la configuration finale
        processing_config = {
            "auto_context_config": {
                "use_generated_title": False,
                "get_document_summary": config['auto_context'],
                "get_section_summaries": config['auto_context'] and config['semantic_sectioning']
            },
            "semantic_sectioning_config": {
                "use_semantic_sectioning": config['semantic_sectioning']
            },
            "chunk_size": config['chunk_size'],
            "min_length_for_chunking": config['min_length'],
            "metadata": metadata
        }

        if config['use_vlm']:
            vlm_config = {
                "provider": config['vlm_provider'],
                "model": config['vlm_model'],
                "exclude_elements": config['exclude_elements'],
                "element_types": config['element_types']
            }
            
            if config['vlm_provider'] == "vertex_ai":
                vlm_config.update({
                    "project_id": config.get('project_id', ''),
                    "location": config.get('location', '')
                })

            processing_config.update({
                "use_vlm": True,
                "vlm_config": vlm_config,
                "exclude_elements": config['exclude_elements'],
                "element_types": config['element_types']
            })

        return processing_config

    def _process_file_sync(
        self, 
        file,
        kb_id: str,
        config: Dict[str, Any],
        progress_key: str
    ) -> Tuple[bool, str]:
        """Version synchrone du traitement des fichiers"""
        try:
            self._update_progress(progress_key, 'processing', 'Validation du fichier...', 0.1)
            
            is_valid, error = self._validate_file(
                file.name,
                len(file.getvalue()),
                config.get('file_parsing_config', {}).get('use_vlm', False)
            )
            if not is_valid:
                self._update_progress(progress_key, 'error', error)
                return False, error

            with tempfile.NamedTemporaryFile(delete=False, suffix=Path(file.name).suffix) as tmp_file:
                self._update_progress(progress_key, 'processing', 'Préparation du fichier...', 0.2)
                tmp_file.write(file.getvalue())
                tmp_file.flush()
                
                try:
                    metadata = config.pop('metadata', {})
                    metadata.update({
                        'original_filename': file.name,
                        'file_size': len(file.getvalue()),
                        'file_type': Path(file.name).suffix.lower()[1:],
                        'upload_timestamp': datetime.now().isoformat()
                    })

                    self._update_progress(progress_key, 'processing', 'Ingestion en cours...', 0.4)
                    
                    success = self.kb_manager.add_document(
                        kb_id=kb_id,
                        file_path=tmp_file.name,
                        doc_id=file.name,
                        metadata=metadata,
                        chunk_size=config.get('chunk_size'),
                        min_length_for_chunking=config.get('min_length'),
                        auto_context_config=config.get('auto_context_config'),
                        semantic_sectioning_config=config.get('semantic_sectioning_config'),
                    )
                    
                    if success:
                        self._update_progress(progress_key, 'success', 'Document ajouté avec succès', 1.0)
                        return True, ""
                    else:
                        self._update_progress(progress_key, 'error', "Échec de l'ingestion")
                        return False, "Échec de l'ingestion"
                        
                finally:
                    Path(tmp_file.name).unlink(missing_ok=True)
                    
        except Exception as e:
            error_msg = f"Erreur inattendue: {str(e)}"
            self._update_progress(progress_key, 'error', error_msg)
            return False, error_msg

    def _process_folder_recursive(self, folder_path: str, kb_id: str, config: dict, allowed_extensions: List[str]) -> Tuple[int, int]:
        """
        Traite récursivement un dossier pour ingérer tous les PDFs.
        
        Args:
            folder_path: Chemin du dossier à traiter
            kb_id: ID de la base de connaissances
            config: Configuration d'ingestion
            allowed_extensions: Extensions de fichiers autorisées
        
        Returns:
            Tuple[int, int]: (nombre de fichiers traités avec succès, nombre total de fichiers)
        """
        success_count = 0
        total_files = 0
        
        for root, _, files in os.walk(folder_path):
            for filename in files:
                if any(filename.lower().endswith(ext) for ext in allowed_extensions):
                    total_files += 1
                    file_path = os.path.join(root, filename)
                    
                    # Créer une clé unique pour suivre la progression
                    progress_key = f"{filename}_{time.time()}"
                    
                    try:
                        # Lecture du fichier
                        with open(file_path, 'rb') as file:
                            file_content = file.read()
                            
                        # Créer un objet temporaire similaire à UploadedFile de Streamlit
                        class TempUploadFile:
                            def __init__(self, name, content):
                                self.name = name
                                self._content = content
                            def read(self):
                                return self._content
                            def getvalue(self):
                                return self._content
                        
                        temp_file = TempUploadFile(filename, file_content)
                        
                        # Utiliser le chemin relatif comme doc_id pour préserver la structure
                        rel_path = os.path.relpath(file_path, folder_path)
                        config['metadata'] = config.get('metadata', {})
                        config['metadata'].update({
                            'original_path': rel_path,
                            'folder_structure': True
                        })
                        
                        # Traiter le fichier
                        success, _ = self._process_file_sync(
                            file=temp_file,
                            kb_id=kb_id,
                            config=config,
                            progress_key=progress_key
                        )
                        
                        if success:
                            success_count += 1
                            
                    except Exception as e:
                        self._update_progress(
                            progress_key,
                            'error',
                            f"Erreur lors du traitement de {filename}: {str(e)}"
                        )
                        continue
                    
        return success_count, total_files

    def _process_uploaded_directory(
        self,
        files: List[Any],  # Modification ici pour accepter les fichiers uploadés
        kb_id: str,
        config: Dict
    ) -> Tuple[int, int]:
        """
        Traite un ensemble de fichiers uploadés représentant un dossier.
        
        Args:
            files: Liste des fichiers uploadés via Streamlit
            kb_id: ID de la base de connaissances
            config: Configuration d'ingestion
            
        Returns:
            Tuple[int, int]: (nombre de succès, nombre total)
        """
        success_count = 0
        total_files = 0
        
        # Organiser les fichiers par structure de dossier
        file_structure = {}
        for uploaded_file in files:
            # Nettoyer le chemin et créer la structure
            clean_path = uploaded_file.name.replace('\\', '/').lstrip('/')
            parts = clean_path.split('/')
            
            # Vérifier l'extension
            if not any(clean_path.lower().endswith(ext) for ext in 
                      ([".pdf"] if config.get("use_vlm", False) else [".pdf", ".docx", ".txt", ".md"])):
                continue
                
            file_structure[clean_path] = uploaded_file
            total_files += 1

        # Traiter chaque fichier
        with st.progress(0) as progress_bar:
            for idx, (file_path, file) in enumerate(file_structure.items()):
                try:
                    # Mise à jour des métadonnées avec le chemin
                    current_config = config.copy()
                    current_config['metadata'] = current_config.get('metadata', {})
                    current_config['metadata'].update({
                        'original_path': file_path,
                        'folder_structure': True,
                        'directory_upload': True
                    })
                    
                    # Clé unique pour le suivi
                    progress_key = f"{file_path}_{time.time()}"
                    
                    # Traiter le fichier
                    success, _ = self._process_file_sync(
                        file=file,
                        kb_id=kb_id,
                        config=current_config,
                        progress_key=progress_key
                    )
                    
                    if success:
                        success_count += 1
                        
                    # Mise à jour de la barre de progression
                    progress_bar.progress((idx + 1) / total_files)
                    
                except Exception as e:
                    self._update_progress(
                        progress_key,
                        'error',
                        f"Erreur lors du traitement de {file_path}: {str(e)}"
                    )
                    continue
                
        return success_count, total_files

    def render(self):
        """Interface principale pour l'ingestion de documents"""
        st.header("📥 Ingestion de Documents")

        # Configuration
        config = self._render_config_section()
        use_vlm = config.get("file_parsing_config", {}).get("use_vlm", False)

        # Sélection de la base
        kb_list = self._get_cached_kb_list(st.session_state.kb_cache_timestamp)
        if not kb_list:
            st.warning("🚫 Aucune base de connaissances disponible.")
            return

        selected_kb = st.selectbox(
            "📚 Base de connaissances",
            options=[kb["id"] for kb in kb_list],
            format_func=lambda x: f"{x} - {next((kb['title'] for kb in kb_list if kb['id'] == x), '')}"
        )

        if selected_kb:
            # Récupérer et afficher la configuration d'embedding de la base
            embedding_config = self._get_kb_embedding_config(selected_kb)
            if embedding_config:
                st.info(
                    f"📊 Configuration d'embedding de la base:\n"
                    f"- Provider: {embedding_config['provider']}\n"
                    f"- Modèle: {embedding_config['model']}\n"
                    f"- Dimension: {embedding_config['dimension']}"
                )
            else:
                st.warning("⚠️ Configuration d'embedding non trouvée pour cette base")
                return

        # Types de fichiers acceptés
        accepted_types = ["pdf"] if use_vlm else ["pdf", "docx", "txt", "md"]

        # Tabs pour les différentes méthodes d'upload
        upload_tab, directory_tab = st.tabs(["📄 Fichiers individuels", "📁 Dossier complet"])
        
        with upload_tab:
            # Zone de dépôt de fichiers individuels (code existant)
            uploaded_files = st.file_uploader(
                "📄 Déposez vos fichiers",
                accept_multiple_files=True,
                type=accepted_types
            )

            if uploaded_files and selected_kb:
                if st.button("📤 Démarrer l'ingestion", type="primary", key="single_upload"):
                    progress_bar = st.progress(0)
                    status_text = st.empty()
                    
                    total = len(uploaded_files)
                    success_count = 0
                    
                    for idx, file in enumerate(uploaded_files):
                        progress_key = f"{file.name}_{time.time()}"
                        success, _ = self._process_file_sync(
                            file=file,
                            kb_id=selected_kb,
                            config=config.copy(),
                            progress_key=progress_key
                        )
                        
                        if success:
                            success_count += 1
                        
                        progress_bar.progress((idx + 1) / total)
                        status_text.text(f"Traitement: {idx + 1}/{total} fichiers")
                    
                    if success_count == total:
                        st.success(f"✅ {success_count} documents ajoutés avec succès!")
                    else:
                        st.warning(f"⚠️ {success_count}/{total} documents traités avec succès")

        with directory_tab:
            st.write("📁 Sélectionnez un dossier contenant des documents")
            
            # Construction de l'arborescence à partir du dossier ./docs
            docs_path = Path("./docs")
            if not docs_path.exists():
                st.warning("⚠️ Le dossier ./docs n'existe pas. Veuillez le créer et y placer vos documents.")
                return
                
            # Récupération de l'arborescence
            directories = [d for d in docs_path.glob("**/*") if d.is_dir()]
            # Ajouter le dossier racine
            all_dirs = [docs_path] + directories
            # Formater les chemins pour l'affichage
            dir_options = {str(d): d.relative_to(docs_path) if d != docs_path else Path(".") 
                        for d in all_dirs}
            
            # Sélection du dossier
            selected_dir = st.selectbox(
                "Sélectionnez un dossier",
                options=list(dir_options.keys()),
                format_func=lambda x: str(dir_options[x])
            )
            
            if selected_dir and selected_kb:
                # Afficher la structure du dossier sélectionné
                selected_path = Path(selected_dir)
                pdf_files = list(selected_path.glob("**/*.pdf"))
                
                if not pdf_files:
                    st.warning("⚠️ Aucun fichier PDF trouvé dans ce dossier")
                else:
                    st.write(f"📊 {len(pdf_files)} fichiers PDF détectés")
                    
                    with st.expander("📂 Voir la structure détectée", expanded=False):
                        # Organiser les fichiers par sous-dossiers
                        files_by_dir = {}
                        for pdf in pdf_files:
                            rel_dir = pdf.parent.relative_to(selected_path)
                            if rel_dir not in files_by_dir:
                                files_by_dir[rel_dir] = []
                            files_by_dir[rel_dir].append(pdf.name)
                        
                        # Afficher l'arborescence
                        for dir_path, files in sorted(files_by_dir.items()):
                            if dir_path == Path("."):
                                st.text("📁 /")
                            else:
                                st.text(f"📁 {dir_path}")
                            for file in sorted(files):
                                st.text(f"    📄 {file}")
                    
                    # Options d'ingestion
                    recursive = st.checkbox(
                        "🔄 Inclure les sous-dossiers", 
                        value=True,
                        help="Traiter également les fichiers dans les sous-dossiers"
                    )
                    
                    if st.button("📤 Ingérer le dossier", type="primary", key="directory_process"):
                        with st.spinner("🔄 Traitement du dossier en cours..."):
                            # Déterminer les fichiers à traiter
                            pattern = "**/*.pdf" if recursive else "*.pdf"
                            files_to_process = list(selected_path.glob(pattern))
                            
                            if config.get("use_vlm", False):
                                process_files = files_to_process
                            else:
                                # Si pas de VLM, inclure aussi les autres types de fichiers
                                for ext in [".docx", ".txt", ".md"]:
                                    files_to_process.extend(selected_path.glob(f"**/*{ext}" if recursive else f"*{ext}"))
                            
                            success_count = 0
                            total = len(files_to_process)
                            
                            if total == 0:
                                st.warning("⚠️ Aucun fichier compatible trouvé dans le dossier")
                                return
                                
                            progress_bar = st.progress(0)
                            
                            for idx, file_path in enumerate(files_to_process):
                                try:
                                    # Créer un identifiant relatif pour le document
                                    rel_path = file_path.relative_to(selected_path)
                                    doc_id = str(rel_path)
                                    
                                    # Préparer la configuration selon la structure attendue
                                    parsing_config = {}
                                    if config.get("use_vlm"):
                                        parsing_config = {
                                            "use_vlm": True,
                                            "vlm_config": {
                                                "provider": config.get("vlm_provider"),
                                                "model": config.get("vlm_model"),
                                                "exclude_elements": config.get("exclude_elements", []),
                                                "element_types": config.get("element_types", [])
                                            }
                                        }
                                        
                                        if config.get("vlm_provider") == "vertex_ai":
                                            parsing_config["vlm_config"].update({
                                                "project_id": config.get("project_id"),
                                                "location": config.get("location")
                                            })

                                    # Préparation des métadonnées
                                    metadata = {
                                        'original_path': str(rel_path),
                                        'folder_structure': True,
                                        'source_directory': str(selected_path.name)
                                    }
                                    metadata.update(config.get('metadata', {}))

                                    try:
                                        success = self.kb_manager.add_document(
                                            kb_id=selected_kb,
                                            file_path=str(file_path),
                                            doc_id=doc_id,
                                            metadata=metadata,
                                            auto_context_config={
                                                "use_generated_title": False,
                                                "get_document_summary": config.get('auto_context', True),
                                                "get_section_summaries": config.get('auto_context', True) and config.get('semantic_sectioning', True)
                                            },
                                            semantic_sectioning_config={
                                                "use_semantic_sectioning": config.get('semantic_sectioning', True),
                                                "llm_provider": "openai",
                                                "language": "fr"
                                            },
                                            chunk_size=config.get('chunk_size', 800),  # Passé directement
                                            min_length_for_chunking=config.get('min_length', 1600)  # Passé directement
                                        )
                                        
                                        if success:
                                            success_count += 1
                                        
                                        # Mise à jour de la progression
                                        progress_bar.progress((idx + 1) / total)
                                        
                                    except Exception as e:
                                        st.error(f"Erreur lors du traitement de {rel_path}: {str(e)}")
                                        continue

                                except Exception as e:
                                    st.error(f"Erreur lors du traitement du fichier {file_path.name}: {str(e)}")
                                    continue
                            
                            # Affichage du résultat final
                            if success_count == total:
                                st.success(f"✅ {success_count} documents ajoutés avec succès!")
                            else:
                                st.warning(
                                    f"⚠️ {success_count}/{total} documents traités avec succès. "
                                    "Consultez les messages d'erreur ci-dessus pour plus de détails."
                                )

        # Affichage de la progression
        self._render_progress()