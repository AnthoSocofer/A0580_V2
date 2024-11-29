#doc_assistant/frontend/components/kb_creation_tab.py

import streamlit as st
from pathlib import Path
from typing import Tuple, Optional
from backend.kb_management.manager import KnowledgeBaseManager
import os 
import json

class KBCreationComponent:
    """Composant pour la création de nouvelles bases de connaissances"""
    
    def __init__(self, kb_manager: KnowledgeBaseManager):
        self.kb_manager = kb_manager

    def _render_basic_info(self) -> Tuple[str, str, str, str]:
        """Rendu des champs d'information de base"""
        kb_id = st.text_input(
            "ID de la Base",
            help="Identifiant unique pour la base de connaissances",
            key="kb_id_input"
        )
        
        title = st.text_input(
            "Titre",
            help="Nom descriptif de la base de connaissances",
            key="kb_title_input"
        )
        
        description = st.text_area(
            "Description",
            help="Description du contenu et de l'usage de la base",
            key="kb_description_input"
        )
        
        language = st.selectbox(
            "Langue principale",
            options=["fr", "en", "es", "de", "it"],
            help="Langue principale des documents de la base",
            key="kb_language_select"
        )
        
        return kb_id, title, description, language

    def _render_embedding_options(self) -> Tuple[str, str, Optional[int]]:
        """Configuration du modèle d'embedding"""
        st.subheader("Configuration de l'Embedding")
        
        provider = st.selectbox(
            "Fournisseur d'embedding",
            options=list(self.kb_manager.SUPPORTED_EMBEDDING_MODELS.keys()),
            help="Service fournissant le modèle d'embedding",
            key="embedding_provider_select"
        )
        
        # Récupérer les modèles disponibles pour ce provider
        available_models = self.kb_manager.SUPPORTED_EMBEDDING_MODELS[provider]["models"]
        
        model = st.selectbox(
            "Modèle d'embedding",
            options=available_models,
            help="Modèle spécifique à utiliser pour l'embedding",
            key="embedding_model_select"
        )
        
        # Récupérer la dimension par défaut pour ce modèle
        dimension = self.kb_manager.SUPPORTED_EMBEDDING_MODELS[provider]["default_dimensions"][model]
        
        # Option pour personnaliser la dimension (expert)
        custom_dimension = st.checkbox(
            "Personnaliser la dimension", 
            value=False,
            help="⚠️ Option avancée - Ne modifier que si nécessaire",
            key="custom_dimension_check"
        )
        
        if custom_dimension:
            dimension = st.number_input(
                "Dimension des vecteurs",
                min_value=64,
                max_value=4096,
                value=dimension,
                help="Dimension des vecteurs d'embedding",
                key="dimension_input"
            )
            
        return provider, model, dimension

    def _render_reranker_options(self) -> Tuple[str, str]:
        """Configuration du modèle de reranking"""
        st.subheader("Configuration du Reranking")
        
        provider = st.selectbox(
            "Fournisseur de reranking",
            options=list(self.kb_manager.SUPPORTED_RERANKERS.keys()),
            help="Service fournissant le modèle de reranking",
            key="reranker_provider_select"
        )
        
        # Récupérer les modèles disponibles pour ce provider
        available_models = self.kb_manager.SUPPORTED_RERANKERS[provider]["models"]
        
        model = st.selectbox(
            "Modèle de reranking",
            options=available_models,
            help="Modèle spécifique à utiliser pour le reranking",
            key="reranker_model_select"
        )
        
        return provider, model

    def _validate_inputs(self, kb_id: str, title: str) -> bool:
        """Validation des entrées utilisateur"""
        if not kb_id:
            st.error("L'ID de la base est obligatoire")
            return False
        
        if not title:
            st.error("Le titre de la base est obligatoire")
            return False
            
        # Vérifier si l'ID existe déjà
        existing_kbs = self.kb_manager.list_knowledge_bases()
        if any(kb["id"] == kb_id for kb in existing_kbs):
            st.error(f"Une base avec l'ID '{kb_id}' existe déjà")
            return False
            
        return True

    def render(self):
        """Rendu principal du composant"""
        st.header("🗄️ Créer une Base de Connaissances")
        
        with st.form("kb_creation_form"):
            # Informations de base
            kb_id, title, description, language = self._render_basic_info()
            
            # Configuration avancée dans un expander
            with st.expander("⚙️ Configuration avancée", expanded=False):
                # Modèle d'embedding
                emb_provider, emb_model, dimension = self._render_embedding_options()
                
                # Modèle de reranking
                rerank_provider, rerank_model = self._render_reranker_options()
                
                # Choix du LLM pour l'auto-contexte
                llm_provider = st.selectbox(
                    "LLM pour l'auto-contexte",
                    options=["openai", "anthropic"],
                    help="Modèle de langage pour la génération de contexte",
                    key="llm_provider_select"
                )
            
            submitted = st.form_submit_button("Créer la base", type="primary")
                    
            if submitted:
                if not self._validate_inputs(kb_id, title):
                    return
                    
                try:
                    with st.spinner("Création de la base en cours..."):
                        # Configuration d'embedding 
                        embedding_config = {
                            'provider': emb_provider,
                            'model': emb_model,
                            'dimension': dimension
                        }

                        # Créer la base avec la configuration d'embedding
                        kb = self.kb_manager.create_knowledge_base(
                            kb_id=kb_id,
                            title=title,
                            description=description,
                            language=language,
                            #embedding_config=embedding_config,  # Passer la config complète
                            embedding_provider=emb_provider,
                            embedding_model=emb_model,
                            embedding_dimension=dimension,
                            reranker_provider=rerank_provider,
                            reranker_model=rerank_model,
                            llm_provider=llm_provider
                        )

                        st.success(f"✅ Base de connaissances '{title}' créée avec succès!")
                        return True
                                    
                except Exception as e:
                    st.error(f"❌ Erreur lors de la création de la base : {str(e)}")
                    return False