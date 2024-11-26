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

    async def _process_file(
        self, 
        file,
        kb_id: str,
        config: Dict[str, Any],
        progress_key: str
    ) -> Tuple[bool, str]:
        """Traitement asynchrone optimisé des fichiers"""
        try:
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
                    # Enrichissement des métadonnées
                    metadata = config.pop('metadata', {})
                    metadata.update({
                        'original_filename': file.name,
                        'file_size': len(file.getvalue()),
                        'file_type': Path(file.name).suffix.lower()[1:],
                        'upload_timestamp': datetime.now().isoformat(),
                        'processing_config': {
                            'use_vlm': config.get('file_parsing_config', {}).get('use_vlm', False),
                            'chunk_size': config.get('chunk_size'),
                            'semantic_sectioning': config.get('semantic_sectioning_config', {}).get('use_semantic_sectioning')
                        }
                    })

                    self._update_progress(progress_key, 'processing', 'Ingestion en cours...', 0.4)
                    
                    # Traitement asynchrone via executor
                    success = await asyncio.get_event_loop().run_in_executor(
                        None,
                        lambda: self.kb_manager.add_document(
                            kb_id=kb_id,
                            file_path=tmp_file.name,
                            doc_id=file.name,
                            metadata=metadata,
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
                    # Nettoyage asynchrone du fichier temporaire
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

    def render(self):
        """Interface principale synchrone pour l'ingestion de documents"""
        st.header("📥 Ingestion de Documents")

        # Configuration
        config = self._render_config_section()
        use_vlm = config.get("file_parsing_config", {}).get("use_vlm", False)

        # Sélection de la base
        kb_list = self._get_cached_kb_list(st.session_state.kb_cache_timestamp)
        if not kb_list:
            st.warning("🚫 Aucune base de connaissances disponible.")
            return

        kb_options = {
            kb["id"]: f"{kb['title']} ({kb['id']})"
            for kb in kb_list
        }
        
        selected_kb = st.selectbox(
            "📚 Base de connaissances",
            options=list(kb_options.keys()),
            format_func=lambda x: kb_options[x]
        )

        # Types de fichiers acceptés
        accepted_types = ["pdf"] if use_vlm else ["pdf", "docx", "txt", "md"]
        
        # Zone de dépôt de fichiers
        uploaded_files = st.file_uploader(
            "📄 Déposez vos fichiers",
            accept_multiple_files=True,
            type=accepted_types
        )

        if uploaded_files and selected_kb:
            if st.button("📤 Démarrer l'ingestion", type="primary"):
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
                    
                    # Mise à jour de la progression
                    progress = (idx + 1) / total
                    progress_bar.progress(progress)
                    status_text.text(f"Traitement: {idx + 1}/{total} fichiers")
                
                if success_count == total:
                    st.success(f"✅ {success_count} documents ajoutés avec succès!")
                else:
                    st.warning(f"⚠️ {success_count}/{total} documents traités avec succès")
        
        # Affichage de la progression
        self._render_progress()
